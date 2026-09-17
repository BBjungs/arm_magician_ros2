"""Physical direction words are converted to the verified TCP convention."""

import pytest

from dobot_calibration.measurement_form import convert, convert_tool_to_suction


def form():
    return {
        'frame_convention': {
            'positive_x': 'away_from_robot_base',
            'positive_y': 'left_when_viewed_from_robot_base_toward_tool',
            'positive_z': 'upward',
        },
        'measurements_mm': {
            'tool_origin_to_suction_tcp': {
                'axial_distance': 60.0,
                'physical_direction': 'below_tool_origin',
            },
            'suction_tcp_to_camera_reference': {
                'forward_backward_distance': 50.0,
                'physical_direction': 'farther_from_robot_base',
                'lateral_distance': 12.0,
                'lateral_direction': 'right',
                'vertical_distance': 35.0,
                'vertical_direction': 'above',
            },
        },
    }


def test_unsigned_measurements_are_mapped_to_tcp_xyz():
    result = convert(form())['derived_tool_frame_mm']
    assert result['tool_to_suction_tcp_xyz'] == [0.0, 0.0, -60.0]
    assert result['suction_tcp_to_camera_link_xyz'] == [50.0, -12.0, 35.0]
    assert result['tool_to_camera_link_xyz'] == [50.0, -12.0, -25.0]


def test_as_built_70_mm_below_tool_is_negative_z_and_available_before_camera_measurement():
    value = form()
    value['measurements_mm']['tool_origin_to_suction_tcp']['axial_distance'] = 70.0
    value['measurements_mm']['suction_tcp_to_camera_reference'][
        'forward_backward_distance'] = None
    assert convert_tool_to_suction(value) == [0.0, 0.0, -70.0]


def test_conversion_also_reports_metres():
    result = convert(form())['derived_tool_frame_m']
    assert result['tool_to_suction_tcp_xyz'] == [0.0, 0.0, -0.06]
    assert result['suction_tcp_to_camera_link_xyz'] == [0.05, -0.012, 0.035]


def test_as_built_camera_measurements_use_verified_direction_signs():
    value = form()
    value['measurements_mm']['tool_origin_to_suction_tcp'].update(
        axial_distance=70.0, physical_direction='below_tool_origin')
    value['measurements_mm']['suction_tcp_to_camera_reference'] = {
        'forward_backward_distance': 50.0,
        'physical_direction': 'farther_from_robot_base',
        'lateral_distance': 0.0,
        'lateral_direction': 'centered',
        'vertical_distance': 35.0,
        'vertical_direction': 'above',
    }
    result = convert(value)
    assert result['derived_tool_frame_mm'] == {
        'tool_to_suction_tcp_xyz': [0.0, 0.0, -70.0],
        'suction_tcp_to_camera_link_xyz': [50.0, 0.0, 35.0],
        'tool_to_camera_link_xyz': [50.0, 0.0, -35.0],
    }
    assert result['derived_tool_frame_m']['tool_to_camera_link_xyz'] == [
        0.05, 0.0, -0.035]


def test_unfilled_distance_fails_before_calibration():
    value = form()
    value['measurements_mm']['suction_tcp_to_camera_reference'][
        'forward_backward_distance'] = None
    with pytest.raises(ValueError, match='must be a number'):
        convert(value)


def test_signed_distance_is_rejected():
    value = form()
    value['measurements_mm']['suction_tcp_to_camera_reference'][
        'lateral_distance'] = -12.0
    with pytest.raises(ValueError, match='non-negative'):
        convert(value)


def test_safety_measurements_convert_as_unsigned_bounds():
    value = form()
    value['safety_measurements_mm'] = {
        'translation_error_bound': {'value': 2.0},
        'tool_origin_envelope_radius': {'value': 150.0},
    }
    assert convert(value)['safety_mount_model'] == {
        'status': 'verified_measurements_supplied',
        'translation_error_bound_m': 0.002,
        'envelope_radius_m': 0.15,
    }


def test_safety_envelope_must_enclose_measured_camera_centre():
    value = form()
    value['safety_measurements_mm'] = {
        'translation_error_bound': {'value': 2.0},
        'tool_origin_envelope_radius': {'value': 50.0},
    }
    with pytest.raises(ValueError, match='enclose the camera centre'):
        convert(value)
