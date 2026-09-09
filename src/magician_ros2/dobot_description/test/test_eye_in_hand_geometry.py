"""Synthetic geometry tests; fixture offsets are not physical calibration."""
import importlib.util
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from geometry_msgs.msg import PointStamped, TransformStamped
import numpy as np
import pytest
from rclpy.time import Time
from tf2_geometry_msgs import do_transform_point
from tf2_ros import Buffer
import xacro
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('geometry_display', ROOT / 'launch/display.launch.py')
DISPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISPLAY)
SYNTHETIC = {'tool': 'suction_cup', 'DOF': '4', 'use_camera': 'false',
             'enable_orbbec_mount': 'true', 'orbbec_mount_xyz': '0.04 -0.02 0.03',
             'orbbec_mount_rpy': f'0 {math.pi/2} 0', 'suction_tcp_xyz': '0 0 -0.06',
             'suction_tcp_rpy': '0 0 0'}


def model(mappings=SYNTHETIC):
    return ET.fromstring(xacro.process_file(str(ROOT / 'model/magician_standalone.urdf.xacro'),
                                           mappings=mappings).toxml())


def rotation(axis, angle):
    axis = np.array(axis, dtype=float)
    axis /= np.linalg.norm(axis)
    x, y, z = axis
    skew = np.array([[0,-z,y],[z,0,-x],[-y,x,0]])
    return np.eye(3) * math.cos(angle) + (1-math.cos(angle))*np.outer(axis,axis) + math.sin(angle)*skew


def joint_transform(joint, angles):
    origin = joint.find('origin')
    transform = np.eye(4)
    if origin is not None:
        transform[:3,3] = [float(v) for v in origin.get('xyz', '0 0 0').split()]
        r, p, y = [float(v) for v in origin.get('rpy', '0 0 0').split()]
        transform[:3,:3] = rotation([0,0,1],y) @ rotation([0,1,0],p) @ rotation([1,0,0],r)
    if joint.get('type') != 'fixed':
        mimic = joint.find('mimic')
        angle = angles.get(joint.get('name'), 0)
        if mimic is not None:
            angle = angles.get(mimic.get('joint'),0)*float(mimic.get('multiplier','1')) + float(mimic.get('offset','0'))
        transform[:3,:3] = transform[:3,:3] @ rotation([float(v) for v in joint.find('axis').get('xyz').split()],angle)
    return transform


def poses(angles):
    result = {'magician_root_link': np.eye(4)}
    remaining = list(model().findall('joint'))
    while remaining:
        progress = False
        for joint in list(remaining):
            parent, child = joint.find('parent').get('link'), joint.find('child').get('link')
            if parent in result:
                assert child not in result, 'Multiple parents or cycle'
                result[child] = result[parent] @ joint_transform(joint, angles)
                remaining.remove(joint); progress = True
        assert progress, 'Disconnected model or loop'
    base_inverse = np.linalg.inv(result['magician_base_link'])
    return {key: base_inverse @ value for key,value in result.items()}


def test_tree_and_tf_ownership():
    xml = model()
    links = {link.get('name') for link in xml.findall('link')}
    assert {'tool','camera_link','suction_tcp'} <= links
    assert not {'camera_depth_frame','camera_depth_optical_frame','camera_color_optical_frame'} & links
    assert set(poses({})) == links


def test_unverified_geometry_is_not_published():
    with pytest.raises(ValueError, match='not verified'):
        DISPLAY._mount_mappings(ROOT / 'model/eye_in_hand_mount.yaml')
    links = {link.get('name') for link in model({'tool':'suction_cup','DOF':'4'}).findall('link')}
    assert 'tool' in links
    assert not {'camera_link','suction_tcp'} & links


def test_mount_requires_explicit_offsets():
    with pytest.raises(xacro.XacroException):
        model({'tool':'suction_cup','DOF':'4','enable_orbbec_mount':'true'})


@pytest.mark.parametrize('bad', [[float('nan'),0,0], [45,0,0], [True,0,0], []])
def test_invalid_or_wrong_unit_geometry_is_rejected(tmp_path, bad):
    config = {'geometry_verified':True, 'rigid_to_rotating_tool':True,
              'measurement_source':'synthetic validation test only', 'translation_units':'m', 'rotation_units':'rad',
              'camera_link':{'xyz':bad,'rpy':[0,0,0]},'suction_tcp':{'xyz':[0,0,0],'rpy':[0,0,0]}}
    path = tmp_path/'mount.yaml'; path.write_text(yaml.safe_dump(config))
    with pytest.raises(ValueError): DISPLAY._mount_mappings(path)


def test_tool_stays_level_and_joint_four_rotates_mount():
    first = poses({'magician_joint_2':math.radians(20),'magician_joint_3':math.radians(10)})
    second = poses({'magician_joint_2':math.radians(20),'magician_joint_3':math.radians(10),'magician_joint_4':math.pi/2})
    np.testing.assert_allclose(first['tool'][:3,:3],np.eye(3),atol=1e-12)
    np.testing.assert_allclose(first['tool'][:3,3],second['tool'][:3,3],atol=1e-12)
    assert not np.allclose(first['camera_link'][:3,3],second['camera_link'][:3,3])


@pytest.mark.parametrize('yaw,expected', [(0,[0.237,-0.04,-0.335]),(math.pi/2,[0.04,0.237,-0.335])])
def test_optical_point_to_base_and_inverse_with_tf2(yaw, expected):
    matrices = poses({'magician_joint_1':yaw})
    # REP-103 optical axes: x right = -body y, y down = -body z, z forward = body x.
    optical = np.eye(4); optical[:3,:3] = [[0,0,1],[-1,0,0],[0,-1,0]]
    camera_to_base = matrices['camera_link'] @ optical
    np.testing.assert_allclose(camera_to_base @ [0.02,0.01,0.5,1], expected+[1],atol=1e-12)
    buffer = Buffer()
    # Encode the independently calculated base-to-optical transform in tf2.
    transform = TransformStamped(); transform.header.frame_id='magician_base_link'; transform.child_frame_id='synthetic_optical'
    transform.transform.translation.x,transform.transform.translation.y,transform.transform.translation.z = camera_to_base[:3,3].tolist()
    from scipy.spatial.transform import Rotation
    q = Rotation.from_matrix(camera_to_base[:3,:3]).as_quat()
    transform.transform.rotation.x,transform.transform.rotation.y,transform.transform.rotation.z,transform.transform.rotation.w = q.tolist()
    buffer.set_transform_static(transform,'synthetic_geometry_test')
    point = PointStamped();point.header.frame_id='synthetic_optical';point.point.x=.02;point.point.y=.01;point.point.z=.5
    out=do_transform_point(point,buffer.lookup_transform('magician_base_link','synthetic_optical',Time()))
    np.testing.assert_allclose([out.point.x,out.point.y,out.point.z],expected,atol=1e-12)
    back=do_transform_point(out,buffer.lookup_transform('synthetic_optical','magician_base_link',Time()))
    np.testing.assert_allclose([back.point.x,back.point.y,back.point.z],[.02,.01,.5],atol=1e-12)


def test_suction_tip_is_separate_from_camera_and_carrier():
    result=poses({})
    np.testing.assert_allclose(result['suction_tcp'][:3,3],[.207,0,.075],atol=1e-12)
    assert not np.allclose(result['suction_tcp'],result['camera_link'])
