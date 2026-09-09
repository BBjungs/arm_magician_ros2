from pathlib import Path
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share = Path(get_package_share_directory('dobot_object_vision'))
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=str(share / 'config/vision.yaml')),
        Node(package='dobot_object_vision', executable='circle_targets', output='screen',
             parameters=[LaunchConfiguration('config')]),
    ])
