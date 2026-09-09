"""View Orbbec data in its own frame, without assuming a robot extrinsic."""

from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = get_package_share_path('dobot_description') / 'rviz/camera.rviz'
    return LaunchDescription([
        DeclareLaunchArgument('rvizconfig', default_value=str(config)),
        DeclareLaunchArgument('fixed_frame', default_value='camera_link'),
        Node(package='rviz2', executable='rviz2', name='camera_rviz2',
             arguments=['-d', LaunchConfiguration('rvizconfig'),
                        '-f', LaunchConfiguration('fixed_frame')], output='screen'),
    ])
