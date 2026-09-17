"""Shared camera freshness contract for passive capture and baseline admission."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraFreshness:
    rgb_fresh: bool
    depth_fresh: bool
    rgb_info_fresh: bool
    depth_info_fresh: bool
    synchronized: bool
    rgb_rate_state: str
    depth_rate_state: str


def _stream_fresh(stream, lease_s):
    """Low rate is a warning; lack of advancing, recent frames is stale."""
    if not isinstance(stream, dict) or not stream.get('fresh', False):
        return False
    if not stream.get('timestamp_valid', False):
        return False
    if int(stream.get('duplicate_timestamps', 0)) != 0:
        return False
    if int(stream.get('regressed_timestamps', 0)) != 0:
        return False
    age_ms = stream.get('age_ms')
    return isinstance(age_ms, (int, float)) and 0 <= age_ms <= lease_s * 1000.0


def evaluate_camera_freshness(*, now_s, bundle, streams, rgb_lease_s, depth_lease_s,
                              camera_info_lease_s, expected_frame, sync_skew_s=0.100,
                              now_monotonic=None, last_valid_sync_monotonic=None):
    """Evaluate callback/driver evidence plus the actual synchronized bundle."""
    rgb = streams.get('rgb', {}) if isinstance(streams, dict) else {}
    depth = streams.get('depth', {}) if isinstance(streams, dict) else {}
    rgb_info = streams.get('rgb_info', {}) if isinstance(streams, dict) else {}
    depth_info = streams.get('depth_info', {}) if isinstance(streams, dict) else {}
    rgb_ok = _stream_fresh(rgb, rgb_lease_s)
    depth_ok = _stream_fresh(depth, depth_lease_s)
    rgb_info_ok = _stream_fresh(rgb_info, camera_info_lease_s) and bool(rgb_info.get('intrinsics_valid', False))
    depth_info_ok = _stream_fresh(depth_info, camera_info_lease_s) and bool(depth_info.get('intrinsics_valid', False))
    sync_ok = False
    if bundle is not None and len(bundle) == 3:
        stamps = [item.header.stamp.sec + item.header.stamp.nanosec * 1e-9 for item in bundle]
        frames_ok = all(item.header.frame_id == expected_frame for item in bundle)
        ages_ok = (0 <= now_s - stamps[0] <= rgb_lease_s
                   and 0 <= now_s - stamps[1] <= depth_lease_s
                   and 0 <= now_s - stamps[2] <= camera_info_lease_s)
        sync_ok = frames_ok and ages_ok and abs(stamps[0] - stamps[1]) <= sync_skew_s
    # A driver-health sample can show a poor instantaneous raw pairing while
    # the production synchronizer has just produced a valid capture.  Retain
    # that evidence only for the same configured stale lease; never relax the
    # 100 ms acceptance threshold itself.
    sync_lease = max(rgb_lease_s, depth_lease_s, camera_info_lease_s)
    recent_valid_sync = (now_monotonic is not None and last_valid_sync_monotonic is not None
                         and 0 <= now_monotonic - last_valid_sync_monotonic <= sync_lease)
    return CameraFreshness(rgb_ok, depth_ok, rgb_info_ok, depth_info_ok,
                           bool((sync_ok or recent_valid_sync) and rgb_ok and depth_ok and rgb_info_ok),
                           str(rgb.get('state', 'UNKNOWN')), str(depth.get('state', 'UNKNOWN')))
