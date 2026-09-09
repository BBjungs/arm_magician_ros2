import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    config = os.path.join(
        get_package_share_directory('dobot_motion'),
        'config',
        'PTP_motion_params.yaml'
        )

    return LaunchDescription([
        Node(
            package='dobot_motion',
            executable='PTP_server',
            output='screen',
            parameters=[config],
        ),
    ])
