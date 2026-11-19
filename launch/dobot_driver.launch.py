from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    default_config = PathJoinSubstitution(
        [FindPackageShare("dobot_driver"), "config", "dobot.yaml"]
    )
    return LaunchDescription([
        DeclareLaunchArgument("params_file", default_value=default_config),
        Node(
            package="dobot_driver",
            executable="dobot_readback",
            parameters=[LaunchConfiguration("params_file")],
            output="screen",
        ),
    ])
