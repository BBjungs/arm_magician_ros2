"""Web workflow orchestration. All readiness decisions remain on the server."""

import copy
import json
import math
import threading
import time
from pathlib import Path

import yaml

from dobot_web_interface.calibration_guide import board_guide, validate_measurements


MESSAGES = {
    'camera': ('Camera ready', 'Camera unavailable', 'Connect the camera and wait for a live image.'),
    'calibration': ('Calibration complete', 'Calibration required', 'Place the printed board and press Calibrate.'),
    'yolo': ('Detector ready', 'Detector not ready', 'Check the detector in Settings, then Detect again.'),
    'target': ('Target valid', 'No object detected', 'Place an object in view and press Detect.'),
    'confidence': ('Confidence passed', 'Confidence too low', 'Improve lighting or separate the objects, then Detect again.'),
    'workspace': ('Inside workspace', 'Target outside workspace', 'Move the object into the work area; check the destination in Settings.'),
    'place': ('Destination ready', 'Destination is not configured', 'Ask the operator to configure a destination for this object in Settings.'),
    'tcp_pose': ('TCP valid', 'Robot position unavailable', 'Wait for fresh robot position data; check the connection.'),
    'look_down_pose': ('Camera pose valid', 'Camera pose unsuitable', 'Return the camera to its calibrated viewing position.'),
    'homing': ('Home confirmed', 'Dobot needs Home', 'Clear the robot work area, then press Home.'),
    'dry_run': ('Motion permission passed', 'Real picking is disabled', 'Complete supervised commissioning with the operator before enabling real picking in deployment settings.'),
    'robot': ('Dobot ready', 'Dobot not ready', 'Check the robot connection and wait for any current motion to finish.'),
    'alarms': ('No robot alarms', 'Robot alarm or alarm data unavailable', 'Check the robot and resolve alarms before continuing.'),
    'tool': ('Tool ready', 'Tool unavailable', 'Connect and verify the configured picking tool in Settings.'),
    'depth': ('Depth valid', 'Invalid depth', 'Place the object within camera range and avoid reflective surfaces.'),
    'fresh_target': ('Target is current', 'Target changed or expired', 'Keep the object still and press Detect again.'),
    'setup': ('Setup unchanged', 'Setup changed', 'Calibrate if the camera or board moved, then Detect again.'),
    'intrinsics': ('Camera measurements ready', 'Camera information unavailable', 'Wait for live camera information; check the camera connection.'),
}


def fresh(value, limit):
    return isinstance(value, (float, int)) and math.isfinite(value) and 0 <= value <= limit


def finite_pose(value):
    return isinstance(value, (list, tuple)) and len(value) == 4 and all(
        isinstance(x, (float, int)) and not isinstance(x, bool) and math.isfinite(x) for x in value)


def check(name, ok):
    passed, failed, action = MESSAGES[name]
    return {'name': name, 'ok': bool(ok), 'label': passed if ok else failed,
            'action': '' if ok else action, 'color': 'green' if ok else 'red'}


def same_target(a, b):
    if not a or not b or not a.get('selected') or not b.get('selected'):
        return False
    for key in ('id', 'class_name', 'place_id', 'vision_mode'):
        if a.get(key) != b.get(key):
            return False
    for key, tolerance in [('pick_pose', 1.0), ('place_pose', .01), ('center_pixel', 2.0)]:
        av, bv = a.get(key, []), b.get(key, [])
        if not av or len(av) != len(bv):
            return False
        if any(not math.isfinite(float(x)) or not math.isfinite(float(y)) or abs(float(x) - float(y)) > tolerance
               for x, y in zip(av, bv)):
            return False
    return True


class OperationWorkflow:
    def __init__(self, node, aruco_lock):
        self.node = node
        self.aruco_lock = aruco_lock
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.busy = None
        self.phase = 'CONNECTING'
        self.stage = 0
        self.target = None
        self.target_time = 0.0
        self.target_setup = None
        self.request = None
        self.measurements = [None, None]
        self.fixture_confirmed = False
        self.guide = None
        self.logs = []
        self.error = None

    def record(self, message):
        with self.lock:
            self.logs.append({'time': time.time(), 'message': str(message)})
            self.logs = self.logs[-100:]

    def calibration(self):
        n = self.node
        result = (n.vision_eye_in_hand_status() if n.vision_mode == 'eye_in_hand'
                  else n.vision_calibration())
        valid = (result.get('is_complete') is True and not result.get('position_estimate')
                 and not result.get('validation_errors') and not result.get('validation', {}).get('warning'))
        return result, valid

    def board(self):
        n = self.node
        return (n._eye_in_hand().load()['aruco']['board'] if n.vision_mode == 'eye_in_hand'
                else n._calibration().load()['auto_calibration']['board'])

    def setup_signature(self):
        n = self.node
        intrinsics = n._current_intrinsics()
        # Timestamps and runtime attempts are not calibration changes.
        intrinsics = {key: value for key, value in intrinsics.items()
                      if key not in ('stamp', 'timestamp', 'age_sec', 'updated_at')}
        return json.dumps([n.vision_mode, n._eye_in_hand().load(), n._calibration().load(),
                           intrinsics, n._safety().config.as_dict(), n._places().status().get('places')],
                          sort_keys=True, default=str)

    def base_checks(self):
        status = self.node.status()
        camera, motion, ros = status['camera'], status['motion'], status['ros']
        _, calibrated = self.calibration()
        return [check('camera', camera.get('has_frame') and fresh(camera.get('frame_age_sec'), 2)),
                check('calibration', calibrated),
                check('tcp_pose', finite_pose(motion.get('current_tcp_pose'))
                      and fresh(motion.get('current_tcp_pose_age_sec'), .5)),
                check('robot', ros.get('ptp_action_ready') and ros.get('validation_ready')
                      and not motion.get('active_goal') and not motion.get('vision_sequence_active')),
                check('alarms', motion.get('alarms') == [] and fresh(motion.get('alarms_age_sec'), 2)),
                check('tool', ros.get('suction_ready')),
                check('intrinsics', camera.get('intrinsics_source') == 'camera_info'
                      and fresh(camera.get('intrinsics_age_sec'), 5))]

    def selection_checks(self, selected, expected=None):
        report = self.node._safety_report({'selected_target': selected, 'dry_run': False})
        checks = {item['name']: check(item['name'], item['ok'])
                  for item in report['checks'] if item['name'] in MESSAGES}
        for item in self.base_checks():
            # A stricter freshness check must never replace a failed existing guard.
            if item['name'] in checks:
                item = check(item['name'], item['ok'] and checks[item['name']]['ok'])
            checks[item['name']] = item
        detections = self.node.vision_detections()
        source = next((d for d in detections.get('detections', [])
                       if str(d.get('id', d.get('detection_id'))) == str(selected.get('id'))
                       and d.get('class_name') == selected.get('class_name')), {})
        depth = source.get('depth_mm')
        # A fixed-plane estimate does not substitute for a missing depth measurement.
        checks['depth'] = check('depth', source.get('depth_valid') is True
                                and isinstance(depth, (float, int)) and math.isfinite(depth) and depth > 0
                                and source.get('pick_eligible') is not False)
        checks['fresh_target'] = check('fresh_target', detections.get('ok') and bool(source)
                                      and time.monotonic() - self.target_time <= 15
                                      and (expected is None or same_target(expected, selected)))
        checks['setup'] = check('setup', self.target_setup == self.setup_signature())
        allowed = report.get('allowed') is True and all(item['ok'] for item in checks.values())
        if not report.get('allowed') and all(item['ok'] for item in checks.values()):
            checks['backend'] = {'name': 'backend', 'ok': False, 'label': 'Safety validation failed',
                                 'action': 'Review the safety report in Settings.', 'color': 'red'}
        return list(checks.values()), allowed

    def validate_selected(self, selected):
        with self.lock:
            expected = copy.deepcopy(self.target)
        checks, allowed = self.selection_checks(selected, expected)
        if not allowed:
            raise ValueError('; '.join(item['label'] for item in checks if not item['ok']))

    def snapshot(self):
        with self.lock:
            phase, busy, target, request, error = self.phase, self.busy, copy.deepcopy(self.target), self.request, self.error
            stage = self.stage
            guide = self.guide
        checks = self.base_checks()
        allowed = False
        if target and not busy:
            try:
                current = self.node._select_target_preview_source(request)
                checks, allowed = self.selection_checks(current, target)
                target = current if same_target(target, current) else target
            except (ValueError, RuntimeError, ConnectionError, KeyError) as exc:
                checks.append(check('fresh_target', False))
                error = 'Target unavailable. Keep the object still and press Detect again.'
                self.record_once(exc)
            phase = 'READY_TO_PICK' if allowed else 'TARGET_INVALID'
        elif not busy and phase not in ('PICK_COMPLETE', 'ERROR', 'TARGET_INVALID'):
            phase = ('NEED_CAMERA' if not checks[0]['ok'] else
                     'NEED_CALIBRATION' if not checks[1]['ok'] else 'CALIBRATION_OK')
        ready = allowed and not busy and phase == 'READY_TO_PICK'
        return {'state': phase, 'ready_to_pick': ready, 'checks': checks,
                'failures': [item for item in checks if not item['ok']],
                'calibration_valid': checks_by_name(checks, 'calibration'),
                'calibration_stage': stage, 'measurement_required': busy == 'CALIBRATING' and stage == 2,
                'measurement_axis': next((i for i, v in enumerate(self.measurements) if v is None), 1),
                'fixture_confirmed': self.fixture_confirmed,
                'guide_available': guide is not None, 'instruction': guide.get('instruction', '') if guide else '',
                'busy': busy, 'error': error,
                'target': ({'object': target.get('class_name'), 'pose': target.get('pick_pose'),
                            'confidence': target.get('confidence'), 'center_pixel': target.get('center_pixel')}
                           if target else None),
                'recommended_action': 'pick' if ready else 'calibrate' if phase == 'NEED_CALIBRATION' else
                                      'detect' if phase in ('CALIBRATION_OK', 'TARGET_INVALID', 'PICK_COMPLETE') else None}

    def record_once(self, message):
        with self.lock:
            if not self.logs or self.logs[-1]['message'] != str(message):
                self.record(message)

    def start(self, operation):
        with self.lock:
            if self.busy:
                raise ValueError('An operation is already running')
            if operation == 'calibrate' and self.calibration()[1]:
                self.phase = 'CALIBRATION_OK'
                self.record('Reused valid stored calibration')
                return {'accepted': True, 'reused': True}
            if operation == 'pick':
                if not self.snapshot()['ready_to_pick']:
                    raise ValueError('Not ready to pick. Resolve the failed checks first')
            elif operation not in ('calibrate', 'detect'):
                raise ValueError('Unknown operation')
            self.stop.clear()
            self.error = None
            self.busy = {'calibrate': 'CALIBRATING', 'detect': 'SEARCHING_TARGET', 'pick': 'PICKING'}[operation]
            self.phase = self.busy
            if operation != 'pick':
                self.target = None
                self.request = None
            if operation == 'calibrate':
                self.measurements = [None, None]
                self.fixture_confirmed = False
                self.stage = 0
                self.guide = None
            threading.Thread(target=self._run, args=(operation,), daemon=True).start()
        return {'accepted': True}

    def _run(self, operation):
        try:
            getattr(self, '_' + operation)()
        except Exception as exc:
            # Worker exceptions must be visible, and must revoke any ready target.
            self.record(exc)
            with self.lock:
                self.phase = 'ERROR'
                self.target = None
                self.error = ('Calibration could not finish. Keep the board visible and robot still, then retry.'
                              if operation == 'calibrate' else
                              'Operation could not finish. Check the failed conditions and retry; details are in Logs.')
        finally:
            with self.lock:
                self.busy = None

    def _calibrate(self):
        setup = self.setup_signature()
        deadline = time.monotonic() + 300
        while not self.stop.is_set() and time.monotonic() < deadline:
            if setup != self.setup_signature():
                raise ValueError('Calibration settings changed during wizard; restart calibration')
            if not self.base_checks()[0]['ok']:
                self.stage = 0
                self.stop.wait(.5)
                continue
            frame = self.node._latest_cv_frame()
            if frame is None:
                self.stop.wait(.5)
                continue
            with self.lock:
                measured = all(value is not None for value in self.measurements)
                axis = next((i for i, value in enumerate(self.measurements) if value is None), 1)
            with self.aruco_lock:
                guide = board_guide(frame, self.board(), measured, axis)
            with self.lock:
                self.guide = guide
                self.stage = 1 if guide['missing_ids'] else 2
            if not guide['missing_ids'] and measured and self.fixture_confirmed:
                self.stage = 3
                result = self.node.vision_auto_calibrate({'dry_run': True, 'vision_mode': self.node.vision_mode,
                                                          'fixture_measured': True})
                if not self.calibration()[1]:
                    self.record(result)
                    raise ValueError('Multi-frame calibration validation failed')
                self.stage = 4
                self.phase = 'CALIBRATION_OK'
                self.record('Calibration complete: measured board, stationary multi-frame solve passed')
                return
            self.stop.wait(.7)
        if self.stop.is_set():
            self.phase = 'NEED_CALIBRATION'
        else:
            raise ValueError('Calibration wizard timed out after five minutes')

    def measure(self, payload):
        with self.lock:
            if self.busy != 'CALIBRATING' or self.stage != 2 or not self.guide or self.guide['missing_ids']:
                raise ValueError('Keep every marker visible before measuring')
            axis = payload.get('axis')
            if isinstance(axis, bool) or axis not in (0, 1):
                raise ValueError('Invalid measurement')
            expected_axis = next((i for i, value in enumerate(self.measurements) if value is None), 1)
            if axis != expected_axis or self.guide['measurement']['axis'] != axis:
                raise ValueError('Wait for the next measurement guide')
            values = list(self.measurements)
            values[axis] = payload.get('mm')
            # Validate each entry against the matching drawn span.
            from dobot_web_interface.calibration_guide import measurement_spans
            pending = [span['expected_mm'] if value is None else value
                       for span, value in zip(measurement_spans(self.board()), values)]
            validate_measurements(self.board(), pending)
            self.measurements[axis] = float(values[axis])
            if payload.get('fixture_confirmed') is True:
                self.fixture_confirmed = True
            return {'accepted': True}

    def _detect(self):
        _, valid = self.calibration()
        if not valid:
            self.phase = 'NEED_CALIBRATION'
            return
        before = self.node.vision_detections().get('stamp')
        self.node.vision_detect_once({'dry_run': True})
        deadline = time.monotonic() + 10
        detections = {}
        while not self.stop.is_set() and time.monotonic() < deadline:
            detections = self.node.vision_detections()
            if detections.get('ok') and detections.get('stamp') != before:
                break
            self.stop.wait(.1)
        else:
            raise ValueError('No new detection frame arrived')
        items = detections.get('detections', [])
        if not items:
            self.phase = 'TARGET_INVALID'
            self.error = 'No object detected. Place an object in view and press Detect.'
            return
        data = yaml.safe_load(Path(self.node.vision_yolo_config_path).read_text()) or {}
        mapping = data.get('target_selector_node', {}).get('ros__parameters', {}).get('class_to_place', {})
        eligible = [d for d in items if d.get('pick_eligible') is not False]
        if not eligible:
            self.phase = 'TARGET_INVALID'
            self.error = 'No valid object depth or shape. Adjust lighting and camera distance, then Detect again.'
            return
        target = max(eligible, key=lambda d: float(d.get('confidence', 0)))
        place = mapping.get(target.get('class_name'))
        if not place:
            self.phase = 'TARGET_INVALID'
            self.error = 'Destination is not configured for this object. Ask the operator to set it in Settings.'
            return
        request = {'dry_run': True, 'vision_mode': self.node.vision_mode, 'object_class': target['class_name'],
                   'place_id': place, 'selection_mode': 'manual_id', 'manual_id': target.get('id', target.get('detection_id'))}
        selected = self.node.vision_select_target(request)
        if not selected.get('selected'):
            raise ValueError(selected.get('reason', 'Target selection failed'))
        with self.lock:
            self.target = selected
            self.request = request
            self.target_time = time.monotonic()
            self.target_setup = self.setup_signature()
            self.phase = 'TARGET_FOUND'
        checks, allowed = self.selection_checks(selected, selected)
        self.phase = 'READY_TO_PICK' if allowed else 'TARGET_INVALID'
        self.record('Detect completed: ' + ', '.join(item['label'] for item in checks if not item['ok']))

    def _pick(self):
        # Clicking Pick is explicit intent; it cannot enable motion permissions.
        payload = dict(self.request, dry_run=False, confirm_real_motion=True,
                       _workflow_expected_target=copy.deepcopy(self.target))
        result = self.node.vision_pick_selected(payload)
        if not result.get('executed'):
            raise ValueError(result.get('reason', 'Pick was rejected'))
        with self.lock:
            self.target = None
            self.phase = 'PICK_COMPLETE'
        self.record('Pick complete')

    def cancel(self):
        self.stop.set()
        with self.lock:
            self.target = None
        return self.node.vision_cancel()


def checks_by_name(checks, name):
    return next((item['ok'] for item in checks if item['name'] == name), False)
