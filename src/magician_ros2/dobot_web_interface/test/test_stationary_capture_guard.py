import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dobot_web_interface.web_interface import DobotWebNode


@pytest.mark.parametrize('fault', ['timing', 'movement', 'resolution', 'frame',
                                  'intrinsics_changed', 'end_pose', 'active_goal'])
def test_invalid_capture_never_reaches_calibration_save(fault):
    start = [220., 0., 70., 0.]
    end = list(start)
    intrinsics = {'image_width': 8, 'image_height': 8, 'frame_id': 'optical', 'fx': 20.}
    records = [dict(tcp_pose_mm_deg=list(start), frame_to_tcp_receive_delta_ms=10.,
                    frame_id='optical') for _ in range(8)]
    if fault == 'timing':
        records[3]['frame_to_tcp_receive_delta_ms'] = 501
    elif fault == 'movement':
        records[3]['tcp_pose_mm_deg'][0] += 2
    elif fault == 'resolution':
        intrinsics['image_width'] = 16
    elif fault == 'frame':
        records[3]['frame_id'] = 'other_camera'
    elif fault == 'end_pose':
        end[0] += 1
    elif fault == 'active_goal':
        records[3]['motion_active'] = True
    ending_intrinsics = dict(intrinsics)
    if fault == 'intrinsics_changed':
        ending_intrinsics['fx'] += 1
    preflights = iter([(start, intrinsics), (end, ending_intrinsics)])
    saves = []
    store = SimpleNamespace(load=lambda: {'aruco': {}},
                            auto_calibrate_from_frames=lambda *a: saves.append(a))
    node = SimpleNamespace(
        _stationary_calibration_preflight=lambda: next(preflights),
        _eye_in_hand=lambda: store,
        _capture_fresh_frames=lambda *a: [np.zeros((8, 8, 3), np.uint8)] * 8,
        _last_calibration_capture_metadata={'frames': records},
        _intrinsics=lambda: SimpleNamespace(save=saves.append),
    )
    with pytest.raises(ValueError):
        DobotWebNode._perform_auto_calibration(node, 'eye_in_hand')
    assert saves == []


def test_capture_does_not_reuse_the_pre_request_cached_image():
    _, old_image = cv2.imencode('.jpg', np.zeros((8, 8, 3), np.uint8))
    _, fresh_image = cv2.imencode('.jpg', np.full((8, 8, 3), 220, np.uint8))
    node = SimpleNamespace(
        _frame_condition=threading.Condition(), _goal_lock=threading.Lock(),
        _frame_sequence=1, _latest_jpeg=old_image.tobytes(),
        _latest_frame_source='rgb', _latest_frame_time=time.monotonic(),
        _latest_frame_stamp_sec=1., _latest_frame_id='optical',
        _latest_tcp_pose=[220., 0., 70., 0.], _latest_tcp_pose_time=time.monotonic(),
        _latest_tcp_pose_source='test', _active_goal_handle=None,
    )
    stop = threading.Event()

    def publish():
        while not stop.wait(0.04):
            with node._frame_condition:
                node._latest_jpeg = fresh_image.tobytes()
                node._frame_sequence += 1
                node._latest_frame_time = time.monotonic()
                with node._goal_lock:
                    node._latest_tcp_pose_time = time.monotonic()
                node._frame_condition.notify_all()

    worker = threading.Thread(target=publish)
    worker.start()
    try:
        frames = DobotWebNode._capture_fresh_frames(node, 8, 3)
    finally:
        stop.set()
        worker.join(timeout=1)
    assert len(frames) == 8
    assert all(frame.mean() > 200 for frame in frames)
    assert all(r['sequence'] > 1 for r in node._last_calibration_capture_metadata['frames'])
