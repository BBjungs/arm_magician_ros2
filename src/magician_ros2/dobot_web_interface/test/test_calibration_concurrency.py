import threading

import numpy as np

import dobot_web_interface.web_interface as web_interface
from dobot_web_interface.web_interface import DobotWebNode


class _BlockingCalibrationStore:
    def __init__(self, entered, release):
        self._entered = entered
        self._release = release

    def load(self):
        return {
            'auto_calibration': {
                'sample_count': 8,
                'capture_timeout_sec': 1.0,
            }
        }

    def auto_compute(self, frames):
        self._entered.set()
        if not self._release.wait(timeout=2.0):
            raise TimeoutError('test did not release calibration')
        return {'calibration_valid': False, 'is_complete': False}


class _EyeInHandStore:
    @staticmethod
    def load():
        return {}


class _ConcurrentCalibrationNode:
    vision_auto_calibrate = DobotWebNode.vision_auto_calibrate
    _perform_auto_calibration = DobotWebNode._perform_auto_calibration
    _run_calibration_change = DobotWebNode._run_calibration_change
    get_eye_in_hand_annotated = DobotWebNode.get_eye_in_hand_annotated

    def __init__(self, calibration):
        self._calibration_operation_lock = threading.Lock()
        self._calibration_store = calibration
        self._eye_store = _EyeInHandStore()
        self._last_calibration_frame_source = 'test'
        self.jpeg_quality = 80
        self.latest_frame_calls = 0

    @staticmethod
    def _vision_mode_from_payload(_payload):
        return 'fixed_camera'

    def _calibration(self):
        return self._calibration_store

    @staticmethod
    def _capture_fresh_frames(sample_count, _timeout_sec):
        return [
            np.zeros((8, 8, 3), dtype=np.uint8)
            for _ in range(sample_count)
        ]

    @staticmethod
    def _make_vision_placeholder():
        return b'calibration-busy'

    def _latest_cv_frame(self):
        self.latest_frame_calls += 1
        return np.zeros((8, 8, 3), dtype=np.uint8)

    def _eye_in_hand(self):
        return self._eye_store

    @staticmethod
    def _current_intrinsics():
        return {
            'image_width': 8,
            'image_height': 8,
            'fx': 10.0,
            'fy': 10.0,
            'cx': 4.0,
            'cy': 4.0,
            'distortion_coefficients': [0.0] * 5,
        }

    @staticmethod
    def _current_tcp_pose():
        return None


def test_annotated_aruco_is_skipped_while_auto_calibration_runs(monkeypatch):
    calibration_entered = threading.Event()
    release_calibration = threading.Event()
    calibration = _BlockingCalibrationStore(
        calibration_entered,
        release_calibration,
    )
    node = _ConcurrentCalibrationNode(calibration)
    overlay_calls = []

    def render_overlay(*_args, **_kwargs):
        overlay_calls.append(True)
        return {'image': np.zeros((8, 8, 3), dtype=np.uint8)}

    monkeypatch.setattr(web_interface, 'render_aruco_overlay', render_overlay)
    outcome = {}

    def run_calibration():
        try:
            outcome['result'] = node.vision_auto_calibrate({'dry_run': True})
        except BaseException as exc:  # pragma: no cover - asserted below
            outcome['error'] = exc

    worker = threading.Thread(target=run_calibration)
    worker.start()
    try:
        assert calibration_entered.wait(timeout=1.0)
        assert node.get_eye_in_hand_annotated() == b'calibration-busy'
        assert overlay_calls == []
        assert node.latest_frame_calls == 0
    finally:
        release_calibration.set()
        worker.join(timeout=2.0)

    assert not worker.is_alive()
    assert 'error' not in outcome
    assert outcome['result']['captured_frame_count'] == 8

    annotated = node.get_eye_in_hand_annotated()
    assert annotated.startswith(b'\xff\xd8')
    assert overlay_calls == [True]
    assert node.latest_frame_calls == 1
