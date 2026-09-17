import json
import numpy as np
import pytest
import yaml

from dobot_calibration.geometry import CalibrationError
from dobot_calibration.passive_session import PassiveSessionStore
from dobot_calibration.registration import Capture


def sample_capture():
    return Capture(
        123.5, np.eye(4), np.zeros((4, 5, 3), np.uint8),
        np.full((4, 5), 0.25), np.eye(3),
        np.array([[0., 0., .25], [.1, 0., .25], [0., .1, .25]]),
        np.array([0., 0., 1., -.25]), {'depth_valid_ratio': .75})


def metadata():
    return {'pose_index': 1, 'J4_yaw_deg': 7.0, 'sync_skew_ms': 4.0,
            'accepted': True, 'XYZ_mm': [150., 0., 100.]}


def test_accepted_pose_survives_store_restart(tmp_path):
    first = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    first.save_pose(sample_capture(), [1., 2., 3., .12], metadata(),
                    123.49, 123.494, 'intrinsics-a')
    second = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    captures, details = second.restore('intrinsics-a')
    assert len(captures) == len(details) == 1
    np.testing.assert_array_equal(captures[0].rgb, sample_capture().rgb)
    np.testing.assert_allclose(captures[0].base_T_tool, sample_capture().base_T_tool)
    np.testing.assert_allclose(captures[0].cloud, sample_capture().cloud)
    assert details[0]['J4_yaw_deg'] == 7.0
    assert second.manifest['accepted_pose_count'] == 1
    assert second.manifest['geometry_verified'] is False
    targets = [{'pose_index': 1, 'xyz_mm': [150., 0., 100.], 'j4_deg': 0.}]
    second.ensure_plan(targets)
    third = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    third.restore('intrinsics-a')
    assert third.manifest['target_poses'] == targets
    with np.load(second.session_dir / 'pose_001.npz', allow_pickle=False) as saved:
        assert str(saved['status']) == 'ACCEPTED'
        assert str(saved['intrinsics_fingerprint']) == 'intrinsics-a'
        assert saved['joint_names'].tolist() == [f'magician_joint_{i}' for i in range(1, 5)]
        assert json.loads(str(saved['camera_info_json'])) == {}


def test_incompatible_mount_or_intrinsics_is_not_silently_restored(tmp_path):
    store = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    store.save_pose(sample_capture(), [0., 0., 0., 0.], metadata(),
                    1., 1., 'intrinsics-a')
    with pytest.raises(CalibrationError, match='mount/config fingerprint changed'):
        PassiveSessionStore(tmp_path, 'mount-b', 'camera-a').restore()
    with pytest.raises(CalibrationError, match='intrinsics changed'):
        PassiveSessionStore(tmp_path, 'mount-a', 'camera-a').restore('intrinsics-b')


def test_corrupt_pose_is_not_silently_loaded(tmp_path):
    store = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    store.save_pose(sample_capture(), [0., 0., 0., 0.], metadata(),
                    1., 1., 'intrinsics-a')
    (store.session_dir / 'pose_001.npz').write_bytes(b'not-an-npz')
    with pytest.raises(CalibrationError, match='pose 1 is corrupt'):
        PassiveSessionStore(tmp_path, 'mount-a', 'camera-a').restore()


def test_pose_intrinsics_must_match_manifest(tmp_path):
    store = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    store.save_pose(sample_capture(), [0., 0., 0., 0.], metadata(),
                    1., 1., 'intrinsics-a')
    manifest_path = store.session_dir / 'manifest.yaml'
    manifest = yaml.safe_load(manifest_path.read_text())
    manifest['intrinsics_fingerprint'] = 'intrinsics-other'
    manifest_path.write_text(yaml.safe_dump(manifest))
    with pytest.raises(CalibrationError, match='disagrees with manifest'):
        PassiveSessionStore(tmp_path, 'mount-a', 'camera-a').restore()


def test_corrupt_manifest_is_not_silently_loaded(tmp_path):
    store = PassiveSessionStore(tmp_path, 'mount-a', 'camera-a')
    store.new('intrinsics-a')
    manifest = yaml.safe_load((store.session_dir / 'manifest.yaml').read_text())
    manifest['schema_version'] = 999
    (store.session_dir / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    with pytest.raises(CalibrationError, match='schema/status is incompatible'):
        PassiveSessionStore(tmp_path, 'mount-a', 'camera-a').restore()
