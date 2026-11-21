import unittest
from collections import deque
from unittest.mock import Mock
from sensor_msgs.msg import CameraInfo
from dataclasses import replace

import numpy as np

from dobot_auto_center.rgbd_sync import append_sample, select_frame
from dobot_auto_center.ros_sensors import CameraReceiver
from dobot_auto_center.workflow import Workflow, State
from dobot_auto_center.vision import Detection, Observation
from dobot_auto_center.config import load
from test_core import CONFIG


class Matching(unittest.TestCase):
    def test_validated_pending_preview_survives_ticks_until_info_arrives(self):
        cfg = load(CONFIG)
        node = Mock()
        node.get_clock().now().nanoseconds = 10_000_000_000
        camera = CameraReceiver(node, cfg['camera'], lambda: 10., simulated=True)
        receive = node.create_subscription.call_args_list[0].args[2]
        msg = Mock(width=cfg['camera']['width'], height=cfg['camera']['height'], encoding='bgr8')
        msg.header.frame_id = cfg['camera']['frame']
        msg.header.stamp.sec, msg.header.stamp.nanosec = 10, 0
        camera.bridge = Mock()
        camera.bridge.imgmsg_to_cv2.return_value = np.zeros((4, 4, 3))
        receive(msg, {})
        self.assertEqual(camera.counts['rgb']['enqueued'], 1)
        camera.enqueue('depth', camera.depth, (10_000_000_000, 10., np.ones((4, 4)), 10.))
        workflow = Workflow(cfg, Mock(), Mock(), lambda *_: False)
        workflow.detector = Mock()
        for now in (10.01, 10.05, 10.1):
            self.assertIsNone(camera.take(now))
            workflow.update_preview(camera.pending_preview(now))
            workflow.tick(now)
            self.assertIsNotNone(workflow.display_frame(now))
            self.assertFalse(workflow.rgbd(now))
            self.assertEqual(workflow.state, State.CONNECTING)
            self.assertEqual(len(camera.rgb), 1)
        camera.enqueue('info', camera.info_stamps, (10_000_000_000, 10., 10.11))
        workflow.ingest(camera.take(10.11), 10.11)
        workflow.tick(10.11)
        self.assertTrue(workflow.rgbd(10.11))
        self.assertEqual(workflow.state, State.DETECTING)
        workflow.tick(10.46)
        self.assertEqual(workflow.state, State.DISCONNECTED)
        workflow.submit.assert_not_called()

    def test_header_boundaries(self):
        base = 1795186880430451681
        r = (base, 10., 10.)
        for ms in (0, 20, 40, 60, 73, 78):
            for sign in (1, -1):
                with self.subTest(ms=ms, sign=sign):
                    d = (base + sign*ms*1000000, 10.)
                    result = select_frame([r], [d], [r], 10.1, .45, .06)
                    self.assertEqual(result[3], '' if ms <= 60 else 'depth_skew')

    def test_out_of_order_and_delayed_calibration(self):
        old = (100000000, 10., 10.)
        latest = (200000000, 10.01, 10.01)
        args = ([latest, old], [old, latest])
        self.assertEqual(select_frame(*args, [], 10.02, .45, .06)[3], 'waiting')
        self.assertEqual(select_frame(*args, [old], 10.03, .45, .06)[0], old)
        self.assertEqual(select_frame(*args, [latest], 10.03, .45, .06)[0], latest)

    def test_calibration_eviction_during_burst_and_delayed_depth(self):
        for info_first in (True, False):
            for offset_ms in (0, 60):
                with self.subTest(info_first=info_first, offset_ms=offset_ms):
                    rgb = deque(maxlen=8)
                    info = deque(maxlen=12)
                    r = (1000000000, 10., 10.)
                    i = (r[0]+offset_ms*1000000, 10., 10.001)
                    if not info_first:
                        rgb.append(r)
                        self.assertEqual(select_frame(rgb, [r], info, 10.01, .45, .06)[3], 'waiting')
                    append_sample('info', info, i, rgb, 60000000)
                    if info_first:
                        rgb.append(r)
                    for j in range(14):
                        append_sample('info', info, (r[0]+(120+j)*1000000, 10., 10.02),
                                      rgb, 60000000)
                    self.assertEqual(len(info), 12)
                    self.assertEqual(select_frame(rgb, [r], info, 10.1, .45, .06),
                                     (r, r, i, ''))
                    self.assertEqual(select_frame(rgb, [r], info, 10.5, .45, .06)[3], 'stale_rgb')

    def test_preview_does_not_retire_newer_rgb_awaiting_info(self):
        older = (100_000_000, 10., 10.)
        newer = (200_000_000, 10.01, 10.01)
        wrong = (1, 9.99, 10.)
        preview = select_frame([newer, older], [older, newer], [wrong], 10.16, .45, .06)
        self.assertEqual((preview[0], preview[3]), (older, 'info_skew'))
        pending = [r for r in [newer, older] if r[0] > preview[0][0]]
        self.assertEqual(select_frame(pending, [newer], [newer], 10.17, .45, .06),
                         (newer, newer, newer, ''))

    def test_delayed_info_and_readiness_expiry(self):
        for delay in (.02, .04, .07, .10, .20):
            with self.subTest(delay=delay):
                camera = CameraReceiver(Mock(), load(CONFIG)['camera'], lambda: 10.,
                                        simulated=True, trace=True)
                rgb = np.zeros((4, 4, 3))
                depth = np.ones((4, 4))
                def enqueue_frame(stamp, local):
                    camera.enqueue('rgb', camera.rgb, (stamp, local, local, rgb))
                    camera.enqueue('depth', camera.depth, (stamp, local, depth, local))
                enqueue_frame(1_000_000_000, 10.)
                camera.enqueue('info', camera.info_stamps, (1_000_000_000, 10., 10.))
                self.assertTrue(camera.take(10.).registered(10., camera.config))
                stamp = 1_066_000_000
                enqueue_frame(stamp, 10.066)
                now = 10.066 + delay
                self.assertIsNone(camera.take(now))
                self.assertEqual(camera.trace[-1]['info_skew_ns'], -66_000_000)
                camera.enqueue('info', camera.info_stamps, (stamp, 10.066, now))
                self.assertTrue(camera.take(now).registered(now, camera.config))
                enqueue_frame(1_400_000_000, 10.4)
                self.assertIsNone(camera.take(10.50))
                preview = camera.take(10.54)
                self.assertIsNone(preview.depth)
                self.assertFalse(preview.registered(10.54, camera.config))

    def test_pending_without_prior_triplet_expires(self):
        r = (100_000_000, 10., 10.)
        self.assertEqual(select_frame([r], [r], [], 10.10, .45, .06)[3], 'waiting')
        self.assertEqual(select_frame([r], [r], [], 10.13, .45, .06)[3], 'missing_info')
        self.assertEqual(select_frame([r], [r], [r], 10.46, .45, .06)[3], 'stale_rgb')

    def test_calibration_publisher_restart_retires_pending_rgb(self):
        camera = CameraReceiver(Mock(), load(CONFIG)['camera'], lambda: 10.)
        camera.endpoints = dict(rgb=b'r', depth=b'd', info=b'i')
        camera.device_name = 'verified'
        camera.device.service_is_ready.return_value = True
        camera.publisher = dict(camera.endpoints, info=b'new').get
        camera.rgb.append((100, 10., 10., None))
        camera.depth.append((100, 10., None, 10.))
        self.assertIsNone(camera.take(10.))
        self.assertFalse(camera.rgb or camera.depth)
        self.assertEqual(camera.source_generation, 1)

    def test_subscription_rejections_exception_and_recovery(self):
        cfg = load(CONFIG)['camera']
        node = Mock()
        node.get_clock().now().nanoseconds = 10_000_000_000
        camera = CameraReceiver(node, cfg, lambda: 10.)
        receive = node.create_subscription.call_args_list[0].args[2]
        msg = Mock(width=cfg['width'], height=cfg['height'], encoding='bgr8')
        msg.header.frame_id = cfg['frame']
        msg.header.stamp.sec, msg.header.stamp.nanosec = 10, 0
        camera.device_name = 'verified'
        camera.endpoints = dict(rgb=b'expected')
        camera.publisher = Mock(side_effect=[None, b'restarted', b'expected', b'expected',
                                             b'expected', b'expected', b'expected'])
        receive(msg, {})
        receive(msg, {})
        msg.header.stamp.sec = 9
        receive(msg, {})
        msg.header.stamp.sec = 10
        msg.encoding = 'bad'
        receive(msg, {})
        msg.encoding = 'bgr8'
        camera.bridge = Mock()
        camera.bridge.imgmsg_to_cv2.side_effect = [ValueError(), RuntimeError(), np.zeros((4, 4, 3))]
        receive(msg, {})
        receive(msg, {})
        self.assertEqual(camera.last_failure['rgb']['exception'], 'RuntimeError')
        receive(msg, {})
        self.assertEqual(camera.counts['rgb'], dict(raw=7, validated=3, rejected=5,
                                                    enqueued=1, duplicates=0, capacity_rejected=0, exceptions=1))
        self.assertEqual(set(camera.rejections['rgb']), {'publisher_identity_mismatch',
                         'source_generation_mismatch', 'stale_header', 'unsupported_encoding',
                         'decode_failure'})
        self.assertEqual(len(camera.rgb), 1)
        depth_callback = node.create_subscription.call_args_list[1].args[2]
        camera.device = None
        depth_callback(msg, {})
        self.assertEqual(camera.rejections['depth']['unsupported_encoding'], 1)
        self.assertFalse(camera.depth)

    def test_unusable_depth_cannot_displace_valid_candidate(self):
        camera = CameraReceiver(Mock(), load(CONFIG)['camera'], lambda: 10.,
                                simulated=True, trace=True)
        camera.rejection_reason = Mock(return_value=None)
        camera.node.get_clock().now().nanoseconds = 10_000_000_000
        msg = Mock(encoding='32FC1')
        msg.header.stamp.sec = 10
        msg.header.stamp.nanosec = 0
        camera.bridge = Mock()
        camera.bridge.imgmsg_to_cv2.side_effect = [np.ones((4, 4)), np.zeros((4, 4))]
        camera.on_depth(msg)
        msg.header.stamp.nanosec = 1
        camera.on_depth(msg)
        self.assertEqual([d[0] for d in camera.depth], [10_000_000_000])
        self.assertEqual(camera.trace[-1]['reason'], 'insufficient_valid_depth')

    def test_repeated_info_before_rgb_preserves_distinct_headers(self):
        partner = (100_000_000, 10., 10.)
        repeated = (200_000_000, 10.1, 10.1)
        info = deque([partner], maxlen=12)
        for _ in range(13):
            append_sample('info', info, repeated, [], 60_000_000)
        self.assertEqual(select_frame([partner], [partner], info, 10.15, .45, .06),
                         (partner, partner, partner, ''))
        self.assertEqual(list(info), [partner, repeated])

    def test_late_old_info_does_not_evict_future_rgb_partner(self):
        pending = [(100_000_000, 10., 10.)]
        partner = (300_000_000, 10.02, 10.02)
        info = deque([partner, pending[0]], maxlen=2)
        self.assertEqual(append_sample('info', info, (1, 9.9, 10.03), pending, 60_000_000), 1)
        self.assertIn(partner, info)
        for offset in (60_000_000, 60_000_001):
            candidate = (partner[0]+offset, 10.02, 10.02)
            result = select_frame([partner], [partner], [candidate], 10.15, .45, .06)
            self.assertEqual(result[3], '' if offset == 60_000_000 else 'info_skew')

    def test_expired_info_does_not_erase_fresh_calibration(self):
        camera = CameraReceiver(Mock(), load(CONFIG)['camera'], lambda: 10.)
        camera.node.get_clock().now().nanoseconds = 10_000_000_000
        camera.info = ('verified',)
        camera.info_stamps.append((9_990_000_000, 9.99, 10.))
        camera.on_info(CameraInfo())
        self.assertEqual(len(camera.info_stamps), 1)
        self.assertEqual(camera.source_generation, 0)

    def test_missing_stale_and_invalid_inputs(self):
        r = (100000000, 10., 10.)
        old = (100000000, 8., 8.)
        for rgb,d,i,bad,reason in [
                (old,[r],[r],False,'stale_rgb'), (r,[old],[r],False,'stale_depth'),
                (r,[],[r],False,'missing_depth'), (r,[r],[],False,'missing_info'),
                (r,[r],[old],False,'stale_info'), (r,[r],[],True,'invalid_calibration'),
                (r,[r],[(200000000,10.)],False,'info_skew')]:
            self.assertEqual(select_frame([rgb],d,i,10.15,.45,.06,bad)[3],reason)

    def test_invalid_calibration_invalidates_pending_identity_and_queues(self):
        camera = CameraReceiver(Mock(), load(CONFIG)['camera'], lambda: 10.)
        camera.info = ('previous calibration',)
        camera.info_stamps.append((10, 10.))
        camera.rgb.append((10, 10., 10., None))
        camera.depth.append((10, 10., None))
        camera.rejection_reason = Mock(return_value=None)
        camera.node.get_clock().now().nanoseconds = 0
        camera.on_info(CameraInfo())
        self.assertTrue(camera.invalid_info)
        self.assertEqual(camera.source_generation, 1)
        self.assertFalse(camera.rgb or camera.depth or camera.info_stamps)

    def test_overflow_and_source_restart(self):
        camera = CameraReceiver(Mock(),load(CONFIG)['camera'],lambda: 10.)
        for k,q in [('rgb',camera.rgb),('depth',camera.depth),('info',camera.info_stamps)]:
            for j in range(q.maxlen+1):
                camera.enqueue(k,q,(j,10.,10.))
            self.assertEqual(camera.overflow[k],1)
        self.assertEqual(camera.last_info_eviction['incoming_ns'], camera.info_stamps.maxlen)
        self.assertNotIn(camera.last_info_eviction['header_ns'], [s[0] for s in camera.info_stamps])
        camera.device_name = 'old'
        camera.publisher = lambda kind: b'new'
        self.assertFalse(camera.refresh_source(10.))
        self.assertFalse(camera.rgb or camera.depth or camera.info_stamps)
        self.assertGreater(camera.source_generation,0)


class PendingTarget(unittest.TestCase):
    def setUp(self):
        self.motion = Mock()
        self.submit = Mock()
        self.w = Workflow(load(CONFIG), self.motion, self.submit, lambda owner,now: owner == 'user')
        self.d = Detection((10,10,20,20),(20,20),1.,300.,10.,.3)
        self.frame = Observation(10.,10.,np.zeros((4,4,3)),np.ones((4,4)),10.,True)
        self.w.detector = Mock()
        self.w.detector.detect.return_value = [self.d]
        self.w.target = self.d
        self.w.target_owner = 'user'
        self.w.tracker.lock(self.d)
        self.w.state = State.TARGET_LOCKED
        self.w.ingest(replace(self.frame,depth=None),10.)
        self.assertEqual(self.w.state,State.PENDING_REVALIDATION)
        self.assertIsNone(self.w.target)

    def test_revalidate_once_without_motion(self):
        with self.assertRaises(ValueError):
            self.w.command('center',{},'user',10.)
        self.w.tick(10.05)
        fresh = replace(self.frame,stamp=10.1,received=10.1,depth_stamp=10.1)
        self.w.ingest(fresh,10.1)
        self.w.ingest(fresh,10.1)
        self.assertEqual(self.w.state,State.TARGET_LOCKED)
        self.assertEqual(self.w.target,self.d)
        self.submit.assert_not_called()

    def test_stale_depth_cannot_revalidate_or_submit_motion(self):
        self.w.ingest(replace(self.frame, stamp=10.1, received=10.1, depth_stamp=9.6), 10.1)
        self.w.tick(10.1)
        self.assertEqual(self.w.state, State.PENDING_REVALIDATION)
        self.assertIsNone(self.w.target)
        self.submit.assert_not_called()

    def test_mismatch_releases_identity(self):
        self.w.detector.detect.return_value = [replace(self.d,hue=90.)]
        self.w.ingest(replace(self.frame,stamp=10.1,received=10.1,depth_stamp=10.1),10.1)
        self.assertEqual(self.w.state,State.DETECTING)
        self.assertIsNone(self.w.target)
        self.submit.assert_not_called()

    def test_timeout_and_recovery(self):
        self.w.ingest(replace(self.frame,stamp=10.5,received=10.5,depth=None),10.5)
        self.assertIsNone(self.w.tracker.target)
        self.w.ingest(replace(self.frame,stamp=10.6,received=10.6,depth_stamp=10.6),10.6)
        self.w.tick(10.6)
        self.assertEqual(self.w.state,State.DETECTING)
        self.submit.assert_not_called()

    def test_source_invalidation_clears_pending(self):
        self.w.camera_offline()
        self.assertIsNone(self.w.tracker.target)
        self.assertIsNone(self.w.revalidate_until)
