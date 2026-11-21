#!/usr/bin/env python3
"""Observe 30 seconds of RGB-D metadata using the dashboard matching rules."""
import argparse
from collections import Counter, deque
import json
import math
from pathlib import Path
import tempfile
import time

import numpy as np
import rclpy
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CameraInfo, Image
import yaml

from dobot_auto_center.rgbd_sync import append_sample, calibration_signature, header_ns, select_frame


def stats(values):
    if not values:
        return None
    return dict(zip(('median', 'p95', 'p99', 'max'), np.percentile(values, (50, 95, 99, 100))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    config = yaml.safe_load((Path(__file__).resolve().parents[1] / 'config/camera.yaml').read_text())
    queues = {k: deque(maxlen=n) for k, n in [('rgb', 8), ('depth', 8), ('info', 12)]}
    latencies = []
    info_matches = 0
    gaps = {k: [] for k in queues}
    previous = {}
    arrivals = Counter()
    overflow = Counter(dict.fromkeys(queues, 0))
    outcomes = Counter()
    skews = {k: [] for k in ('depth', 'info')}
    last_rgb = 0
    invalid_info = False
    calibration = None
    rclpy.init()
    node = rclpy.create_node('rgbd_timing_observer', start_parameter_services=False)
    output = (args.output.open('x') if args.output else
              tempfile.NamedTemporaryFile(mode='w', prefix='rgbd-timing-', suffix='.jsonl', delete=False))
    def record(**fields):
        print(json.dumps(fields), file=output)

    def receive(kind, msg):
        nonlocal invalid_info, calibration
        received = time.monotonic_ns()
        stamp = header_ns(msg.header)
        delay = node.get_clock().now().nanoseconds - stamp
        q = queues[kind]
        arrivals[kind] += 1
        if kind in previous:
            gaps[kind].append((received-previous[kind])/1e6)
        previous[kind] = received
        reason = ''
        if (msg.header.frame_id != config['frame'] or msg.width != config['width']
                or msg.height != config['height']):
            reason = 'geometry'
        elif not 0 <= delay <= config['freshness'] * 1e9:
            reason = 'header_age'
        elif kind == 'info' and not (all(map(math.isfinite, msg.k)) and msg.k[0] > 0 and msg.k[4] > 0):
            reason = 'invalid_calibration'
        elif kind == 'rgb' and stamp <= last_rgb:
            reason = 'superseded'
        if (kind == 'info' and 0 <= delay <= round(config['freshness'] * 1e9)
                and reason in ('', 'invalid_calibration', 'geometry')):
            invalid_info = bool(reason)
            signature = None if invalid_info else calibration_signature(msg)
            if calibration is not None and calibration != signature:
                record(event='calibration_reset', header_ns=stamp,
                       retired_rgb_ns=[r[0] for r in queues['rgb']])
                for queue in queues.values():
                    queue.clear()
            calibration = signature
            if invalid_info:
                q.clear()
        dropped = None
        if not reason:
            dropped = append_sample(kind, q, (stamp, (received-delay)/1e9, received/1e9),
                                    queues['rgb'], round(config['max_depth_skew']*1e9))
            if dropped is not None:
                overflow[kind] += 1
        record(event='arrival', topic=config[kind+'_topic'], frame_id=msg.header.frame_id,
               header_ns=stamp, receive_monotonic_ns=received, header_age_ms=delay/1e6,
               queue_length=len(q), reason=reason or ('local_queue_eviction' if dropped is not None else ''),
               evicted_header_ns=dropped)

    def evaluate():
        nonlocal last_rgb, info_matches
        now = time.monotonic()
        r, d, i, reason = select_frame(queues['rgb'], queues['depth'], queues['info'], now,
                                       config['freshness'], config['max_depth_skew'], invalid_info)
        if not r:
            if reason == 'stale_rgb':
                outcomes[reason] += len(queues['rgb'])
                record(event='drop', reason=reason, headers=[x[0] for x in queues['rgb']])
                queues['rgb'].clear()
            return
        last_rgb = r[0]
        latencies.append((now-r[1])*1000)
        if i and abs(i[0]-r[0]) <= round(config['max_depth_skew']*1e9):
            info_matches += 1
        record(event='match', evaluation_monotonic_ns=round(now*1e9), rgb_ns=r[0], result=reason or 'matched',
               rgb_received_monotonic_ns=round(r[2]*1e9),
               queues={k: len(q) for k, q in queues.items()},
               superseded_rgb_ns=[x[0] for x in queues['rgb'] if x[0] < last_rgb],
               **{k: (dict(header_ns=x[0], received_monotonic_ns=round(x[2]*1e9),
                           skew_ms=(x[0]-r[0])/1e6,
                           receive_delta_ms=(x[2]-r[2])*1000) if x else None)
                  for k, x in [('depth', d), ('info', i)]})
        for k, x in [('depth', d), ('info', i)]:
            if x:
                skews[k].append(abs(x[0]-r[0])/1e6)
        outcomes[reason or 'matched'] += 1
        queues['rgb'] = deque((x for x in queues['rgb'] if x[0] > last_rgb), maxlen=8)

    try:
        # Bind only the message argument. rclpy treats a second argument as MessageInfo.
        def callback(kind):
            def on_message(msg):
                receive(kind, msg)
            return on_message
        for kind in queues:
            node.create_subscription(CameraInfo if kind == 'info' else Image, config[kind+'_topic'],
                                     callback(kind), qos_profile_sensor_data)
        node.create_timer(.025, evaluate)
        end = time.monotonic() + 30
        while time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=.05)
        summary = dict(arrivals=arrivals, outcomes=outcomes, overflow=overflow,
                       matched_percent_of_rgb=(100*outcomes['matched']/arrivals['rgb'] if arrivals['rgb'] else None),
                       absolute_skew_ms={k: stats(v) for k,v in skews.items()},
                       arrival_gap_ms={k: stats(v) for k,v in gaps.items()},
                       rgb_capture_to_evaluation_ms=stats(latencies),
                       camera_info_matches=info_matches,
                       matched_percent_of_evaluated=(100*outcomes['matched']/len(latencies) if latencies else None),
                       camera_info_received=arrivals['info'], file=output.name)
        record(event='summary', **summary)
        print(json.dumps(summary, indent=2))
    finally:
        output.close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
