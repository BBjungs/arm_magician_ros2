from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=get_package_share_directory('dobot_auto_center') + '/config'),
        Node(package='dobot_auto_center', executable='auto_center', output='screen',
             arguments=['--config', LaunchConfiguration('config')]),
    ])
