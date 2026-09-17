from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.actions import OpaqueFunction
from launch.actions import SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch.substitutions import PathJoinSubstitution
from launch_ros.actions import Node


def _truthy(value):
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _maybe_start_bringup(context, *args, **kwargs):
    if not _truthy(LaunchConfiguration('start_bringup').perform(context)):
        return []
    bringup_launch = PathJoinSubstitution(
        [
            get_package_share_directory('dobot_bringup'),
            'launch',
            'dobot_magician_control_system.launch.py',
        ]
    )
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(bringup_launch),
        )
    ]


def _maybe_start_camera(context, *args, **kwargs):
    if not _truthy(LaunchConfiguration('start_camera').perform(context)):
        return []
    camera_launch = PathJoinSubstitution(
        [
            get_package_share_directory('orbbec_camera'),
            'launch',
            'ob_camera.launch.py',
        ]
    )
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(camera_launch),
            launch_arguments={
                'camera_name': LaunchConfiguration('orbbec_camera_name'),
                'serial_number': LaunchConfiguration('orbbec_serial_number'),
                'depth_registration': LaunchConfiguration(
                    'orbbec_depth_registration'
                ),
                'enable_color': 'true',
                'color_width': '640',
                'color_height': '480',
                'color_fps': '30',
                'color_format': 'MJPG',
                'enable_depth': 'true',
                'depth_width': '640',
                'depth_height': '400',
                'depth_fps': '30',
                'depth_format': 'Y11',
                'enable_ir': 'false',
                'enable_ldp': 'false',
                'enable_point_cloud': LaunchConfiguration('enable_point_cloud'),
                'enable_colored_point_cloud': LaunchConfiguration('enable_colored_point_cloud'),
            }.items(),
        )
    ]


def _maybe_start_rviz(context, *args, **kwargs):
    if not _truthy(LaunchConfiguration('start_rviz').perform(context)):
        return []
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(PathJoinSubstitution([
            get_package_share_directory('dobot_description'), 'launch', 'display.launch.py'])),
        launch_arguments={'tool': LaunchConfiguration('tool'), 'gui': 'false'}.items(),
    )]


def _maybe_start_vision(context, *args, **kwargs):
    if not _truthy(LaunchConfiguration('start_vision').perform(context)):
        return []
    engine = LaunchConfiguration('vision_engine').perform(context)
    if engine in ('rgbd_shape', 'hybrid'):
        vision_launch = PathJoinSubstitution([
            get_package_share_directory('dobot_vision_rgbd'), 'launch',
            'rgbd_vision.launch.py'])
        return [IncludeLaunchDescription(
            PythonLaunchDescriptionSource(vision_launch),
            launch_arguments={
                'camera_expected_fps': LaunchConfiguration('camera_fps'),
                'camera_minimum_fps': LaunchConfiguration('camera_minimum_fps'),
                'camera_freshness_timeout_s': '1.5',
                'start_object_fusion': LaunchConfiguration('start_object_fusion'),
                'enable_cloud_health_validation': LaunchConfiguration('enable_cloud_health_validation'),
            }.items(),
        )]
    vision_launch = PathJoinSubstitution([
        get_package_share_directory('dobot_vision_yolo'), 'launch',
        'vision_pick_place.launch.py'])
    port = LaunchConfiguration('port').perform(context)
    return [
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(vision_launch),
            launch_arguments={
                'dry_run': 'true',
                'source_type': 'http_snapshot',
                'http_snapshot_url': f'http://127.0.0.1:{port}/api/snapshot',
                'camera_device': LaunchConfiguration('camera_device'),
                'vision_mode': LaunchConfiguration('vision_mode'),
                'calibration_bundle_path': LaunchConfiguration('calibration_file'),
                'tcp_pose_topic': LaunchConfiguration('tcp_pose_topic'),
                'fallback_tcp_pose_topic': LaunchConfiguration(
                    'fallback_tcp_pose_topic'
                ),
            }.items(),
        )
    ]


def _maybe_start_calibration(context, *args, **kwargs):
    """Launch the live calibration verifier before the web startup gate uses it.

    The node itself remains idle until the integration state machine requests a
    verification.  Starting the process here therefore establishes a stable
    dependency without issuing unprompted robot motion.
    """
    if not _truthy(LaunchConfiguration('start_calibration').perform(context)):
        return []
    calibration_launch = PathJoinSubstitution([
        get_package_share_directory('dobot_calibration'), 'launch',
        'markerless_calibration.launch.py'])
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(calibration_launch),
        launch_arguments={
            'camera_id': LaunchConfiguration('calibration_camera_id'),
            'calibration_file': LaunchConfiguration('calibration_file'),
            'carrier_frame': LaunchConfiguration('calibration_carrier_frame'),
            'mount_model': LaunchConfiguration('calibration_mount_model'),
            'auto_start': 'false',
            'recalibrate_on_failure': LaunchConfiguration(
                'startup_auto_recalibrate'
            ),
        }.items(),
    )]


def generate_launch_description():
    tool_arg = DeclareLaunchArgument(
        'tool',
        default_value='extended_gripper',
        choices=['none', 'pen', 'suction_cup', 'gripper', 'extended_gripper'],
        description='Dobot end effector configuration.',
    )
    host_arg = DeclareLaunchArgument('host', default_value='127.0.0.1')
    port_arg = DeclareLaunchArgument('port', default_value='8080')
    camera_device_arg = DeclareLaunchArgument(
        'camera_device',
        default_value='',
        description='Direct V4L2 fallback. Empty when using Orbbec ROS topics.',
    )
    camera_raw_topic_arg = DeclareLaunchArgument(
        'camera_raw_topic',
        default_value='/camera/color/image_raw',
    )
    camera_compressed_topic_arg = DeclareLaunchArgument(
        'camera_compressed_topic',
        default_value='/camera/color/image_raw/compressed',
        description='Native MJPG topic; empty falls back to throttled raw RGB.',
    )
    enable_camera_preview_arg = DeclareLaunchArgument(
        'enable_camera_preview', default_value='true', choices=['true', 'false'],
        description='Subscribe to and retain camera frames for the web preview.',
    )
    camera_info_topic_arg = DeclareLaunchArgument(
        'camera_info_topic',
        default_value='/camera/color/camera_info',
    )
    camera_width_arg = DeclareLaunchArgument('camera_width', default_value='640')
    camera_height_arg = DeclareLaunchArgument('camera_height', default_value='480')
    camera_fps_arg = DeclareLaunchArgument('camera_fps', default_value='30.0')
    camera_minimum_fps_arg = DeclareLaunchArgument(
        'camera_minimum_fps', default_value='20.0',
        description='Minimum usable received RGB-D rate; lower rates fail readiness.',
    )
    stream_fps_arg = DeclareLaunchArgument('stream_fps', default_value='12.0')
    vision_mode_arg = DeclareLaunchArgument(
        'vision_mode',
        default_value='eye_in_hand',
        choices=['fixed_camera', 'eye_in_hand'],
        description='Camera mounting topology only; calibration is always markerless.',
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
    start_bringup_arg = DeclareLaunchArgument(
        'start_bringup',
        default_value='false',
        description='Start Dobot hardware bringup. Keep false for dry-run web tests.',
    )
    start_camera_arg = DeclareLaunchArgument(
        'start_camera',
        default_value='true',
        description='Start the Orbbec Gemini driver.',
    )
    orbbec_camera_name_arg = DeclareLaunchArgument(
        'orbbec_camera_name',
        default_value='camera',
        description='Orbbec namespace; camera publishes below /<name>/.',
    )
    orbbec_serial_number_arg = DeclareLaunchArgument(
        'orbbec_serial_number',
        default_value='',
        description='Optional Orbbec serial number when more than one camera is connected.',
    )
    orbbec_depth_registration_arg = DeclareLaunchArgument(
        'orbbec_depth_registration',
        default_value='true',
        description='Align depth pixels to the color image.',
    )
    start_vision_arg = DeclareLaunchArgument(
        'start_vision',
        default_value='true',
        description='Start the selected dry-run vision pipeline.',
    )
    start_object_fusion_arg = DeclareLaunchArgument(
        'start_object_fusion', default_value='false', choices=['true', 'false'],
        description='Start optional RGB-D object fusion after passive readiness.',
    )
    vision_engine_arg = DeclareLaunchArgument(
        'vision_engine', default_value='rgbd_shape',
        choices=['rgbd_shape', 'yolo', 'hybrid'],
        description='Primary detector; hybrid currently uses RGB-D only.',
    )
    tool_mapping_arg = DeclareLaunchArgument(
        'tool_mapping', default_value='canonical',
        choices=['canonical'],
        description='Keep web gripper and suction controls on separate services.',
    )
    vision_annotated_path_arg = DeclareLaunchArgument(
        'vision_annotated_path', default_value='/tmp/dobot_rgbd_annotated.jpg')
    start_calibration_arg = DeclareLaunchArgument(
        'start_calibration', default_value='true',
        description='Start the live calibration verification node (idle until requested).',
    )
    calibration_camera_id_arg = DeclareLaunchArgument(
        # Calibration resolves the active Orbbec driver's serial through
        # get_device_info.  Do not turn the camera driver's optional selection
        # argument into an unconditional calibration override.
        'calibration_camera_id', default_value='auto',
        description='Immutable camera serial/device identity for live calibration.',
    )
    calibration_file_arg = DeclareLaunchArgument(
        'calibration_file', default_value='~/.ros/dobot/markerless_calibration.npz',
    )
    calibration_carrier_frame_arg = DeclareLaunchArgument(
        'calibration_carrier_frame', default_value='',
        description='Verified camera bracket TF frame; empty selects legacy TCP mode.',
    )
    calibration_mount_model_arg = DeclareLaunchArgument(
        'calibration_mount_model', default_value=PathJoinSubstitution([
            get_package_share_directory('dobot_calibration'), 'config', 'mount_model.yaml',
        ]),
        description='Measured mount YAML matching the selected calibration parent.',
    )
    require_integrated_startup_arg = DeclareLaunchArgument(
        'require_integrated_startup', default_value='true',
        choices=['true', 'false'],
        description='Require live robot/camera/vision/calibration/HOME readiness for picks.',
    )
    startup_auto_arg = DeclareLaunchArgument(
        'startup_auto', default_value='false', choices=['true', 'false'],
        description='Automatically request calibration verification once prerequisites are ready.',
    )
    startup_auto_recalibrate_arg = DeclareLaunchArgument(
        'startup_auto_recalibrate', default_value='false',
        choices=['true', 'false'],
        description=(
            'Permit one calibration attempt after failed load/verification; '
            'the calibration hardware safety gates still control all motion.'
        ),
    )
    startup_auto_motion_arg = DeclareLaunchArgument(
        'startup_auto_motion', default_value='false', choices=['true', 'false'],
        description='Allow startup_auto to issue HOME and observation-pose motion.',
    )
    observation_pose_arg = DeclareLaunchArgument(
        'observation_pose_mm', default_value='[220.0, 0.0, 80.0, 0.0]',
        description='Safe [x,y,z,r] millimetre pose used to observe the work area.',
    )

    web_node = Node(
        package='dobot_web_interface',
        executable='web_interface',
        output='screen',
        parameters=[
            {
                'host': LaunchConfiguration('host'),
                'port': LaunchConfiguration('port'),
                'camera_device': LaunchConfiguration('camera_device'),
                'camera_raw_topic': LaunchConfiguration('camera_raw_topic'),
                'camera_compressed_topic': LaunchConfiguration(
                    'camera_compressed_topic'
                ),
                'enable_camera_preview': LaunchConfiguration('enable_camera_preview'),
                'camera_info_topic': LaunchConfiguration('camera_info_topic'),
                'camera_width': LaunchConfiguration('camera_width'),
                'camera_height': LaunchConfiguration('camera_height'),
                'camera_fps': LaunchConfiguration('camera_fps'),
                'stream_fps': LaunchConfiguration('stream_fps'),
                'vision_mode': LaunchConfiguration('vision_mode'),
                'vision_engine': LaunchConfiguration('vision_engine'),
                'tool_mapping': LaunchConfiguration('tool_mapping'),
                'vision_annotated_path': LaunchConfiguration('vision_annotated_path'),
                'tcp_pose_topic': LaunchConfiguration('tcp_pose_topic'),
                'fallback_tcp_pose_topic': LaunchConfiguration(
                    'fallback_tcp_pose_topic'
                ),
                'require_integrated_startup': LaunchConfiguration(
                    'require_integrated_startup'
                ),
                'startup_auto': LaunchConfiguration('startup_auto'),
                'startup_auto_motion': LaunchConfiguration('startup_auto_motion'),
                'observation_pose_mm': LaunchConfiguration('observation_pose_mm'),
                'calibration_bundle_path': LaunchConfiguration('calibration_file'),
            }
        ],
    )

    return LaunchDescription(
        [
            tool_arg,
            host_arg,
            port_arg,
            camera_device_arg,
            camera_raw_topic_arg,
            camera_compressed_topic_arg,
            enable_camera_preview_arg,
            camera_info_topic_arg,
            camera_width_arg,
            camera_height_arg,
            camera_fps_arg,
            camera_minimum_fps_arg,
            stream_fps_arg,
            vision_mode_arg,
            tcp_pose_topic_arg,
            fallback_tcp_pose_topic_arg,
            start_bringup_arg,
            start_camera_arg,
            DeclareLaunchArgument('start_rviz', default_value='false',
                                  choices=['true', 'false']),
            DeclareLaunchArgument('enable_point_cloud', default_value='true',
                                  choices=['true', 'false']),
            DeclareLaunchArgument('enable_colored_point_cloud', default_value='false',
                                  choices=['true', 'false']),
            DeclareLaunchArgument('enable_cloud_health_validation', default_value='false',
                                  choices=['true', 'false']),
            orbbec_camera_name_arg,
            orbbec_serial_number_arg,
            orbbec_depth_registration_arg,
            start_vision_arg,
            start_object_fusion_arg,
            vision_engine_arg,
            tool_mapping_arg,
            vision_annotated_path_arg,
            start_calibration_arg,
            calibration_camera_id_arg,
            calibration_file_arg,
            calibration_carrier_frame_arg,
            calibration_mount_model_arg,
            require_integrated_startup_arg,
            startup_auto_arg,
            startup_auto_recalibrate_arg,
            startup_auto_motion_arg,
            observation_pose_arg,
            SetEnvironmentVariable('MAGICIAN_TOOL', LaunchConfiguration('tool')),
            OpaqueFunction(function=_maybe_start_bringup),
            OpaqueFunction(function=_maybe_start_camera),
            OpaqueFunction(function=_maybe_start_rviz),
            OpaqueFunction(function=_maybe_start_calibration),
            web_node,
            OpaqueFunction(function=_maybe_start_vision),
        ]
    )
