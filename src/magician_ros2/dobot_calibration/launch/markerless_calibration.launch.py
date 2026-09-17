from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = Path(get_package_share_directory('dobot_calibration'))
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=str(share / 'config/calibration.yaml')),
        DeclareLaunchArgument('mount_model', default_value=str(share / 'config/mount_model.yaml')),
        DeclareLaunchArgument('camera_id', default_value=''),
        DeclareLaunchArgument('carrier_frame', default_value=''),
        DeclareLaunchArgument('auto_start', default_value='false'),
        DeclareLaunchArgument('recalibrate_on_failure', default_value='false'),
        DeclareLaunchArgument('calibration_file', default_value='~/.ros/dobot/markerless_calibration.npz'),
        Node(package='dobot_calibration', executable='markerless_calibration', output='screen',
             parameters=[LaunchConfiguration('config'), {
                 'mount_model': LaunchConfiguration('mount_model'),
                 'camera_id': ParameterValue(LaunchConfiguration('camera_id'), value_type=str),
                 'carrier_frame': ParameterValue(LaunchConfiguration('carrier_frame'), value_type=str),
                 'auto_start': ParameterValue(LaunchConfiguration('auto_start'), value_type=bool),
                 'recalibrate_on_failure': ParameterValue(
                     LaunchConfiguration('recalibrate_on_failure'), value_type=bool,
                 ),
                 'calibration_file': LaunchConfiguration('calibration_file'),
             }]),
    ])
