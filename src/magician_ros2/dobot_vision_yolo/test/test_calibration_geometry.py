import cv2
import numpy as np

import dobot_vision_yolo.eye_in_hand_transform as eye_module
from dobot_vision_yolo.aruco_board import aruco_dictionary
from dobot_vision_yolo.aruco_board import board_geometry
from dobot_vision_yolo.aruco_board import default_aruco_board
from dobot_vision_yolo.aruco_board import detect_markers
from dobot_vision_yolo.aruco_board import marker_corners_board
from dobot_vision_yolo.aruco_board import rpy_matrix
from dobot_vision_yolo.aruco_board import transform_from_pose
from dobot_vision_yolo.camera_calibration_tool import auto_calibration_candidate
from dobot_vision_yolo.camera_calibration_tool import default_auto_calibration
from dobot_vision_yolo.camera_calibration_tool import transform_pixel
from dobot_vision_yolo.eye_in_hand_transform import aggregate_eye_in_hand_calibration
from dobot_vision_yolo.eye_in_hand_transform import calibrate_from_frame
from dobot_vision_yolo.eye_in_hand_transform import camera_matrix
from dobot_vision_yolo.eye_in_hand_transform import camera_optical_axis_base
from dobot_vision_yolo.eye_in_hand_transform import default_eye_in_hand_config
from dobot_vision_yolo.eye_in_hand_transform import distortion_coefficients
from dobot_vision_yolo.eye_in_hand_transform import make_transform
from dobot_vision_yolo.eye_in_hand_transform import normalize_tcp_pose
from dobot_vision_yolo.eye_in_hand_transform import rotation_error_deg
from dobot_vision_yolo.eye_in_hand_transform import transform_from_mount
from dobot_vision_yolo.eye_in_hand_transform import transform_from_tcp_pose


def _base_marker_centers(board):
    transform = transform_from_pose(board["pose_base"])
    return {
        marker_id: (
            transform
            @ np.array(
                [*board["markers"][str(marker_id)]["center_mm"], 1.0],
                dtype=np.float64,
            )
        )[:3]
        for marker_id in board["required_ids"]
    }


def _robot_to_pixel(points):
    points = np.asarray(points, dtype=np.float64)
    return np.column_stack(
        (
            4.0 * (points[:, 0] - 150.0) + 100.0,
            3.0 * (points[:, 1] + 110.0) + 50.0,
        )
    )


def _fixed_observations(invalid_indexes=()):
    config = default_auto_calibration()
    board = config["board"]
    t_base_board = transform_from_pose(board["pose_base"])
    observations = []
    for frame_index in range(config["sample_count"]):
        observation = {}
        for marker_id in board["required_ids"]:
            if frame_index in invalid_indexes and marker_id == 1:
                continue
            local = marker_corners_board(
                board["markers"][str(marker_id)],
                board["marker_length_mm"],
            )
            base = (
                t_base_board
                @ np.column_stack((local, np.ones(len(local)))).T
            ).T[:, :3]
            observation[marker_id] = _robot_to_pixel(base[:, :2])
        observations.append(observation)
    return observations


def _eye_sample(translation, rotation=(180.0, 0.0, 0.0)):
    return {
        "detected_ids": [0, 1, 2, 3],
        "missing_ids": [],
        "observation_valid": True,
        "reprojection_error_px": 0.25,
        "marker_cross_check_mean_mm": 0.4,
        "marker_cross_check_max_mm": 0.8,
        "measured_camera_mount": {
            "translation_mm": list(translation),
            "rotation_rpy_deg": list(rotation),
        },
    }


def test_dictionary_and_required_marker_ids_are_canonical():
    board = default_aruco_board()

    assert board["dictionary"] == "DICT_4X4_50"
    assert board["required_ids"] == [0, 1, 2, 3]

    dictionary = aruco_dictionary(cv2, board["dictionary"])
    canvas = np.full((520, 520), 255, dtype=np.uint8)
    for marker_id, (x, y) in enumerate(((40, 40), (280, 40), (280, 280), (40, 280))):
        if hasattr(cv2.aruco, "generateImageMarker"):
            marker = cv2.aruco.generateImageMarker(dictionary, marker_id, 180)
        else:
            marker = cv2.aruco.drawMarker(dictionary, marker_id, 180)
        canvas[y : y + 180, x : x + 180] = marker

    detection = detect_markers(cv2, canvas, board["dictionary"])

    assert sorted(detection["detected_ids"]) == [0, 1, 2, 3]


def test_board_corner_orientation_and_center_spans():
    board = default_aruco_board()
    marker_zero = marker_corners_board(
        board["markers"]["0"],
        board["marker_length_mm"],
    )

    assert np.allclose(
        marker_zero,
        [
            [-55.0, -65.0, 0.0],
            [-25.0, -65.0, 0.0],
            [-25.0, -95.0, 0.0],
            [-55.0, -95.0, 0.0],
        ],
    )
    geometry = board_geometry(board)
    assert geometry["width_mm"] == 80.0
    assert geometry["height_mm"] == 160.0
    assert geometry["id_layout"] == {
        "top_left": 3,
        "top_right": 2,
        "bottom_right": 1,
        "bottom_left": 0,
    }


def test_print_layout_detector_and_pnp_preserve_right_handed_board():
    """Exercise the physical print layout instead of self-projecting points.

    Pixel Y grows downward, so the printable board must place positive board Y
    toward the top.  With the board anchored in base and a camera looking down,
    the recovered camera mount is the hand-computable [0, 0, 45] mm / Rx(180).
    """
    board = default_aruco_board()
    dictionary = aruco_dictionary(cv2, board["dictionary"])
    pixels_per_mm = 4.0
    image_width = 520
    image_height = 840
    center_pixel = np.array([image_width / 2.0, image_height / 2.0])
    marker_size_px = int(round(board["marker_length_mm"] * pixels_per_mm))
    canvas = np.full((image_height, image_width), 255, dtype=np.uint8)
    for marker_id in board["required_ids"]:
        if hasattr(cv2.aruco, "generateImageMarker"):
            marker_image = cv2.aruco.generateImageMarker(
                dictionary,
                marker_id,
                marker_size_px,
            )
        else:
            marker_image = cv2.aruco.drawMarker(
                dictionary,
                marker_id,
                marker_size_px,
            )
        center_mm = np.asarray(
            board["markers"][str(marker_id)]["center_mm"][:2],
            dtype=np.float64,
        )
        pixel_center = center_pixel + np.array(
            [center_mm[0], -center_mm[1]],
            dtype=np.float64,
        ) * pixels_per_mm
        x = int(round(pixel_center[0] - marker_size_px / 2.0))
        y = int(round(pixel_center[1] - marker_size_px / 2.0))
        canvas[y : y + marker_size_px, x : x + marker_size_px] = marker_image

    intrinsics = {
        "image_width": image_width,
        "image_height": image_height,
        "fx": 600.0,
        "fy": 600.0,
        "cx": float(center_pixel[0]),
        "cy": float(center_pixel[1]),
        "distortion_coefficients": [0.0] * 5,
    }
    config = default_eye_in_hand_config()
    tcp_pose = [220.0, 0.0, 70.0, 0.0]

    result = calibrate_from_frame(
        cv2.cvtColor(canvas, cv2.COLOR_GRAY2BGR),
        tcp_pose,
        config,
        intrinsics,
    )
    recovered = make_transform(
        rpy_matrix(result["measured_camera_mount"]["rotation_rpy_deg"]),
        result["measured_camera_mount"]["translation_mm"],
    )
    expected = make_transform(rpy_matrix([180.0, 0.0, 0.0]), [0.0, 0.0, 45.0])

    assert sorted(result["detected_ids"]) == [0, 1, 2, 3]
    assert result["calibration_valid"] is True, result["warning"]
    assert np.linalg.norm(recovered[:3, 3] - expected[:3, 3]) < 2.0
    assert rotation_error_deg(recovered, expected) < 1.0
    assert result["look_down"]["ok"] is True


def test_board_local_coordinates_map_to_absolute_base_fixture():
    centers = _base_marker_centers(default_aruco_board())

    assert np.allclose(centers[0], [180.0, -80.0, -35.0])
    assert np.allclose(centers[1], [260.0, -80.0, -35.0])
    assert np.allclose(centers[2], [260.0, 80.0, -35.0])
    assert np.allclose(centers[3], [180.0, 80.0, -35.0])


def test_tcp_unit_conversion_is_explicit_and_unambiguous():
    assert normalize_tcp_pose([0.18, -0.08, 0.12, 15.0], xyz_unit="m") == [
        180.0,
        -80.0,
        120.0,
        15.0,
    ]
    assert normalize_tcp_pose([0.5, 1.0, -1.0, 15.0], xyz_unit="mm") == [
        0.5,
        1.0,
        -1.0,
        15.0,
    ]


def test_transform_inverse_rpy_and_camera_optical_axis():
    transform = make_transform(rpy_matrix([17.0, -8.0, 31.0]), [20.0, -15.0, 55.0])
    assert np.allclose(transform @ np.linalg.inv(transform), np.eye(4), atol=1e-10)
    assert np.allclose(
        camera_optical_axis_base(
            [220.0, 0.0, 120.0, 0.0],
            default_eye_in_hand_config(),
        ),
        [0.0, 0.0, -1.0],
        atol=1e-10,
    )


def test_t_base_tcp_times_t_tcp_camera_uses_column_vector_direction():
    t_base_tcp = transform_from_tcp_pose([200.0, 30.0, 100.0, 90.0])
    t_tcp_camera = make_transform(np.eye(3), [10.0, 0.0, 45.0])
    t_base_camera = t_base_tcp @ t_tcp_camera

    assert np.allclose(t_base_camera[:3, 3], [200.0, 40.0, 145.0])
    assert np.allclose(
        np.linalg.inv(t_base_tcp) @ t_base_camera,
        t_tcp_camera,
        atol=1e-10,
    )


def test_homography_is_serialized_row_major():
    matrix = np.array(
        [[2.0, 0.0, 10.0], [0.0, -3.0, 20.0], [0.0, 0.0, 1.0]],
        dtype=np.float64,
    )

    assert transform_pixel(matrix.reshape(-1).tolist(), [5.0, 4.0]) == [20.0, 8.0]


def test_missing_frames_are_rejected_and_eighty_percent_is_required():
    config = default_auto_calibration()
    accepted = auto_calibration_candidate(
        _fixed_observations(invalid_indexes={0, 1}),
        (720, 1280, 3),
        config,
    )
    rejected = auto_calibration_candidate(
        _fixed_observations(invalid_indexes={0, 1, 2}),
        (720, 1280, 3),
        config,
    )

    assert accepted["calibration_valid"] is True
    assert accepted["quality"]["valid_frame_count"] == 10
    assert accepted["quality"]["rejection_counts"]["missing_marker"] == 2
    assert accepted["estimated_marker_ids"] == []
    assert [row["id"] for row in accepted["marker_validation"]] == [0, 1, 2, 3]
    assert all(
        row["error_norm_mm"] < 1.0
        and max(abs(value) for value in row["delta_xyz_mm"]) < 1.0
        for row in accepted["marker_validation"]
    )
    assert rejected["calibration_valid"] is False
    assert rejected["quality"]["valid_frame_count"] == 9
    assert "need at least 10" in rejected["warning"]


def test_eye_in_hand_robust_estimator_rejects_two_outliers_and_keeps_eighty_percent():
    samples = [
        _eye_sample([0.1 * ((index % 3) - 1), 0.0, 45.0])
        for index in range(10)
    ]
    samples.extend(
        [
            _eye_sample([30.0, 0.0, 45.0], (150.0, 0.0, 0.0)),
            _eye_sample([-30.0, 0.0, 45.0], (210.0, 0.0, 0.0)),
        ]
    )

    result = aggregate_eye_in_hand_calibration(
        samples,
        default_eye_in_hand_config(),
        [220.0, 0.0, 120.0, 0.0],
    )

    assert result["calibration_valid"] is True, result["marker_validation"]
    assert result["quality"]["valid_sample_count"] == 10
    assert result["quality"]["valid_frame_ratio"] >= 0.8
    assert result["quality"]["robust_outlier_count"] == 2


def test_synthetic_eye_in_hand_solve_recovers_known_transform(monkeypatch):
    intrinsics = {
        "image_width": 1280,
        "image_height": 720,
        "fx": 900.0,
        "fy": 905.0,
        "cx": 640.0,
        "cy": 360.0,
        "distortion_coefficients": [0.0] * 5,
    }
    tcp_pose = [220.0, 0.0, 145.0, 12.0]
    expected_mount = {
        "translation_mm": [20.0, -15.0, 55.0],
        "rotation_rpy_deg": [178.0, 2.0, -4.0],
    }
    config = default_eye_in_hand_config()
    config["camera_mount"].update(expected_mount)
    board = config["aruco"]["board"]
    t_expected = transform_from_mount(config["camera_mount"])
    t_camera_board = (
        np.linalg.inv(transform_from_tcp_pose(tcp_pose) @ t_expected)
        @ transform_from_pose(board["pose_base"])
    )
    rvec, _ = cv2.Rodrigues(t_camera_board[:3, :3])
    corners = []
    for marker_id in board["required_ids"]:
        projected, _ = cv2.projectPoints(
            marker_corners_board(
                board["markers"][str(marker_id)],
                board["marker_length_mm"],
            ),
            rvec,
            t_camera_board[:3, 3].reshape(3, 1),
            camera_matrix(intrinsics),
            distortion_coefficients(intrinsics),
        )
        corners.append(projected.reshape(1, 4, 2))
    detection = {
        "ids": list(board["required_ids"]),
        "detected_ids": list(board["required_ids"]),
        "corners": corners,
        "rejected": [],
        "diagnostics": {
            "dictionary": board["dictionary"],
            "detected_ids": list(board["required_ids"]),
            "missing_ids": [],
            "rejected_marker_count": 0,
            "blur_laplacian_variance": 100.0,
            "image_resolution": {"width": 1280, "height": 720},
            "markers": [],
        },
    }
    monkeypatch.setattr(
        eye_module,
        "detect_aruco_markers",
        lambda _frame, _config: detection,
    )

    result = calibrate_from_frame(
        np.zeros((720, 1280, 3), dtype=np.uint8),
        tcp_pose,
        config,
        intrinsics,
    )
    recovered = make_transform(
        rpy_matrix(result["measured_camera_mount"]["rotation_rpy_deg"]),
        result["measured_camera_mount"]["translation_mm"],
    )
    translation_error = float(
        np.linalg.norm(recovered[:3, 3] - t_expected[:3, 3])
    )
    rotation_error = rotation_error_deg(recovered, t_expected)

    assert result["calibration_valid"] is True, result["marker_validation"][0].get(
        "warning"
    )
    assert translation_error < 2.0
    assert rotation_error < 1.0
    assert result["marker_cross_check_mean_mm"] <= 5.0
    assert result["marker_cross_check_max_mm"] <= 10.0
    assert result["transforms"]["T_base_camera"]["name"] == "T_base_camera_optical"
    assert result["transforms"]["T_tcp_camera"]["name"] == "T_tcp_camera_optical"
