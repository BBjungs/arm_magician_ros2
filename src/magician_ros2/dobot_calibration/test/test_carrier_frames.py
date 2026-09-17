"""Independent camera carrier must never be confused with commanded TCP."""
from dataclasses import replace
import json
from types import SimpleNamespace
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from dobot_calibration.geometry import CalibrationError, Mount, transform, inverse
from dobot_calibration.registration import Capture, predicted_camera_motion
from dobot_calibration.solver import excitation, Solution
from dobot_calibration.workflow import calibration_poses, check_path, Workflow, save_bundle, load_bundle
from dobot_calibration.bundle import VerifiedBundle

def pose(x=0.2, y=0., z=0.18, yaw=0.):
    return transform(Rotation.from_euler('z', yaw, degrees=True).as_matrix(), [x,y,z])

def capture(command, carrier=None):
    return Capture(10., command, np.zeros((2,2,3),np.uint8), np.ones((2,2)),
                   np.eye(3), np.array([[0.,0.,1.]]), np.array([0.,0.,1.,0.]), {}, carrier)

def test_tool_rotation_does_not_create_camera_motion():
    first=capture(pose(yaw=0),pose(yaw=15))
    second=capture(pose(yaw=45),pose(yaw=15))
    extrinsic=transform(translation=[.03,0,.06])
    np.testing.assert_allclose(predicted_camera_motion(first,second,extrinsic),np.eye(4),atol=1e-12)
    legacy=replace(second,base_T_carrier=None)
    assert not np.allclose(predicted_camera_motion(replace(first,base_T_carrier=None),legacy,extrinsic),np.eye(4))

def test_camera_motion_uses_carrier_when_tool_yaw_is_constant():
    first=capture(pose(),pose(yaw=-10));second=capture(pose(),pose(yaw=10))
    expected=inverse(first.base_T_carrier)@second.base_T_carrier
    np.testing.assert_allclose(predicted_camera_motion(first,second,np.eye(4)),expected)

def test_tool_only_yaw_is_not_accepted_as_carrier_excitation():
    obs=[replace(capture(pose(.2+i*.01,yaw=i*5),pose(.2+i*.01)), stamp=10.+i) for i in range(7)]
    with pytest.raises(CalibrationError,match='excitation'):
        excitation(obs)
    with pytest.raises(CalibrationError,match='Mixed'):
        excitation([replace(obs[0],base_T_carrier=None),*obs[1:]])

def test_bracket_plan_excites_base_azimuth_but_preserves_tcp_orientation():
    start=pose(yaw=37)
    targets=calibration_poses(start,carrier_mode=True)
    azimuth=np.rad2deg(np.arctan2([p[1,3] for p in targets],[p[0,3] for p in targets]))
    assert np.ptp(azimuth)>=20-1e-8
    for target in targets:
        np.testing.assert_allclose(target[:3,:3],start[:3,:3])
    verify=calibration_poses(start,verification=True,carrier_mode=True)
    for a in targets:
        for b in verify: assert not np.allclose(a,b)

def test_clearance_uses_carrier_scene_and_tcp_swept_center():
    # Table at base Z=.10 via carrier, while commanded TCP is at .18.
    c=capture(pose(),pose(z=0.));mount=SimpleNamespace(tool_T_camera=np.eye(4),translation_error_bound_m=.003,envelope_radius_m=.03)
    check_path(pose(),pose(x=.205),c,mount)
    # Raising only the carrier/table by .10 brings the table above the TCP.
    with pytest.raises(CalibrationError,match='table clearance'):
        check_path(pose(),pose(x=.205),replace(c,base_T_carrier=pose(z=.20)),mount)

def test_capture_target_is_checked_against_tcp_not_carrier(tmp_path):
    commanded=pose();c=capture(commanded,pose(x=.25))
    backend=SimpleNamespace(move=lambda target:None,capture=lambda:c,checkpoint=lambda:None)
    w=Workflow(backend,None,tmp_path/'x.npz',{'carrier_frame':'bracket'})
    assert w.capture_at(commanded) is c
    with pytest.raises(CalibrationError,match='commanded pose'):
        w.capture_at(c.base_T_carrier)

def test_mount_requires_carrier_identity_and_tcp_envelope(tmp_path):
    import yaml
    p=tmp_path/'mount.yaml'
    data=dict(geometry_verified=True,rigid_to_camera_carrier=True,measurement_source='test fixture',
              translation_units='m',camera_carrier_frame='bracket',carrier_T_camera_optical=np.eye(4).tolist(),
        translation_error_bound_m=.003,envelope_radius_m=.04,envelope_reference_frame='TCP')
    p.write_text(yaml.safe_dump(data));Mount.load(p,carrier_frame='bracket')
    with pytest.raises(CalibrationError,match='frame does not match'):Mount.load(p,carrier_frame='other')
    with pytest.raises(CalibrationError,match='verified'):Mount.load(p)
    data['envelope_reference_frame']='bracket';p.write_text(yaml.safe_dump(data))
    with pytest.raises(CalibrationError,match='about command TCP'):Mount.load(p,carrier_frame='bracket')

def test_schema_two_preserves_command_and_carrier_and_blocks_tcp_consumer(tmp_path,monkeypatch):
    import dobot_calibration.workflow as wf
    path=tmp_path/'carrier.npz';c=capture(pose(),pose(x=.25));context={'carrier_frame':'bracket'}
    # Persistence contract test only: geometry/registration quality has separate tests.
    solution=Solution(np.eye(4),{}, {},np.array([c.base_T_carrier]*6),np.array([c.base_T_tool]*6))
    save_bundle(path,solution,c,context,{'result':'PASS'})
    monkeypatch.setattr(wf,'require_mount_agreement',lambda *a:None)
    monkeypatch.setattr(wf,'require_quality',lambda *a:None)
    monkeypatch.setattr(wf,'make_capture',lambda stamp,command,rgb,depth,k,cloud,hint,limits,base_T_carrier=None: capture(command,base_T_carrier))
    loaded,anchor=load_bundle(path,context,SimpleNamespace(tool_T_camera=np.eye(4)))
    np.testing.assert_allclose(anchor.base_T_tool,c.base_T_tool)
    np.testing.assert_allclose(anchor.base_T_carrier,c.base_T_carrier)
    np.testing.assert_allclose(loaded.command_training_poses,solution.command_training_poses)
    from dobot_calibration.geometry import fingerprint
    status=dict(state='READY',result='PASS',ready=True,bundle_loaded=True,geometry_verified=True,
                verification_status='PASS',reload_verification_status='PASS',bundle_path=str(path),
                context_digest=fingerprint(context))
    with pytest.raises(CalibrationError,match='TCP-only'):
        VerifiedBundle(path).load_transform(status)
    with pytest.raises(CalibrationError,match='identity'):
        load_bundle(path,{},SimpleNamespace(tool_T_camera=np.eye(4)))
    with pytest.raises(CalibrationError,match='context'):
        save_bundle(path,solution,c,{}, {'result':'PASS'})
    with pytest.raises(CalibrationError,match='separate command'):
        save_bundle(path,replace(solution,command_training_poses=None),c,context,{'result':'PASS'})


def test_solver_recovers_carrier_extrinsic_with_independent_tcp_yaw():
    from dobot_calibration.geometry import apply, transform_plane, pose_distance
    from dobot_calibration.registration import Registration
    from dobot_calibration.solver import solve, verify
    rng=np.random.default_rng(91)
    world=rng.uniform([.05,-.15,-.05],[.35,.15,.04],(500,3))
    actual=transform(Rotation.from_euler('xyz',[180,3,5],degrees=True).as_matrix(),[.03,-.01,.07])
    # Translation is a trusted measured constraint; only rotation is estimated.
    hint=transform(Rotation.from_euler('xyz',[179,4,6],degrees=True).as_matrix(),actual[:3,3])
    mount=Mount(hint,.001,.12,'synthetic carrier fixture','fixture')
    def observation(parent,stamp):
        command=parent.copy();command[:3,:3]=np.eye(3)
        camera=parent@actual
        c=capture(command,parent)
        return replace(c,stamp=stamp,cloud=apply(inverse(camera),world),
                       plane=transform_plane(inverse(camera),np.array([0,0,1,.1])),
                       quality={'depth_valid_ratio':1.})
    def pairs(obs):
        result=[]
        for j in range(1,len(obs)):
            first,second=obs[0],obs[j]
            motion=inverse(first.calibration_pose@actual)@second.calibration_pose@actual
            result.append((0,j,Registration(motion,second.cloud,first.cloud,
                          {'registration_fitness':1.,'registration_rmse_m':0.})))
        return result
    training=[observation(p,10+i) for i,p in enumerate([pose(),*calibration_poses(pose())])]
    solution=solve(training,mount,pairs=pairs(training))
    distance,angle=pose_distance(actual,solution.tool_T_camera)
    assert distance<1e-6 and angle<1e-4
    assert not np.allclose(solution.command_training_poses,solution.training_poses)
    fresh=[observation(p,100+i) for i,p in enumerate(calibration_poses(pose(),True))]
    report=verify(solution,training[0],fresh,mount,pairs=pairs([training[0],*fresh]))
    assert report['result']=='PASS', report
