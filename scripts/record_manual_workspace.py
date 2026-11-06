#!/usr/bin/env python3
"""Record manually moved robot telemetry with HTTP GET only; never authorize motion."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import urllib.request


def finite_vector(value, length):
    return (isinstance(value, list) and len(value) == length
            and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                    and math.isfinite(v) for v in value))


def fresh(age):
    return isinstance(age, (int, float)) and math.isfinite(age) and 0 <= age <= .5


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=600.)
    args = parser.parse_args()
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error('duration must be positive and finite')
    args.output.mkdir(parents=True, exist_ok=False)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    summary = {
        'state': 'RECORDING', 'started_utc': datetime.now(timezone.utc).isoformat(),
        'duration_limit_s': args.duration, 'source': 'GET /api/status',
        'classification': 'OBSERVED_TCP_RANGE_NOT_CERTIFIED_FREE_VOLUME',
        'frame': 'magician_base_link', 'xyz_units': 'mm', 'angle_units': 'deg',
        'recorder_sent_motion_command': False, 'samples': 0, 'accepted_samples': 0,
        'rejected_samples': 0, 'request_errors': 0, 'alarm_samples': 0,
        'tcp_min_mm_deg': None, 'tcp_max_mm_deg': None,
        'joint_min_deg': None, 'joint_max_deg': None,
    }

    def save():
        summary['updated_utc'] = datetime.now(timezone.utc).isoformat()
        tmp = args.output / 'summary.tmp'
        tmp.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
        tmp.replace(args.output / 'summary.json')

    def extend(name, values):
        low, high = name
        if summary[low] is None:
            summary[low], summary[high] = list(values), list(values)
        else:
            summary[low] = [min(a, b) for a, b in zip(summary[low], values)]
            summary[high] = [max(a, b) for a, b in zip(summary[high], values)]

    start = time.monotonic()
    save()
    try:
        with (args.output / 'samples.jsonl').open('x', buffering=1) as stream:
            while time.monotonic() - start < args.duration:
                if (args.output / 'STOP').exists():
                    summary['stop_reason'] = 'operator_requested'
                    break
                tick = time.monotonic()
                record = {'utc': datetime.now(timezone.utc).isoformat(),
                          'elapsed_s': tick - start}
                try:
                    with opener.open('http://127.0.0.1:8080/api/status', timeout=3) as response:
                        status = json.load(response)
                    motion, ros = status.get('motion', {}), status.get('ros', {})
                    pose, joints = motion.get('current_tcp_pose'), motion.get('joints_deg')
                    issues = []
                    if not finite_vector(pose, 4) or not fresh(motion.get('current_tcp_pose_age_sec')):
                        issues.append('TCP_INVALID_OR_STALE')
                    if not finite_vector(joints, 4) or not fresh(motion.get('joints_age_sec')):
                        issues.append('JOINTS_INVALID_OR_STALE')
                    if ros.get('alarm_codes'):
                        summary['alarm_samples'] += 1
                        issues.append('ALARM_ACTIVE')
                    if (ros.get('alarm_state_fresh') is not True
                            or ros.get('no_critical_alarm') is not True
                            or ros.get('alarm_codes') != []):
                        issues.append('ALARM_CLEAR_NOT_CONFIRMED')
                    record.update(motion=motion, ros=ros, accepted=not issues, issues=issues)
                    summary['samples'] += 1
                    summary['last_tcp_mm_deg'] = pose
                    summary['last_alarm_codes'] = ros.get('alarm_codes')
                    summary['last_issues'] = issues
                    if issues:
                        summary['rejected_samples'] += 1
                    else:
                        summary['accepted_samples'] += 1
                        extend(('tcp_min_mm_deg', 'tcp_max_mm_deg'), pose)
                        extend(('joint_min_deg', 'joint_max_deg'), joints)
                    summary['last_success_elapsed_s'] = time.monotonic() - start
                except Exception as error:
                    record.update(accepted=False, error=str(error))
                    summary['request_errors'] += 1
                    summary['last_issues'] = ['REQUEST_FAILED: ' + str(error)]
                stream.write(json.dumps(record, allow_nan=False) + '\n')
                summary['elapsed_s'] = time.monotonic() - start
                save()
                time.sleep(max(0., .2 - (time.monotonic() - tick)))
            else:
                summary['stop_reason'] = 'duration_limit'
        summary['state'] = 'STOPPED'
    except BaseException as error:
        summary['state'] = 'INTERRUPTED'
        summary['stop_reason'] = type(error).__name__
        raise
    finally:
        summary['elapsed_s'] = time.monotonic() - start
        save()


if __name__ == '__main__':
    main()
