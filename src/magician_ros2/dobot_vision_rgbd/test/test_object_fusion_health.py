"""Health remains live without synchronized detection results."""
import json
from collections import deque
from types import SimpleNamespace as NS
from unittest.mock import Mock

import numpy as np
import pytest
from dobot_vision_rgbd import object_fusion_node as fusion


def test_heartbeat_continues_after_sync_without_republishing_targets():
    node = NS(last_sync=1.0, last_detection_health=([], 5.0, True, ''),
              _publish_status=Mock(), detections_pub=Mock())
    fusion.ObjectFusionNode.publish_health(node)
    node._publish_status.assert_called_once_with([], 5.0, True, '')
    node.detections_pub.publish.assert_not_called()


@pytest.mark.parametrize('raw,expected', [
    (np.full((4, 4), 200, dtype=np.uint16), True),
    (np.zeros((4, 4), dtype=np.uint16), False),
])
def test_live_depth_validity_changes_without_synchronized_detection(raw, expected):
    node = NS(_record_stream=Mock(), bridge=NS(imgmsg_to_cv2=Mock(return_value=raw)),
              scale_16u=1.0, fusion=NS(reject={
                  'depth_minimum_mm': 100, 'depth_maximum_mm': 2000}),
              minimum_frame_depth_valid_ratio=0.1, depth_data_valid=not expected)
    fusion.ObjectFusionNode._mark_depth(node, NS(encoding='16UC1'))
    assert node.depth_data_valid is expected


def test_unreadable_live_depth_clears_previous_validity():
    node = NS(_record_stream=Mock(),
              bridge=NS(imgmsg_to_cv2=Mock(side_effect=ValueError('bad payload'))),
              depth_data_valid=True)
    fusion.ObjectFusionNode._mark_depth(node, NS(encoding='16UC1'))
    assert node.depth_data_valid is False


def test_repeated_health_does_not_refresh_stopped_streams(monkeypatch):
    monkeypatch.setattr(fusion.time, 'monotonic', lambda: 12.0)
    node = NS(get_clock=lambda: NS(now=lambda: NS(nanoseconds=12000000000)),
              _age_ms=fusion.ObjectFusionNode._age_ms,
              _stream_report=lambda key: {}, last_rgb=10.0, last_depth=10.0,
              last_sync=10.0, depth_data_valid=True, depth_frame_valid_ratio=0.5,
              max_delta=100, annotated_path='', rgb_payload_valid=True,
              stream_samples={'rgb': deque(), 'depth': deque()},
              status_pub=Mock())
    fusion.ObjectFusionNode._publish_status(node, [], 5.0, True, '')
    payload=json.loads(node.status_pub.publish.call_args.args[0].data)
    assert payload['depth_age_ms'] == 2000
    assert not payload['depth_stream_ok']
    assert not payload['depth_data_valid']
    assert not payload['sync_ok']
