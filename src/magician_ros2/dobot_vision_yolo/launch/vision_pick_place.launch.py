from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = Path(get_package_share_directory("dobot_vision_yolo"))
    config_dir = package_share / "config"

    dry_run = LaunchConfiguration("dry_run")
    source_type = LaunchConfiguration("source_type")
    http_snapshot_url = LaunchConfiguration("http_snapshot_url")
    camera_device = LaunchConfiguration("camera_device")
    vision_mode = LaunchConfiguration("vision_mode")
    tcp_pose_topic = LaunchConfiguration("tcp_pose_topic")
    fallback_tcp_pose_topic = LaunchConfiguration("fallback_tcp_pose_topic")
    calibration_bundle_path = LaunchConfiguration("calibration_bundle_path")

    yolo_config = str(config_dir / "yolo.yaml")
    workspace_config = str(config_dir / "workspace.yaml")
    place_config = str(config_dir / "place_positions.yaml")

    detector_params = {
        "dry_run": ParameterValue(dry_run, value_type=bool),
        "source_type": ParameterValue(source_type, value_type=str),
        "http_snapshot_url": ParameterValue(http_snapshot_url, value_type=str),
        "camera_device": ParameterValue(camera_device, value_type=str),
    }
    common_params = {
        "dry_run": ParameterValue(dry_run, value_type=bool),
    }
    transform_params = {
        "dry_run": ParameterValue(dry_run, value_type=bool),
        "vision_mode": ParameterValue(vision_mode, value_type=str),
        "calibration_bundle_path": ParameterValue(calibration_bundle_path, value_type=str),
        "calibration_status_topic": "/calibration/status",
        "tcp_pose_topic": ParameterValue(tcp_pose_topic, value_type=str),
        "fallback_tcp_pose_topic": ParameterValue(
            fallback_tcp_pose_topic,
            value_type=str,
        ),
    }
    target_selector_params = dict(transform_params)
    target_selector_params["place_positions_path"] = place_config
    safety_params = {
        "dry_run": ParameterValue(dry_run, value_type=bool),
        "workspace_config_path": workspace_config,
    }

    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "dry_run",
                default_value="true",
                description="Keep all vision pick-and-place nodes in dry-run mode.",
            ),
            DeclareLaunchArgument(
                "vision_mode",
                default_value="eye_in_hand",
                choices=["fixed_camera", "eye_in_hand"],
                description="Camera mounting topology only; calibration is always markerless.",
            ),
            DeclareLaunchArgument(
                "source_type",
                default_value="http_snapshot",
                description="Detector source: http_snapshot for web dry-run, camera for direct V4L2.",
            ),
            DeclareLaunchArgument(
                "http_snapshot_url",
                default_value="http://127.0.0.1:8080/api/snapshot",
                description="Snapshot URL used when source_type is http_snapshot.",
            ),
            DeclareLaunchArgument(
                "camera_device",
                default_value="/dev/video0",
                description="Camera device used when source_type is camera.",
            ),
            DeclareLaunchArgument(
                "tcp_pose_topic",
                default_value="dobot_pose_raw",
                description="Float64MultiArray TCP pose topic [x, y, z, r] in m/m/m/deg.",
            ),
            DeclareLaunchArgument(
                "fallback_tcp_pose_topic",
                default_value="",
                description="Optional fallback Float64MultiArray TCP pose topic.",
            ),
            DeclareLaunchArgument(
                "calibration_bundle_path",
                default_value="~/.ros/dobot/markerless_calibration.npz",
                description="Verified bundle owned by dobot_calibration.",
            ),
            Node(
                package="dobot_vision_yolo",
                executable="yolo_detector_node",
                name="yolo_detector_node",
                output="screen",
                emulate_tty=True,
                parameters=[yolo_config, detector_params],
            ),
            Node(
                package="dobot_vision_yolo",
                executable="target_selector_node",
                name="target_selector_node",
                output="screen",
                emulate_tty=True,
                parameters=[yolo_config, target_selector_params],
            ),
            Node(
                package="dobot_vision_yolo",
                executable="pixel_to_robot_node",
                name="pixel_to_robot_node",
                output="screen",
                emulate_tty=True,
                parameters=[transform_params],
            ),
            Node(
                package="dobot_vision_yolo",
                executable="vision_pick_place_node",
                name="vision_pick_place_node",
                output="screen",
                emulate_tty=True,
                parameters=[common_params],
            ),
            Node(
                package="dobot_vision_yolo",
                executable="safety_guard_node",
                name="safety_guard_node",
                output="screen",
                emulate_tty=True,
                parameters=[safety_params],
            ),
        ]
    )
