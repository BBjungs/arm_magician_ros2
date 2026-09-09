import json
from types import SimpleNamespace as NS
from unittest.mock import Mock

import numpy as np
import pytest

import dobot_vision_rgbd.camera_health_node as health


@pytest.mark.parametrize('speeds,ready', [((480, 480), False), ((5000, 480), False), ((5000, 5000), True)])
def test_usb_requires_both_interfaces_at_superspeed(tmp_path, speeds, ready):
    for product, speed in zip(('0511', '0614'), speeds):
        path = tmp_path / product
        path.mkdir()
        for key, value in [('idVendor', '2bc5'), ('idProduct', product), ('speed', str(speed))]:
            (path / key).write_text(value)
    assert health.usb_status(tmp_path)['superspeed'] is ready


def test_missing_usb_does_not_report_ready(tmp_path):
    assert not health.usb_status(tmp_path)['superspeed']


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


def test_metrics_report_staleness_gaps_and_repeated_timestamps():
    samples = [(1.0, 100.0, 'camera'), (1.1, 100.1, 'camera')]
    result = health.stream_metrics(samples, 3.0, 30)
    assert not result['fresh']
    assert result['estimated_missing_frames'] == 2
    assert result['fps'] == 10
    samples.append((1.2, 100.1, 'camera'))
    assert not health.stream_metrics(samples, 1.2, 30)['timestamp_valid']


@pytest.fixture
def healthy(monkeypatch):
    monkeypatch.setattr(health, 'time', NS(monotonic=lambda: 10.0))
    monkeypatch.setattr(health, 'usb_status', lambda: {'superspeed': True, 'devices': []})
    samples = [(10-(59-i)/30, 100+i/30, 'color_optical') for i in range(60)]
    header = NS(frame_id='color_optical')
    image = NS(width=2, height=2, header=header, encoding='rgb8', step=6, data=bytes(12))
    info = NS(width=2, height=2, header=header, k=[100, 0, 1, 0, 100, 1, 0, 0, 1])
    value = NS(samples={key: list(samples) for key in ('rgb','depth','rgb_info','depth_info','cloud')},
               validity={key: {'valid': True, 'valid_ratio': 0.5} for key in ('depth','cloud')},
               latest={'rgb': image, 'depth': image, 'rgb_info': info, 'depth_info': info, 'cloud': NS(header=header)},
               publisher=Mock(), expected_fps=30, protection_active=False, protection_checked_at=10)
    return value


def report(node):
    health.CameraHealthNode.publish_health(node)
    return json.loads(node.publisher.publish.call_args.args[0].data)


def test_health_can_report_ready_for_complete_valid_data(healthy):
    assert report(healthy)['ready']


def test_usb2_blocks_otherwise_valid_streams(healthy, monkeypatch):
    monkeypatch.setattr(health, 'usb_status', lambda: {'superspeed': False, 'devices': []})
    result = report(healthy)
    assert not result['ready']
    assert 'usb_not_superspeed_or_device_ambiguous' in result['blockers']


def test_stream_loss_clears_readiness(healthy):
    healthy.samples['depth'] = []
    assert not report(healthy)['ready']


def test_zero_depth_clears_readiness(healthy):
    healthy.validity['depth'] = {'valid': False, 'valid_ratio': 0}
    assert 'depth_data_invalid' in report(healthy)['blockers']


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
