from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    config = str(Path(get_package_share_directory('dobot_vision_rgbd')) / 'config' / 'rgbd_vision.yaml')
    return LaunchDescription([
        DeclareLaunchArgument('camera_expected_fps', default_value='30.0'),
        DeclareLaunchArgument('camera_minimum_fps', default_value='20.0'),
        Node(
            package='dobot_vision_rgbd', executable='camera_health_node',
            name='camera_health', output='screen', respawn=True,
            respawn_delay=2.0,
            parameters=[{
                'expected_fps': ParameterValue(
                    LaunchConfiguration('camera_expected_fps'), value_type=float,
                ),
                'minimum_fps': ParameterValue(
                    LaunchConfiguration('camera_minimum_fps'), value_type=float,
                ),
            }],
        ),
        DeclareLaunchArgument('debug_enabled', default_value='false'),
        Node(
            package='dobot_vision_rgbd', executable='object_fusion_node',
            name='object_fusion_node', output='screen', parameters=[config, {
                'debug_enabled': ParameterValue(LaunchConfiguration('debug_enabled'), value_type=bool),
                'dry_run': True, 'allow_real_motion': False,
            }],
        ),
    ])
