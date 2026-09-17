from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    host_arg = DeclareLaunchArgument(
        'host',
        default_value='127.0.0.1',
        description='HTTP bind host.',
    )
    port_arg = DeclareLaunchArgument(
        'port',
        default_value='8080',
        description='HTTP bind port.',
    )
    raw_topic_arg = DeclareLaunchArgument(
        'camera_raw_topic',
        default_value='/camera/color/image_raw',
        description='Raw sensor_msgs/Image camera topic.',
    )
    compressed_topic_arg = DeclareLaunchArgument(
        'camera_compressed_topic',
        default_value='/camera/color/image_raw/compressed',
        description='Compressed sensor_msgs/CompressedImage camera topic.',
    )
    preview_arg = DeclareLaunchArgument(
        'enable_camera_preview', default_value='true', choices=['true', 'false'],
        description='Subscribe to and retain camera frames for the web preview.',
    )
    camera_info_topic_arg = DeclareLaunchArgument(
        'camera_info_topic',
        default_value='/camera/color/camera_info',
        description='Factory-calibrated sensor_msgs/CameraInfo topic.',
    )
    camera_device_arg = DeclareLaunchArgument(
        'camera_device',
        default_value='',
        description='Direct V4L2 fallback. Empty by default for Orbbec ROS topics.',
    )
    camera_width_arg = DeclareLaunchArgument(
        'camera_width',
        default_value='1280',
        description='Direct camera capture width.',
    )
    camera_height_arg = DeclareLaunchArgument(
        'camera_height',
        default_value='720',
        description='Direct camera capture height.',
    )
    camera_fps_arg = DeclareLaunchArgument(
        'camera_fps',
        default_value='15.0',
        description='Direct camera capture frame rate.',
    )
    fps_arg = DeclareLaunchArgument(
        'stream_fps',
        default_value='12.0',
        description='MJPEG stream frame rate.',
    )
    vision_mode_arg = DeclareLaunchArgument(
        'vision_mode',
        default_value='fixed_camera',
        choices=['fixed_camera', 'eye_in_hand'],
        description='Default vision mode for web safety checks.',
    )
    tcp_pose_topic_arg = DeclareLaunchArgument(
        'tcp_pose_topic',
        default_value='dobot_pose_raw',
        description='Float64MultiArray TCP pose topic [x, y, z, r] in m/m/m/deg.',
    )
    fallback_tcp_pose_topic_arg = DeclareLaunchArgument(
        'fallback_tcp_pose_topic',
        default_value='',
        description='Optional fallback Float64MultiArray TCP pose topic.',
    )

    web_node = Node(
        package='dobot_web_interface',
        executable='web_interface',
        output='screen',
        parameters=[
            {
                'host': LaunchConfiguration('host'),
                'port': LaunchConfiguration('port'),
                'camera_raw_topic': LaunchConfiguration('camera_raw_topic'),
                'camera_compressed_topic': LaunchConfiguration(
                    'camera_compressed_topic'
                ),
                'enable_camera_preview': LaunchConfiguration('enable_camera_preview'),
                'camera_info_topic': LaunchConfiguration('camera_info_topic'),
                'camera_device': LaunchConfiguration('camera_device'),
                'camera_width': LaunchConfiguration('camera_width'),
                'camera_height': LaunchConfiguration('camera_height'),
                'camera_fps': LaunchConfiguration('camera_fps'),
                'stream_fps': LaunchConfiguration('stream_fps'),
                'vision_mode': LaunchConfiguration('vision_mode'),
                'tcp_pose_topic': LaunchConfiguration('tcp_pose_topic'),
                'fallback_tcp_pose_topic': LaunchConfiguration(
                    'fallback_tcp_pose_topic'
                ),
            }
        ],
    )

    return LaunchDescription(
        [
            host_arg,
            port_arg,
            raw_topic_arg,
            compressed_topic_arg,
            preview_arg,
            camera_info_topic_arg,
            camera_device_arg,
            camera_width_arg,
            camera_height_arg,
            camera_fps_arg,
            fps_arg,
            vision_mode_arg,
            tcp_pose_topic_arg,
            fallback_tcp_pose_topic_arg,
            web_node,
        ]
    )
