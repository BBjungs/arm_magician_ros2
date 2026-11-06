from itertools import product
from types import SimpleNamespace
import threading

import numpy as np
import pytest

from dobot_calibration.geometry import CalibrationError, transform
from dobot_calibration.workspace_proposal import WorkspaceProposal, propose_workspace


def observations():
    return np.full((3, 120, 160), .6), np.array([[100., 0, 80], [0, 100., 60], [0, 0, 1]])


def test_sensor_proposal_is_never_a_verified_workspace():
    frames, k = observations()
    report = propose_workspace(frames, k)
    assert report['state'] == 'PROPOSED'
    assert report['camera_volume'] and report['base_volume'] is None
    assert not report['motion_authorized']
    assert not report['installation_verified']
    assert not report['whole_robot_environment_verified']
    assert 'CAMERA_TO_BASE_UNVERIFIED' in report['blockers']
    assert report['dominant_surface']['confirmed_table'] is False


@pytest.mark.parametrize('bad_value', [0., np.nan, np.inf, 2.])
def test_unknown_depth_is_excluded_instead_of_filled(bad_value):
    frames, k = observations()
    frames[:, :, 80] = bad_value
    report = propose_workspace(frames, k)
    left, top, right, bottom = report['observed_roi_px']
    assert right <= 80 or left > 80
    assert report['unknown_or_unstable_ratio'] > 0


def test_temporal_obstacle_is_not_smoothed_away():
    frames, k = observations()
    frames[1, :, 80] = .3
    report = propose_workspace(frames, k)
    left, _, right, _ = report['observed_roi_px']
    assert right <= 80 or left > 80


def test_box_corners_are_inside_observed_frustum_at_near_and_far_depths():
    frames, k = observations()
    k[0, 2] = 20.  # Off-center principal point exercises asymmetric rays.
    report = propose_workspace(frames, k)
    volume = report['camera_volume']
    left, top, right, bottom = report['observed_roi_px']
    for xyz in product(*zip(volume['min_m'], volume['max_m'])):
        pixel = k @ np.asarray(xyz)
        u, v = pixel[:2] / pixel[2]
        assert left <= u <= right - 1 and top <= v <= bottom - 1
        assert xyz[2] <= frames.min() - .035 + 1e-9


def test_rotated_base_box_is_inscribed_not_an_outer_bounding_box():
    from scipy.spatial.transform import Rotation
    frames, k = observations()
    mapping = transform(Rotation.from_euler('xyz', [35, 20, 45], degrees=True).as_matrix(), [.2, 0, .1])
    report = propose_workspace(frames, k, base_T_camera=mapping, envelope_radius_m=.2)
    base, camera = report['base_volume'], report['camera_volume']
    for xyz in product(*zip(base['min_m'], base['max_m'])):
        point = mapping[:3, :3].T @ (np.asarray(xyz) - mapping[:3, 3])
        assert np.all(point >= np.asarray(camera['min_m']) - 1e-9)
        assert np.all(point <= np.asarray(camera['max_m']) + 1e-9)
    assert 'ATTACHMENT_ENVELOPE_DOES_NOT_FIT' in report['blockers']
    assert not report['installation_verified']


@pytest.mark.parametrize('depth', [0., .16])
def test_insufficient_depth_never_creates_a_box(depth):
    frames, k = observations()
    frames.fill(depth)
    result = propose_workspace(frames, k)
    assert result['state'] == 'INSUFFICIENT_OBSERVATION'
    assert result['camera_volume'] is None and result['base_volume'] is None
    if depth > 0:
        assert result['observed_surface']['classification'] == 'MEASURED_SURFACE_NOT_FREE_VOLUME'
        assert result['observed_surface']['depth_range_m'] == [depth, depth]
        assert 'DEPTH_CLEARANCE_TOO_SMALL' in result['blockers']


def test_invalid_intrinsics_are_rejected():
    frames, k = observations()
    k[0, 0] = 0
    with pytest.raises(CalibrationError, match='INVALID'):
        propose_workspace(frames, k)


@pytest.fixture
def controller(tmp_path):
    from dobot_calibration.geometry import Limits
    node = SimpleNamespace(operation_lock=threading.Lock(), active_goal=None,
        real_motion_arm=None, workflow=None, mount=None, limits=Limits(), stop=threading.Event(),
        settings={'calibration_minimum_clearance_m': .025, 'camera_frame': 'camera_optical',
                  'base_frame': 'base', 'camera_id': 'test-camera', 'carrier_frame': '',
                  'automatic_workspace_file': str(tmp_path / 'must-not-be-written.yaml')},
        intrinsics_fingerprint=lambda info: 'intrinsics')
    node.stop.set()
    worker = WorkspaceProposal(node)
    frames, k = observations()
    worker.observe = lambda: (frames, k, np.eye(4), object(), [1., 1.1, 1.2],
                              np.zeros((120, 160, 3), dtype=np.uint8))
    return node, worker


def test_observation_preserves_stop_and_does_not_write_config(controller, tmp_path):
    node, worker = controller
    assert worker.start()[0]
    worker.worker.join(3)
    assert worker.snapshot()['state'] == 'PROPOSED'
    assert node.stop.is_set()
    assert not node.operation_lock.locked()
    assert not list(tmp_path.iterdir())
    assert not worker.snapshot()['motion_command_sent']


@pytest.mark.parametrize('active', ['operation', 'goal', 'permit'])
def test_active_operations_cannot_be_observed(controller, active):
    node, worker = controller
    if active == 'operation':
        node.operation_lock.acquire()
    elif active == 'goal':
        node.active_goal = object()
    else:
        node.real_motion_arm = object()
    assert not worker.start()[0]
    assert worker.worker is None
    assert node.operation_lock.locked() == (active == 'operation')


def test_cancel_during_analysis_discards_result(controller):
    node, worker = controller
    original = worker.observe
    def cancel():
        worker.cancel()
        return original()
    worker.observe = cancel
    assert worker.start()[0]
    worker.worker.join(3)
    assert worker.snapshot()['state'] == 'CANCELLED'
    assert 'camera_volume' not in worker.snapshot()
    assert not node.operation_lock.locked()


def test_observation_failure_releases_operation_lock(controller):
    node, worker = controller
    def fail():
        raise CalibrationError('RGB_DEPTH_FRAME_OR_TIMESTAMP_INVALID')
    worker.observe = fail
    assert worker.start()[0]
    worker.worker.join(3)
    assert worker.snapshot()['state'] == 'FAILED'
    assert not node.operation_lock.locked()


@pytest.mark.parametrize('verified', [False, True])
def test_base_projection_requires_reloaded_matching_calibration(controller, verified):
    node, worker = controller
    node.workflow = SimpleNamespace(solution=SimpleNamespace(tool_T_camera=np.eye(4)),
        reload_verified=verified, state='READY', context={'camera': 'test'})
    node.camera_context = lambda info: {'camera': 'test'}
    assert worker.start()[0]
    worker.worker.join(3)
    assert (worker.snapshot()['base_volume'] is not None) == verified
    assert not worker.snapshot()['installation_verified']


@pytest.mark.parametrize('moving', [False, True])
def test_observe_requires_new_images_and_checks_total_robot_drift(controller, monkeypatch, moving):
    from dobot_calibration import workspace_proposal as module
    node, worker = controller
    # Exercise the actual ingest loop, replacing only ROS messages and time waits.
    worker.observe = WorkspaceProposal.observe.__get__(worker)
    node.settings.update(capture_timeout_s=1., rgb_stale_timeout_s=1.5, depth_stale_timeout_s=1.5)
    node.lock = threading.Lock()
    node.history = []
    tick = SimpleNamespace(index=0)
    activated = []
    node.ensure_camera_sync = activated.append
    node.now_s = lambda: 10. + tick.index * .12
    k = observations()[1]
    info = SimpleNamespace(width=160, height=120, p=np.c_[k, np.zeros(3)].ravel(), k=k.ravel(), d=[])
    def camera():
        tick.index += 1
        stamp = node.now_s() - .01
        header = SimpleNamespace(frame_id='camera_optical',
            stamp=SimpleNamespace(sec=int(stamp), nanosec=round((stamp % 1) * 1e9)))
        info.header = header
        node.bundle = (SimpleNamespace(header=header), SimpleNamespace(header=header, encoding='16UC1'), info)
        return SimpleNamespace(synchronized=True)
    node.camera_freshness = camera
    node.hardware_readiness = lambda: SimpleNamespace(ready=True, reason='')
    node.bridge = SimpleNamespace(imgmsg_to_cv2=lambda msg, encoding:
        np.full((120, 160), 600, dtype=np.uint16) if encoding == 'passthrough'
        else np.zeros((120, 160, 3), dtype=np.uint8))
    monkeypatch.setattr(worker.cancelled, 'wait', lambda timeout: False)
    monkeypatch.setattr(module, 'settled_pose', lambda *args:
        transform(translation=[(tick.index - 1) * .0008 if moving else 0., 0., 0.]))
    if moving:
        with pytest.raises(CalibrationError, match='ROBOT_MOVED'):
            worker.observe()
    else:
        frames, _, _, _, stamps, _ = worker.observe()
        assert len(stamps) == 3 and len(set(stamps)) == 3
        assert min(stamps) > 10.
        assert np.allclose(frames, .6)
    assert activated == ['workspace_proposal']
    assert node.stop.is_set()
