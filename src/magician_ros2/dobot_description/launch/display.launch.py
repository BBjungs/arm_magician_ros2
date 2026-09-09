"""Display the upstream full Magician model using measured joint states."""

from ament_index_python.packages import get_package_share_path
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import EnvironmentVariable, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
import math
from pathlib import Path

import xacro
import yaml


def _mount_mappings(config_path):
    config = yaml.safe_load(Path(config_path).read_text())
    if not isinstance(config, dict) or config.get('geometry_verified') is not True:
        raise ValueError('Eye-in-hand mount geometry is not verified')
    if config.get('rigid_to_rotating_tool') is not True:
        raise ValueError('Confirm the camera is rigidly attached to the rotating tool')
    if config.get('translation_units') != 'm' or config.get('rotation_units') != 'rad':
        raise ValueError('Mount geometry requires metres and radians')
    if not isinstance(config.get('measurement_source'), str) or not config['measurement_source'].strip():
        raise ValueError('Mount geometry requires a measurement source')
    mappings = {'enable_orbbec_mount': 'true'}
    for frame, prefix in [('camera_link', 'orbbec_mount'), ('suction_tcp', 'suction_tcp')]:
        frame_config = config.get(frame)
        if not isinstance(frame_config, dict):
            raise ValueError(f'Missing {frame} geometry')
        for key, limit in [('xyz', 0.5), ('rpy', 2 * math.pi)]:
            values = frame_config.get(key)
            if (not isinstance(values, list) or len(values) != 3
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) or abs(v) > limit for v in values)):
                raise ValueError(f'{frame}.{key} requires three finite values in declared units')
            mappings[prefix + '_' + key] = ' '.join(str(v) for v in values)
    return mappings


def _display(context):
    tool = LaunchConfiguration('tool').perform(context)
    dof = LaunchConfiguration('DOF').perform(context)
    if dof == 'auto':
        dof = '3' if tool in ('none', 'pen') else '4'
    camera = LaunchConfiguration('use_camera').perform(context)
    if ((dof == '3' and (tool not in ('none', 'pen') or camera == 'true'))
            or (dof == '4' and tool in ('none', 'pen'))):
        raise ValueError('URDF requires DOF=3 for none/pen (no RealSense), '
                         'or DOF=4 for gripper/extended_gripper/suction_cup.')
    mappings = {'DOF': dof, 'tool': tool, 'use_camera': camera}
    mount_config = context.launch_configurations.get('eye_in_hand_config', '')
    if mount_config:
        if tool != 'suction_cup' or camera == 'true':
            raise ValueError('Orbbec mount requires suction_cup with legacy camera disabled')
        mappings.update(_mount_mappings(mount_config))
    description = xacro.process_file(
        LaunchConfiguration('model').perform(context), mappings=mappings,
    ).toxml()
    return [
        Node(
            package='robot_state_publisher', executable='robot_state_publisher',
            name='robot_state_publisher', output='screen',
            parameters=[{'robot_description': ParameterValue(description, value_type=str)}],
            remappings=[('joint_states', LaunchConfiguration('joint_states_topic'))],
            condition=IfCondition(LaunchConfiguration('publish_robot_description')),
        ),
        Node(
            package='joint_state_publisher_gui', executable='joint_state_publisher_gui',
            remappings=[('joint_states', LaunchConfiguration('joint_states_topic'))],
            condition=IfCondition(LaunchConfiguration('gui')),
        ),
        Node(
            package='rviz2', executable='rviz2', name='rviz2', output='screen',
            arguments=['-d', LaunchConfiguration('rvizconfig')],
            condition=IfCondition(LaunchConfiguration('rviz')),
        ),
    ]


def generate_launch_description():
    share = get_package_share_path('dobot_description')
    return LaunchDescription([
        DeclareLaunchArgument('model', default_value=str(
            share / 'model/magician_standalone.urdf.xacro')),
        DeclareLaunchArgument('rvizconfig', default_value=str(share / 'rviz/urdf_full.rviz')),
        DeclareLaunchArgument('tool', default_value=EnvironmentVariable(
            'MAGICIAN_TOOL', default_value='suction_cup'),
            choices=['none', 'pen', 'suction_cup', 'gripper', 'extended_gripper']),
        DeclareLaunchArgument('DOF', default_value='auto', choices=['auto', '3', '4']),
        DeclareLaunchArgument('use_camera', default_value='false', choices=['true', 'false'],
            description='Legacy upstream RealSense mesh only; NOT the Orbbec transform.'),
        DeclareLaunchArgument('eye_in_hand_config', default_value='',
            description='Verified tool-to-camera and suction geometry YAML; empty disables mount TF.'),
        DeclareLaunchArgument('joint_states_topic', default_value='joint_states',
            description='URDF joint angles in radians; do not use dobot_joint_states.'),
        DeclareLaunchArgument('gui', default_value='false', choices=['true', 'false'],
            description='Offline joint sliders only; never enable alongside hardware state.'),
        DeclareLaunchArgument('publish_robot_description', default_value='true',
            choices=['true', 'false'], description='Disable if a robot_state_publisher exists.'),
        DeclareLaunchArgument('rviz', default_value='true', choices=['true', 'false']),
        OpaqueFunction(function=_display),
    ])
