from dobot_vision_yolo.eye_in_hand_transform import CameraIntrinsicsStore
from dobot_vision_yolo.eye_in_hand_transform import intrinsics_for_image_size


def test_intrinsics_scale_to_actual_capture_size():
    intrinsics = {
        "image_width": 640,
        "image_height": 480,
        "fx": 900.0,
        "fy": 900.0,
        "cx": 320.0,
        "cy": 240.0,
        "distortion_coefficients": [0.0] * 5,
    }

    scaled = intrinsics_for_image_size(intrinsics, (720, 1280, 3))

    assert scaled["image_width"] == 1280
    assert scaled["image_height"] == 720
    assert scaled["fx"] == 1800.0
    assert scaled["fy"] == 1350.0
    assert scaled["cx"] == 640.0
    assert scaled["cy"] == 360.0


def test_factory_intrinsics_can_be_persisted_for_all_vision_nodes(tmp_path):
    store = CameraIntrinsicsStore(str(tmp_path / "camera_intrinsics.yaml"))
    expected = {
        "image_width": 1280,
        "image_height": 720,
        "fx": 910.0,
        "fy": 912.0,
        "cx": 640.0,
        "cy": 360.0,
        "distortion_coefficients": [0.1, -0.2, 0.0, 0.0, 0.01],
    }

    store.save(expected)

    assert store.load() == expected
