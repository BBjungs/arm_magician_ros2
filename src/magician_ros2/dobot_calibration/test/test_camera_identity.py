from dobot_calibration.camera_identity import resolve_camera_id
from dobot_calibration.camera_launch import camera_parameter_overrides


def device(serial='ORB-1', verified=True):
    return {'serial': serial, 'topics_verified': verified}


def test_explicit_launch_wins_when_connected():
    value = resolve_camera_id('ORB-2', 'EXPLICIT_LAUNCH', [device('ORB-1'), device('ORB-2')])
    assert (value.serial, value.source, value.verified, value.resolution) == (
        'ORB-2', 'EXPLICIT_LAUNCH', True, 'PASS')


def test_yaml_is_preserved_for_empty_or_auto_launch_semantics():
    for configured in ('ORB-1',):
        value = resolve_camera_id(configured, 'YAML', [device()])
        assert value.serial == 'ORB-1' and value.source == 'YAML'


def test_auto_with_yaml_serial_uses_yaml_precedence():
    value = resolve_camera_id('ORB-1', 'YAML', [device('ORB-1'), device('ORB-2')])
    assert value.serial == 'ORB-1' and value.source == 'YAML'


def test_auto_detects_exactly_one_and_propagates_serial():
    value = resolve_camera_id('', 'YAML', [device('ORB-9')])
    assert value.serial == 'ORB-9' and value.source == 'AUTO_DETECTED'
    assert value.verified and value.resolution == 'PASS'


def test_no_camera_fails_closed():
    assert resolve_camera_id('', 'YAML', []).gate == 'CAMERA_NOT_FOUND'


def test_multiple_cameras_require_selection():
    assert resolve_camera_id('', 'YAML', [device('ORB-1'), device('ORB-2')]).gate == \
        'MULTIPLE_CAMERAS_REQUIRE_SELECTION'


def test_configured_serial_must_be_connected():
    assert resolve_camera_id('ORB-9', 'YAML', [device('ORB-1')]).gate == \
        'CONFIGURED_CAMERA_NOT_FOUND'


def test_serial_must_own_active_rgb_depth_and_camerainfo_topics():
    assert resolve_camera_id('', 'YAML', [device(verified=False)]).gate == 'CAMERA_ID_NOT_VERIFIED'


def test_empty_launch_argument_does_not_override_yaml_camera_id():
    assert camera_parameter_overrides('') == {}


def test_auto_launch_argument_does_not_override_yaml_camera_id():
    assert camera_parameter_overrides('auto') == {}
