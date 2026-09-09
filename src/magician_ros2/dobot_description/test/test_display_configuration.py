"""Validate model assets and launch choices without connecting to hardware."""

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

from launch import LaunchContext
import pytest
import xacro
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('display_launch', ROOT / 'launch/display.launch.py')
DISPLAY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DISPLAY)


@pytest.mark.parametrize('tool', ['none', 'pen', 'suction_cup', 'gripper', 'extended_gripper'])
def test_supported_tool_has_complete_model_and_live_launch(tool):
    context = LaunchContext()
    context.launch_configurations.update({
        'tool': tool, 'DOF': 'auto', 'use_camera': 'false',
        'model': str(ROOT / 'model/magician_standalone.urdf.xacro'),
        'gui': 'false', 'rviz': 'false', 'publish_robot_description': 'true',
        'joint_states_topic': 'joint_states', 'rvizconfig': str(ROOT / 'rviz/urdf_full.rviz'),
    })
    state, sliders, rviz = DISPLAY._display(context)
    assert state.condition.evaluate(context)
    assert not sliders.condition.evaluate(context)
    assert not rviz.condition.evaluate(context)
    model = ET.fromstring(xacro.process_file(str(ROOT / 'model/magician_standalone.urdf.xacro'),
        mappings={'tool': tool, 'DOF': '3' if tool in ('none', 'pen') else '4',
                  'use_camera': 'false'}).toxml())
    links = {link.get('name') for link in model.findall('link')}
    assert 'magician_root_link' in links
    assert 'magician_link_4' in links
    for joint in model.findall('joint'):
        assert joint.find('parent').get('link') in links
        assert joint.find('child').get('link') in links
    for mesh in model.findall('.//mesh'):
        uri = mesh.get('filename')
        assert uri.startswith('package://dobot_description/')
        assert (ROOT / uri.removeprefix('package://dobot_description/')).is_file()
    assert not any('realsense' in link for link in links)


def test_incompatible_configuration_fails_with_explanation():
    context = LaunchContext()
    context.launch_configurations.update({'tool': 'suction_cup', 'DOF': '3',
                                          'use_camera': 'false'})
    with pytest.raises(ValueError, match='URDF requires'):
        DISPLAY._display(context)


def test_rviz_can_receive_latched_model_and_sensor_images():
    manager = yaml.safe_load((ROOT / 'rviz/urdf_full.rviz').read_text())['Visualization Manager']
    displays = manager['Displays']
    robot = next(d for d in displays if d['Class'].endswith('/RobotModel'))
    assert robot['Description Topic']['Durability Policy'] == 'Transient Local'
    assert manager['Global Options']['Fixed Frame'] == 'magician_root_link'
    images = [d for d in displays if d['Class'].endswith('/Image')]
    assert {d['Topic']['Value'] for d in images} == {
        '/camera/color/image_raw', '/camera/depth/image_raw'}
    assert all(d['Topic']['Reliability Policy'] == 'Best Effort' for d in images)
    camera = yaml.safe_load((ROOT / 'rviz/camera.rviz').read_text())['Visualization Manager']
    assert camera['Global Options']['Fixed Frame'] == 'camera_link'
