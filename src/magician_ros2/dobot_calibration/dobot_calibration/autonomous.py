"""Automatic acquisition and verification with an injected guarded backend."""

from contextlib import contextmanager
from copy import deepcopy
import threading
import time

from .motion_authorization import new_run_id
from .geometry import CalibrationError


class AutomaticCalibration:
    def __init__(self, backend):
        self.backend = backend
        self.lock = threading.RLock()
        self.abort_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.dispatch_lock = threading.RLock()
        self.authorization_event = threading.Event()
        self.authorization_request = None
        self.run_id = new_run_id()
        self.purpose = 'AUTONOMOUS_10_POSES'
        self.status = {'state': 'IDLE', 'accepted_pose_count': 0, 'total_poses': 10,
                       'dry_run': False, 'production_ready': False, 'reason': '',
                       'authorization_protocol': 2}

    def snapshot(self):
        with self.lock:
            return deepcopy(self.status)

    def update(self, state, **fields):
        with self.lock:
            self.status.update(state=state, **fields)

    def start(self, purpose='AUTONOMOUS_10_POSES'):
        if purpose not in ('AUTONOMOUS_10_POSES', 'COMMISSIONING_TWO_POSES'):
            return False, 'Unknown calibration scope'
        with self.lock:
            if self.worker and self.worker.is_alive():
                return False, 'Automatic calibration is already running'
            self.run_id = new_run_id()
            self.purpose = purpose
            self.authorization_event.clear()
            self.authorization_request = None
            self.abort_event.clear()
            self.pause_event.clear()
            self.status = {'state': 'PREFLIGHT', 'accepted_pose_count': 0, 'total_poses': 10,
                           'dry_run': False, 'production_ready': False, 'reason': '',
                           'purpose': purpose, 'run_id': self.run_id, 'motion_command_sent': False,
                           'blockers': [], 'trace': [], 'authorization_protocol': 2}
            self.worker = threading.Thread(target=self.run, daemon=True)
            self.worker.start()
        return True, 'Automatic calibration requested'

    def trace(self, function, **fields):
        with self.lock:
            self.status.setdefault('trace', []).append(
                {'function': function, 'monotonic': time.monotonic(), **fields})

    def authorize(self, request):
        with self.lock:
            if (self.status['state'] != 'WAITING_FOR_OPERATOR_AUTHORIZATION'
                    or self.authorization_request is not None or self.abort_event.is_set()):
                return False, 'No unclaimed validated plan is waiting for authorization'
            from .motion_authorization import RunAuthorization
            try:
                # Reject an invalid confirmation synchronously; worker rechecks
                # all live interlocks before applying controller parameters.
                RunAuthorization.issue(request, run_id=self.run_id,
                    plan_fingerprint=self.status.get('plan_fingerprint'),
                    purpose=self.purpose, ttl=1.)
            except CalibrationError as error:
                return False, str(error)
            self.authorization_request = deepcopy(request)
            self.authorization_event.set()
            return True, 'Operator authorization submitted; inspect the live result'

    def wait_authorization(self, checkpoint, timeout):
        deadline = time.monotonic() + timeout
        while not self.authorization_event.wait(.05):
            checkpoint()
            if time.monotonic() >= deadline:
                raise CalibrationError('OPERATOR_AUTHORIZATION_EXPIRED')
        checkpoint()
        return deepcopy(self.authorization_request)

    def abort(self):
        # Latch before cancellation, including while an action acceptance is pending.
        self.abort_event.set()
        with self.dispatch_lock:
            self.backend.stop()
        return True, 'Stop requested; physical stop must be verified from feedback'

    def pause(self):
        with self.dispatch_lock:
            self.pause_event.set()
        return True, 'Pause requested at the next stationary checkpoint'

    def resume(self):
        with self.dispatch_lock:
            self.pause_event.clear()
        return True, 'Resume requested; authorization and live gates are rechecked'

    @contextmanager
    def dispatch_guard(self):
        # Serialize only the irreversible send with pause/abort, never a long
        # action wait. A pause during path validation cannot leak a new goal.
        while True:
            self.checkpoint()
            with self.dispatch_lock:
                if self.abort_event.is_set():
                    raise InterruptedError('Operator abort')
                if self.pause_event.is_set():
                    continue
                self.backend.check()
                yield
                return

    def checkpoint(self):
        if self.abort_event.is_set():
            raise InterruptedError('Operator abort')
        self.backend.check()
        previous = self.snapshot()['state']
        was_paused = self.pause_event.is_set()
        while self.pause_event.is_set():
            self.update('PAUSED')
            if self.abort_event.wait(0.05):
                raise InterruptedError('Operator abort')
            self.backend.check()
        if was_paused:
            self.update(previous)

    def run(self):
        result, failure = None, None
        try:
            self.trace('AutomaticBackend.prepare')
            targets = self.backend.prepare(self.checkpoint)
            if len(targets) != 10:
                raise RuntimeError('Automatic calibration requires exactly ten independent targets')
            # Audit the entire requested sequence before the first command.
            for previous, target in zip(targets, targets[1:]):
                self.checkpoint()
                self.trace('AutomaticBackend.validate')
                self.backend.validate(previous, target)
            self.backend.wait_for_authorization(self.checkpoint)
            selected = targets[:2] if self.purpose == 'COMMISSIONING_TWO_POSES' else targets
            for index, target in enumerate(selected, 1):
                self.checkpoint()
                self.update('MOVING', current_pose=index, target_xyz_mm=(target[:3, 3] * 1000).tolist())
                self.trace('AutomaticBackend.move', pose=index)
                self.backend.move(target)
                self.checkpoint()
                self.update('SETTLING')
                self.backend.settle(target, self.checkpoint)
                self.checkpoint()
                self.update('CAPTURING')
                capture = self.backend.capture(target)
                self.checkpoint()
                self.update('VALIDATING_CAPTURE')
                self.backend.accept(capture, index)
                self.update('NEXT_POSE', accepted_pose_count=index)
            self.checkpoint()
            if self.purpose == 'COMMISSIONING_TWO_POSES':
                result = self.backend.commissioning_result()
            else:
                self.update('SOLVING')
                result = self.backend.solve(self.checkpoint)
            self.checkpoint()
            expected = 'COMMISSIONING_COMPLETE' if self.purpose == 'COMMISSIONING_TWO_POSES' else 'CANDIDATE_VERIFIED'
            if result.get('state') != expected:
                raise RuntimeError('Automatic solution failed independent/reload verification')
        except Exception as error:
            failure = str(error)
            try:
                self.backend.stop()
            except Exception as stop_error:
                failure += '; SAFE_STOP_FAILED: ' + str(stop_error)
        finally:
            try:
                self.backend.close()
            except Exception as error:
                failure = 'CLEANUP_FAILED: ' + str(error)
            if self.abort_event.is_set() and failure is None:
                failure = 'Operator abort'
            if failure is None and self.purpose == 'COMMISSIONING_TWO_POSES':
                try:
                    self.backend.record_commissioning(result)
                except Exception as error:
                    failure = str(error)
            if failure is not None:
                self.update('SAFE_STOP' if self.abort_event.is_set() else 'FAULT', reason=failure,
                            blockers=list(dict.fromkeys(self.snapshot().get('blockers', []) + [failure])))
            else:
                self.update(result['state'], result=result,
                            reason=('Two real poses acquired and PTP parameters restored; authorize ten poses separately'
                                    if self.purpose == 'COMMISSIONING_TWO_POSES' else
                                    'Automatic collection and independent verification passed'))
            try:
                self.backend.persist_status(self.snapshot())
            except Exception as error:
                self.update('FAULT', reason='AUDIT_PERSISTENCE_FAILED: ' + str(error))
