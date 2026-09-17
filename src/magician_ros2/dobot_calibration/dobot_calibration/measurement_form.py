"""Validated conversion of physical direction words to TCP-frame translation."""

import math


def _magnitude(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{field} must be a number in millimetres')
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f'{field} must be finite and non-negative')
    return value


def _signed(value, direction, mapping, field):
    magnitude = _magnitude(value, field)
    if direction not in mapping:
        raise ValueError(f'{field} direction must be one of: {", ".join(mapping)}')
    return mapping[direction] * magnitude


def convert_tool_to_suction(document):
    convention = document.get('frame_convention', {})
    expected = {
        'positive_x': 'away_from_robot_base',
        'positive_y': 'left_when_viewed_from_robot_base_toward_tool',
        'positive_z': 'upward',
    }
    if any(convention.get(key) != value for key, value in expected.items()):
        raise ValueError('Unsupported or modified TCP frame convention')
    measurements = document['measurements_mm']
    suction = measurements['tool_origin_to_suction_tcp']
    if suction.get('physical_direction') != 'below_tool_origin':
        raise ValueError('tool-to-suction direction must be below_tool_origin')
    return [0.0, 0.0, -_magnitude(
        suction.get('axial_distance'), 'tool_origin_to_suction_tcp.axial_distance')]


def convert(document):
    tool_to_suction = convert_tool_to_suction(document)
    measurements = document['measurements_mm']
    camera = measurements['suction_tcp_to_camera_reference']
    suction_to_camera = [
        _signed(camera.get('forward_backward_distance'), camera.get('physical_direction'),
                {'farther_from_robot_base': 1, 'closer_to_robot_base': -1},
                'suction_tcp_to_camera_reference.forward_backward_distance'),
        _signed(camera.get('lateral_distance'), camera.get('lateral_direction'),
                {'left': 1, 'right': -1, 'centered': 0},
                'suction_tcp_to_camera_reference.lateral_distance'),
        _signed(camera.get('vertical_distance'), camera.get('vertical_direction'),
                {'above': 1, 'below': -1},
                'suction_tcp_to_camera_reference.vertical_distance'),
    ]
    result = dict(document)
    result['derived_tool_frame_mm'] = {
        'tool_to_suction_tcp_xyz': tool_to_suction,
        'suction_tcp_to_camera_link_xyz': suction_to_camera,
        'tool_to_camera_link_xyz': [
            tool_to_suction[index] + suction_to_camera[index] for index in range(3)],
    }
    result['derived_tool_frame_m'] = {
        key: [component / 1000.0 for component in value]
        for key, value in result['derived_tool_frame_mm'].items()
    }
    safety = document.get('safety_measurements_mm', {})
    error_item = safety.get('translation_error_bound', {})
    envelope_item = safety.get('tool_origin_envelope_radius', {})
    error_mm, envelope_mm = error_item.get('value'), envelope_item.get('value')
    if error_mm is None or envelope_mm is None:
        result['safety_mount_model'] = {
            'status': 'pending_verified_measurements',
            'translation_error_bound_m': None,
            'envelope_radius_m': None,
        }
    else:
        error_mm = _magnitude(error_mm, 'safety_measurements_mm.translation_error_bound')
        envelope_mm = _magnitude(
            envelope_mm, 'safety_measurements_mm.tool_origin_envelope_radius')
        camera_radius_mm = math.sqrt(sum(
            component ** 2
            for component in result['derived_tool_frame_mm']['tool_to_camera_link_xyz']))
        if not 0 < error_mm <= 6.0:
            raise ValueError('translation error bound must be greater than 0 and at most 6 mm')
        if not camera_radius_mm < envelope_mm < 300.0:
            raise ValueError(
                'tool-origin envelope radius must enclose the camera centre and be below 300 mm')
        result['safety_mount_model'] = {
            'status': 'verified_measurements_supplied',
            'translation_error_bound_m': error_mm / 1000.0,
            'envelope_radius_m': envelope_mm / 1000.0,
        }
    return result
