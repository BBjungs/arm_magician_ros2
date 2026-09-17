from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from dobot_calibration.camera_launch import camera_parameter_overrides


def generate_launch_description():
    share = Path(get_package_share_directory('dobot_calibration'))
    def make_node(context):
        # ``auto`` (and the legacy empty value) deliberately omit the overlay:
        # this preserves a non-empty camera_id from the YAML parameter file.
        requested = LaunchConfiguration('camera_id').perform(context).strip()
        overrides = {
            'mount_model': LaunchConfiguration('mount_model'),
            'carrier_frame': ParameterValue(LaunchConfiguration('carrier_frame'), value_type=str),
            'auto_start': ParameterValue(LaunchConfiguration('auto_start'), value_type=bool),
            'recalibrate_on_failure': ParameterValue(
                LaunchConfiguration('recalibrate_on_failure'), value_type=bool),
            'calibration_file': LaunchConfiguration('calibration_file'),
        }
        overrides.update(camera_parameter_overrides(requested))
        return [Node(package='dobot_calibration', executable='markerless_calibration', output='screen',
                     parameters=[LaunchConfiguration('config'), overrides])]
    return LaunchDescription([
        DeclareLaunchArgument('config', default_value=str(share / 'config/calibration.yaml')),
        DeclareLaunchArgument('mount_model', default_value=str(share / 'config/mount_model.yaml')),
        DeclareLaunchArgument('camera_id', default_value='auto'),
        DeclareLaunchArgument('carrier_frame', default_value=''),
        DeclareLaunchArgument('auto_start', default_value='false'),
        DeclareLaunchArgument('recalibrate_on_failure', default_value='false'),
        DeclareLaunchArgument('calibration_file', default_value='~/.ros/dobot/markerless_calibration.npz'),
        OpaqueFunction(function=make_node),
    ])
