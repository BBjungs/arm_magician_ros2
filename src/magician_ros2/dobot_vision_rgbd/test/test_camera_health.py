import inspect
import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import numpy as np
import pytest

import dobot_vision_rgbd.camera_health_node as health


def test_health_sensor_qos_keeps_only_the_latest_sample():
    assert health.HEALTH_SENSOR_QOS.depth == 1


def test_low_rate_cloud_can_use_a_longer_freshness_window():
    samples = [(8.5, 100.0, 'color_optical')]
    assert not health.stream_metrics(samples, 10.0, 30)['fresh']
    assert health.stream_metrics(samples, 10.0, 30, freshness_s=2.0)['fresh']


def test_cloud_callback_never_destroys_or_recreates_executor_entities():
    source = inspect.getsource(health.CameraHealthNode.receive_cloud)
    assert 'destroy_subscription' not in source
    assert 'create_subscription' not in source


@pytest.mark.parametrize(
    'speeds,ready',
    [((480, 480), False), ((480, 5000), True), ((5000, 5000), True)],
)
def test_usb_requires_superspeed_on_depth_data_path(tmp_path, speeds, ready):
    for product, speed in zip(('0511', '0614'), speeds):
        path = tmp_path / product
        path.mkdir()
        values = [('idVendor', '2bc5'), ('idProduct', product), ('speed', str(speed))]
        if product == '0511':
            values.append(('serial', 'camera-serial'))
        for key, value in values:
            (path / key).write_text(value)
    result = health.usb_status(tmp_path)
    assert result['superspeed'] is ready
    assert result['identity_valid'] is True
    assert result['camera_identity'] == 'camera-serial'


def test_missing_usb_does_not_report_ready(tmp_path):
    result = health.usb_status(tmp_path)
    assert not result['superspeed']
    assert not result['identity_valid']


def test_missing_or_ambiguous_camera_identity_fails_closed(tmp_path):
    for suffix, product, serial in (
        ('rgb-a', '0511', 'camera-a'),
        ('rgb-b', '0511', 'camera-b'),
        ('depth', '0614', ''),
    ):
        path = tmp_path / suffix
        path.mkdir()
        for key, value in (
            ('idVendor', '2bc5'), ('idProduct', product), ('speed', '5000')
        ):
            (path / key).write_text(value)
        if serial:
            (path / 'serial').write_text(serial)
    result = health.usb_status(tmp_path)
    assert not result['superspeed']
    assert not result['identity_valid']


def test_depth_rejects_zero_and_respects_endianness_and_padding():
    data = np.array([[100, 0, 999], [200, 0, 999]], dtype='>u2').tobytes()
    msg = NS(encoding='16UC1', is_bigendian=True, width=2, height=2, step=6, data=data)
    assert health.valid_depth_ratio(msg) == 0.5
    msg.data = bytes(12)
    assert health.valid_depth_ratio(msg) == 0
    msg.data = bytes(2)
    with pytest.raises(ValueError):
        health.valid_depth_ratio(msg)


def test_cloud_requires_finite_xyz_and_positive_depth():
    msg = NS(width=3, height=1, row_step=36, point_step=12, is_bigendian=False,
             fields=[NS(name=name, offset=i*4, count=1, datatype=7) for i, name in enumerate('xyz')],
             data=np.array([[1, 2, 3], [float('nan'), 2, 3], [1, 2, 0]], dtype='<f4').tobytes())
    assert health.valid_cloud_ratio(msg) == pytest.approx(1/3)


def test_cloud_accepts_only_a_provably_complete_packed_vendor_buffer():
    points = np.array(
        [[1, 2, 3, 0], [4, 5, 6, 0], [7, 8, 9, 0]], dtype='<f4',
    )
    msg = NS(
        width=3, height=1, row_step=16, point_step=16, is_bigendian=False,
        fields=[NS(name=name, offset=i*4, count=1, datatype=7)
                for i, name in enumerate('xyz')],
        data=points.tobytes(),
    )
    assert health.valid_cloud_ratio(msg) == 1.0
    msg.data = msg.data[:-1]
    with pytest.raises(ValueError):
        health.valid_cloud_ratio(msg)


def test_metrics_report_staleness_gaps_and_repeated_timestamps():
    samples = [(1.0, 100.0, 'camera'), (1.1, 100.1, 'camera')]
    result = health.stream_metrics(samples, 3.0, 30)
    assert not result['fresh']
    assert result['estimated_missing_frames'] == 2
    assert result['fps'] == 10
    samples.append((1.2, 100.1, 'camera'))
    repeated = health.stream_metrics(samples, 1.2, 30)
    assert not repeated['timestamp_valid']
    assert repeated['duplicate_timestamps'] == 1
    assert repeated['timestamp_fps'] == pytest.approx(20.0)


def test_old_duplicate_does_not_block_current_lease():
    samples = [(1.0, 100.0, 'camera'), (1.1, 100.0, 'camera'),
               (9.8, 200.0, 'camera'), (10.0, 200.2, 'camera')]
    result = health.stream_metrics(samples, 10.0, 30, freshness_s=1.5)
    assert result['historical_duplicate_timestamps'] == 1
    assert result['current_duplicate_timestamps'] == 0
    assert result['current_timestamp_valid']


def test_fresh_low_rate_is_degraded_warning_not_hard_blocker(healthy):
    samples = [(9.8, 100.0, 'color_optical'), (10.0, 100.2, 'color_optical')]
    healthy.samples['rgb'] = samples
    result = report(healthy)
    assert result['streams']['rgb']['state'] == 'DEGRADED_RATE'
    assert 'rgb_rate_unverified_or_degraded' in result['warnings']
    assert 'rgb_rate_unverified_or_degraded' not in result['blockers']


def test_sync_uses_a_live_matching_pair_instead_of_unrelated_latest_frames():
    rgb = [(9.6, 100.0, 'camera'), (9.9, 100.3, 'camera')]
    depth = [(9.7, 100.01, 'camera'), (10.0, 100.7, 'camera')]
    assert health.synchronized_skew_ms(rgb, depth, 10.0) == pytest.approx(10.0)
    assert health.synchronized_skew_ms(rgb, depth, 12.0) is None


def test_health_reports_only_a_threshold_valid_live_sync_pair(healthy):
    assert report(healthy)['rgb_depth_sync_valid'] is True


@pytest.fixture
def healthy(monkeypatch):
    monkeypatch.setattr(health, 'time', NS(monotonic=lambda: 10.0))
    monkeypatch.setattr(health, 'usb_status', lambda: {
        'superspeed': True,
        'identity_valid': True,
        'camera_identity': 'test-camera',
        'devices': [],
    })
    samples = [(10-(59-i)/30, 100+i/30, 'color_optical') for i in range(60)]
    header = NS(frame_id='color_optical')
    image = NS(width=2, height=2, header=header, encoding='rgb8', step=6, data=bytes(12))
    info = NS(width=2, height=2, header=header, k=[100, 0, 1, 0, 100, 1, 0, 0, 1])
    value = NS(samples={key: list(samples) for key in ('rgb','depth','rgb_info','depth_info','cloud')},
               validity={key: {'valid': True, 'valid_ratio': 0.5} for key in ('depth','cloud')},
               latest={'rgb': image, 'depth': image, 'rgb_info': info, 'depth_info': info, 'cloud': NS(header=header)},
               publisher=Mock(), expected_fps=30, minimum_fps=2, cloud_sample_period_s=0.5,
               protection_active=False, protection_checked_at=10,
               data_lock=health.threading.Lock())
    return value


def report(node):
    health.CameraHealthNode.publish_health(node)
    return json.loads(node.publisher.publish.call_args.args[0].data)


def test_health_can_report_ready_for_complete_valid_data(healthy):
    assert report(healthy)['ready']


def test_usable_rate_is_ready_but_requested_rate_degradation_is_visible(healthy):
    samples = [(10-(59-i)/3, 100+i/3, 'color_optical') for i in range(60)]
    healthy.samples = {key: list(samples) for key in healthy.samples}
    result = report(healthy)
    assert result['ready']
    assert 'rgb_below_requested_rate' in result['warnings']
    assert not result['streams']['rgb']['expected_rate_ok']


def test_usb2_blocks_otherwise_valid_streams(healthy, monkeypatch):
    monkeypatch.setattr(health, 'usb_status', lambda: {
        'superspeed': False,
        'identity_valid': True,
        'camera_identity': 'test-camera',
        'devices': [],
    })
    result = report(healthy)
    assert not result['ready']
    assert 'usb_not_superspeed_or_device_ambiguous' in result['blockers']


def test_stream_loss_clears_readiness(healthy):
    healthy.samples['depth'] = []
    assert not report(healthy)['ready']


def test_depth_quality_is_delegated_and_does_not_mask_transport_health(healthy):
    healthy.validity['depth'] = {'valid': False, 'valid_ratio': 0}
    result = report(healthy)
    assert 'depth_data_invalid' not in result['blockers']
    assert result['depth_quality_state'] == 'delegated_to_calibration'


def test_invalid_rgb_buffer_clears_readiness(healthy):
    healthy.latest['rgb'] = NS(width=2, height=2, header=NS(frame_id='color_optical'), encoding='rgb8', step=6, data=b'')
    assert 'rgb_payload_invalid' in report(healthy)['blockers']


def test_cloud_frame_mismatch_clears_readiness(healthy):
    healthy.latest['cloud'] = NS(header=NS(frame_id='wrong'))
    assert 'point_cloud_frame_mismatch' in report(healthy)['blockers']


@pytest.mark.parametrize('protection', [True, None])
def test_active_or_unknown_protection_blocks_readiness(healthy, protection):
    healthy.protection_active = protection
    result = report(healthy)
    assert not result['ready']
    assert 'ldp_protection_active_or_unverified' in result['blockers']


def test_stale_protection_status_blocks_readiness(healthy):
    healthy.protection_checked_at = 0
    assert not report(healthy)['ready']


@pytest.mark.parametrize('age_ms,expected_age,fresh', [
    (50.0, 450.0, True), (700.0, 1100.0, False),
    (None, None, False), (-1.0, None, False), (float('nan'), None, False),
])
def test_forwarded_health_preserves_image_age(healthy, age_ms, expected_age, fresh):
    stream = {'count': 60, 'fps': 30, 'max_gap_ms': 34,
              'timestamp_valid': True, 'frame_id': 'color_optical'}
    healthy.vision_health_time = 9.6
    healthy.vision_health = {
        'rgb_stream': stream, 'depth_stream': stream,
        'rgb_age_ms': age_ms, 'depth_age_ms': age_ms,
        'depth_valid_ratio': 0.5, 'depth_data_valid': True,
        'rgb_payload_valid': True, 'registered_depth': True,
        'sync_delta_ms': 5,
    }
    result = report(healthy)['streams']['depth']
    assert result['fresh'] is fresh
    if expected_age is None:
        assert result['age_ms'] is None
    else:
        assert result['age_ms'] == pytest.approx(expected_age)


def test_direct_images_do_not_depend_on_detector_heartbeat(healthy):
    healthy.direct_image_health = True
    healthy.vision_health = {}
    healthy.vision_health_time = None
    result = report(healthy)
    assert result['ready']
    assert result['streams']['depth']['fresh']


def test_stopped_direct_depth_cannot_be_masked_by_detector_health(healthy):
    healthy.direct_image_health = True
    healthy.samples['depth'] = []
    stream = {'count': 60, 'fps': 30, 'timestamp_valid': True,
              'frame_id': 'color_optical', 'max_gap_ms': 34}
    healthy.vision_health_time = 10.0
    healthy.vision_health = {'rgb_stream': stream, 'depth_stream': stream,
                             'rgb_age_ms': 0, 'depth_age_ms': 0}
    result = report(healthy)
    assert not result['ready']
    assert not result['streams']['depth']['fresh']
