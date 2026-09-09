"""ROS adapter tests use a private domain and never create a motion client."""
from types import SimpleNamespace
import time

import numpy as np
import pytest

rclpy = pytest.importorskip('rclpy')
pytest.importorskip('dobot_msgs.msg._circle_target_array')
from cv_bridge import CvBridge
from sensor_msgs.msg import CameraInfo
from dobot_object_vision.detector import Detector, VisionError
from dobot_object_vision.node import ObjectVisionNode, convert_bundle, detection_message
from scene import K, scene


def bundle(encoding='32FC1', stamp=10.):
    image, depth, _, _ = scene()
    bridge = CvBridge()
    rgb = bridge.cv2_to_imgmsg(image, 'bgr8')
    data = (depth * 1000).astype(np.uint16) if encoding == '16UC1' else depth.astype(np.float32)
    dep = bridge.cv2_to_imgmsg(data, encoding)
    info = CameraInfo()
    info.width, info.height = image.shape[1], image.shape[0]
    info.k = K.ravel().tolist()
    info.p = np.c_[K, np.zeros(3)].ravel().tolist()
    for message in (rgb, dep, info):
        message.header.frame_id = 'camera_color_optical_frame'
        message.header.stamp.sec = int(stamp)
        message.header.stamp.nanosec = int((stamp - int(stamp)) * 1e9)
    return rgb, dep, info


@pytest.mark.parametrize('encoding', ['16UC1', '32FC1'])
def test_depth_units_and_native_schema(encoding):
    messages = bundle(encoding)
    image, depth, k = convert_bundle(messages, CvBridge(), 10.1, 'camera_color_optical_frame', .5, .05)
    result = Detector().process(image, depth, k)
    message = detection_message(result, messages[0].header)
    assert message.valid and len(message.detections) == 3
    assert message.header == messages[0].header
    for target in message.detections:
        assert .5 < target.depth < .65
        assert target.depth == target.camera_xyz.z
        assert target.pickable
        assert target.class_name in ('black', 'white', 'yellow')
        assert target.size < .08


@pytest.mark.parametrize('fault', ['stale', 'future', 'frame', 'size', 'skew', 'roi', 'distortion'])
def test_misaligned_or_stale_inputs_are_rejected(fault):
    messages = bundle()
    rgb, depth, info = messages
    if fault == 'stale':
        rgb.header.stamp.sec = 8
    elif fault == 'future':
        rgb.header.stamp.sec = 11
    elif fault == 'frame':
        depth.header.frame_id = 'camera_depth_optical_frame'
    elif fault == 'size':
        info.width = 320
    elif fault == 'skew':
        depth.header.stamp.nanosec = 80_000_000
    elif fault == 'roi':
        info.roi.x_offset = 10
    elif fault == 'distortion':
        info.p = [0.] * 12
        info.d = [.1, 0., 0., 0., 0.]
    with pytest.raises(VisionError):
        convert_bundle(messages, CvBridge(), 10.1, 'camera_color_optical_frame', .5, .05)


@pytest.fixture
def node():
    rclpy.init()
    value = ObjectVisionNode()
    try:
        yield value
    finally:
        value.destroy_node()
        rclpy.shutdown()


class Publisher:
    def __init__(self):
        self.messages = []
    def publish(self, message):
        self.messages.append(message)


def test_watchdog_clears_detections_when_stream_stops(node):
    node.output = Publisher()
    node.watchdog()
    assert node.output.messages[-1].valid is False
    node.latest = bundle(stamp=node.now_s())
    node.received = time.monotonic() - 2
    node.watchdog()
    assert not node.output.messages[-1].detections
    assert 'stale' in node.output.messages[-1].reason


def test_slow_frame_cannot_republish_targets_after_expiry(node, monkeypatch):
    node.output, node.annotated = Publisher(), Publisher()
    node.on_bundle(*bundle())
    clock = [10.1]
    monkeypatch.setattr(node, 'now_s', lambda: clock[0])
    process = node.detector.process
    def slow(*args):
        result = process(*args)
        clock[0] = 11.
        return result
    monkeypatch.setattr(node.detector, 'process', slow)
    node.process_latest()
    assert not node.output.messages[-1].valid
    assert not node.output.messages[-1].detections
    assert 'freshness' in node.output.messages[-1].reason


def test_raw_registered_rgbd_is_rectified_before_deprojection():
    import cv2
    messages = bundle()
    rgb, dep, info = messages
    bridge = CvBridge()
    image = bridge.imgmsg_to_cv2(rgb, 'bgr8')
    depth = bridge.imgmsg_to_cv2(dep, 'passthrough')
    distortion = np.array([.20, -.05, .001, -.001, 0.])
    yy, xx = np.indices(depth.shape)
    raw_uv = np.c_[xx.ravel(), yy.ravel()].astype(np.float32).reshape(-1, 1, 2)
    ideal = cv2.undistortPoints(raw_uv, K, distortion, P=K).reshape(*depth.shape, 2)
    raw_rgb = bridge.cv2_to_imgmsg(cv2.remap(image, ideal[:, :, 0], ideal[:, :, 1], cv2.INTER_LINEAR), 'bgr8')
    raw_depth = bridge.cv2_to_imgmsg(cv2.remap(depth, ideal[:, :, 0], ideal[:, :, 1], cv2.INTER_NEAREST), '32FC1')
    raw_rgb.header, raw_depth.header = rgb.header, dep.header
    info.d = distortion.tolist()
    info.distortion_model = 'plumb_bob'
    info.r = np.eye(3).ravel().tolist()
    image, depth, k = convert_bundle((raw_rgb, raw_depth, info), bridge, 10.1,
                                     'camera_color_optical_frame', .5, .05, input_rectified=False)
    result = Detector().process(image, depth, k)
    assert len(result.detections) == 3, result.rejected
    for target, uv in zip(result.detections, [(150, 230), (320, 240), (485, 245)]):
        assert np.linalg.norm(np.asarray(target.center_uv) - uv) < 1.5


def test_typed_detection_and_annotation_delivery_then_stream_loss(node):
    from rclpy.node import Node
    from rclpy.executors import MultiThreadedExecutor
    from rclpy.qos import qos_profile_sensor_data
    from sensor_msgs.msg import Image
    from dobot_msgs.msg import CircleTargetArray
    probe = Node('vision_test_camera')
    executor = MultiThreadedExecutor(num_threads=3)
    executor.add_node(probe)
    executor.add_node(node)
    outputs, annotations = [], []
    publishers = [probe.create_publisher(cls, node.settings[topic], qos_profile_sensor_data)
                  for cls, topic in [(Image, 'rgb_topic'), (Image, 'depth_topic'), (CameraInfo, 'camera_info_topic')]]
    output_sub = probe.create_subscription(CircleTargetArray, node.settings['detections_topic'], outputs.append, 1)
    annotation_sub = probe.create_subscription(Image, node.settings['annotated_topic'], annotations.append, qos_profile_sensor_data)
    messages = bundle()
    try:
        deadline, last = time.monotonic() + 4, 0.
        while time.monotonic() < deadline:
            if time.monotonic() - last > .07:
                stamp = probe.get_clock().now().to_msg()
                for pub, message in zip(publishers, messages):
                    message.header.stamp = stamp
                    pub.publish(message)
                last = time.monotonic()
            executor.spin_once(timeout_sec=.01)
        good = [message for message in outputs if message.valid and len(message.detections) == 3]
        assert good, [(m.valid, m.reason, len(m.detections)) for m in outputs]
        assert annotations
        assert any(a.header.stamp == m.header.stamp for a in annotations for m in good)
        deadline = time.monotonic() + .9
        while time.monotonic() < deadline:
            executor.spin_once(timeout_sec=.02)
        assert outputs[-1].valid is False
        assert not outputs[-1].detections
    finally:
        executor.shutdown()
        probe.destroy_node()
