"""Launch-time camera parameter precedence, kept ROS-free for regression tests."""


def camera_parameter_overrides(requested):
    """Return only an explicit non-auto override; never erase YAML with empty."""
    requested = str(requested or '').strip()
    if not requested or requested.lower() == 'auto':
        return {}
    return {'camera_id': requested, 'camera_id_source': 'EXPLICIT_LAUNCH'}
