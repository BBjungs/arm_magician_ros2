from types import SimpleNamespace

from dobot_calibration.baseline_admission import AuthoritativeBaselineAdmissionGate
from dobot_calibration.camera_freshness import evaluate_camera_freshness


def message(stamp, frame='camera_color_optical_frame'):
    sec = int(stamp); nanosec = int((stamp - sec) * 1e9)
    return SimpleNamespace(header=SimpleNamespace(stamp=SimpleNamespace(sec=sec, nanosec=nanosec),
                                                   frame_id=frame))


def stream(age_ms, state='DEGRADED_RATE', **extra):
    return {'fresh': True, 'timestamp_valid': True, 'duplicate_timestamps': 0,
            'regressed_timestamps': 0, 'age_ms': age_ms, 'state': state, **extra}


def inputs(now=100.0, rgb_age=700, depth_age=960, skew=.05):
    bundle = (message(now-rgb_age/1000), message(now-rgb_age/1000-skew),
              message(now-rgb_age/1000))
    streams = {'rgb': stream(rgb_age), 'depth': stream(depth_age),
               'rgb_info': stream(rgb_age, intrinsics_valid=True),
               'depth_info': stream(depth_age, intrinsics_valid=True)}
    return now, bundle, streams


def evaluate(*args, **kwargs):
    now, bundle, streams = inputs(*args, **kwargs)
    return evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                     rgb_lease_s=1.5, depth_lease_s=1.5,
                                     camera_info_lease_s=1.5,
                                     expected_frame='camera_color_optical_frame')


def snapshot(result):
    return {'HARDWARE_READY':True, 'PASSIVE_CAPTURE_READY':True, 'RGB_FRESH':result.rgb_fresh,
            'DEPTH_FRESH':result.depth_fresh, 'RGB_CAMERAINFO_FRESH':result.rgb_info_fresh,
            'DEPTH_CAMERAINFO_FRESH':result.depth_info_fresh, 'DEPTH_STABLE':True,
            'RGB_DEPTH_CAMERAINFO_SYNCHRONIZED':result.synchronized, 'TCP_FRESH':True,
            'JOINTS_FRESH':True, 'ROBOT_STABLE':True, 'ALARM_FREE':True,
            'POINT_CLOUD_USABLE':True, 'SCENE_GEOMETRY_PASS':True, 'DOMINANT_PLANE_PASS':True}


def test_rgb_4_to_5_fps_under_lease_is_fresh(): assert evaluate().rgb_fresh
def test_depth_2_to_3_fps_under_lease_is_fresh(): assert evaluate().depth_fresh
def test_low_rate_is_warning_not_stale(): assert evaluate().rgb_rate_state == 'DEGRADED_RATE'
def test_rgb_stops_beyond_lease_is_stale(): assert not evaluate(rgb_age=1501).rgb_fresh
def test_depth_stops_beyond_lease_is_stale(): assert not evaluate(depth_age=1501).depth_fresh

def test_duplicate_timestamp_is_rejected():
    now,bundle,streams=inputs(); streams['rgb']['duplicate_timestamps']=1
    assert not evaluate_camera_freshness(now_s=now,bundle=bundle,streams=streams,rgb_lease_s=1.5,depth_lease_s=1.5,camera_info_lease_s=1.5,expected_frame='camera_color_optical_frame').rgb_fresh

def test_regressed_timestamp_is_rejected():
    now,bundle,streams=inputs(); streams['depth']['regressed_timestamps']=1
    assert not evaluate_camera_freshness(now_s=now,bundle=bundle,streams=streams,rgb_lease_s=1.5,depth_lease_s=1.5,camera_info_lease_s=1.5,expected_frame='camera_color_optical_frame').depth_fresh

def test_historical_duplicate_outside_lease_recovers_current_freshness():
    now, bundle, streams = inputs()
    streams['rgb'].update(current_timestamp_valid=True,
                          current_duplicate_timestamps=0,
                          historical_duplicate_timestamps=1,
                          duplicate_timestamps=1)
    value = evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                      rgb_lease_s=1.5, depth_lease_s=1.5,
                                      camera_info_lease_s=1.5,
                                      expected_frame='camera_color_optical_frame')
    assert value.rgb_fresh

def test_duplicate_in_active_window_fails_closed():
    now, bundle, streams = inputs()
    streams['rgb'].update(current_timestamp_valid=False,
                          current_duplicate_timestamps=1)
    value = evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                      rgb_lease_s=1.5, depth_lease_s=1.5,
                                      camera_info_lease_s=1.5,
                                      expected_frame='camera_color_optical_frame')
    assert not value.rgb_fresh
def test_raw_rate_does_not_override_valid_synchronized_capture(): assert evaluate().synchronized
def test_sync_skew_over_threshold_is_rejected(): assert not evaluate(skew=.101).synchronized

def test_bad_instantaneous_pair_uses_recent_valid_synchronized_capture():
    now,bundle,streams=inputs(skew=.101)
    value=evaluate_camera_freshness(now_s=now,bundle=bundle,streams=streams,rgb_lease_s=1.5,depth_lease_s=1.5,camera_info_lease_s=1.5,expected_frame='camera_color_optical_frame',now_monotonic=50,last_valid_sync_monotonic=49)
    assert value.synchronized

def test_health_sync_cannot_substitute_for_an_actual_payload():
    now, bundle, streams = inputs(skew=.101)
    streams['rgb_depth_sync_valid'] = True
    value = evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                      rgb_lease_s=1.5, depth_lease_s=1.5,
                                      camera_info_lease_s=1.5,
                                      expected_frame='camera_color_optical_frame')
    assert not value.synchronized


def test_recent_actual_payload_survives_an_unmatched_intermediate_frame():
    now, bundle, streams = inputs(skew=.101)
    value = evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                      rgb_lease_s=1.5, depth_lease_s=1.5,
                                      camera_info_lease_s=1.5,
                                      expected_frame='camera_color_optical_frame',
                                      now_monotonic=20.0,
                                      last_valid_sync_monotonic=19.98)
    assert value.synchronized


def test_recent_actual_payload_expires_at_the_existing_lease():
    now, bundle, streams = inputs(skew=.101)
    value = evaluate_camera_freshness(now_s=now, bundle=bundle, streams=streams,
                                      rgb_lease_s=1.5, depth_lease_s=1.5,
                                      camera_info_lease_s=1.5,
                                      expected_frame='camera_color_optical_frame',
                                      now_monotonic=21.51,
                                      last_valid_sync_monotonic=20.0)
    assert not value.synchronized


def test_all_fresh_for_ten_seconds_is_admitted():
    gate=AuthoritativeBaselineAdmissionGate(); item=snapshot(evaluate())
    gate.update(item,0); assert gate.update(item,10)['eligible']

def test_stale_at_second_nine_resets_window():
    gate=AuthoritativeBaselineAdmissionGate(); item=snapshot(evaluate()); gate.update(item,0)
    bad=dict(item, DEPTH_FRESH=False); assert gate.update(bad,9)['stable_for_s']==0

def test_recovery_starts_a_new_ten_second_window():
    gate=AuthoritativeBaselineAdmissionGate(); item=snapshot(evaluate()); gate.update(item,0)
    gate.update(dict(item, RGB_FRESH=False),9); gate.update(item,10)
    assert gate.update(item,20)['eligible']
