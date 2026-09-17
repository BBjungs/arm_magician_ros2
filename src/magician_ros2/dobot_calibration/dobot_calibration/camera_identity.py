"""Fail-closed camera identity resolution, independent of ROS transport."""

from dataclasses import dataclass


AUTO_VALUES = {'', 'auto'}


@dataclass(frozen=True)
class CameraIdentity:
    serial: str = ''
    source: str = 'AUTO_DETECTED'
    verified: bool = False
    resolution: str = 'FAIL'
    gate: str = 'CAMERA_NOT_FOUND'


def resolve_camera_id(configured_id, source, devices):
    """Resolve only from enumerated active Orbbec driver devices.

    ``devices`` is an iterable of ``{'serial': str, 'topics_verified': bool}``.
    A configured serial still has to be present, and must own the RGB, depth,
    and CameraInfo topic namespace used by calibration.
    """
    configured = str(configured_id or '').strip()
    source = source if source in ('EXPLICIT_LAUNCH', 'YAML') else 'AUTO_DETECTED'
    by_serial = {str(item.get('serial', '')).strip(): item for item in devices
                 if str(item.get('serial', '')).strip()}
    if configured and configured.lower() not in AUTO_VALUES:
        item = by_serial.get(configured)
        if item is None:
            return CameraIdentity(source=source, gate='CONFIGURED_CAMERA_NOT_FOUND')
        if not item.get('topics_verified', False):
            return CameraIdentity(serial=configured, source=source,
                                  gate='CAMERA_ID_NOT_VERIFIED')
        return CameraIdentity(configured, source, True, 'PASS', '')
    if not by_serial:
        return CameraIdentity(gate='CAMERA_NOT_FOUND')
    if len(by_serial) != 1:
        return CameraIdentity(gate='MULTIPLE_CAMERAS_REQUIRE_SELECTION')
    serial, item = next(iter(by_serial.items()))
    if not item.get('topics_verified', False):
        return CameraIdentity(serial=serial, gate='CAMERA_ID_NOT_VERIFIED')
    return CameraIdentity(serial, 'AUTO_DETECTED', True, 'PASS', '')
