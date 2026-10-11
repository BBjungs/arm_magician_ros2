"""Automatic acquisition and verification with an injected guarded backend."""

from copy import deepcopy
import threading


class AutomaticCalibration:
    def __init__(self, backend):
        self.backend = backend
        self.lock = threading.RLock()
        self.abort_event = threading.Event()
        self.pause_event = threading.Event()
        self.worker = None
        self.status = {'state': 'IDLE', 'accepted_pose_count': 0, 'total_poses': 10,
                       'dry_run': False, 'production_ready': False, 'reason': ''}

    def snapshot(self):
        with self.lock:
            return deepcopy(self.status)

    def update(self, state, **fields):
        with self.lock:
            self.status.update(state=state, **fields)

    def start(self):
        with self.lock:
            if self.worker and self.worker.is_alive():
                return False, 'Automatic calibration is already running'
            self.abort_event.clear()
            self.pause_event.clear()
            self.status = {'state': 'PREFLIGHT', 'accepted_pose_count': 0, 'total_poses': 10,
                           'dry_run': False, 'production_ready': False, 'reason': ''}
            self.worker = threading.Thread(target=self.run, daemon=True)
            self.worker.start()
        return True, 'Automatic calibration requested'

    def abort(self):
        with self.lock:
            if self.worker is None or not self.worker.is_alive():
                return True, 'Automatic calibration is idle'
            self.abort_event.set()
            self.backend.stop()
        return True, 'Stop requested'

    def pause(self):
        # An in-flight move completes at its validated target; no next move
        # starts. Emergency stop/abort is a separate immediate cancellation.
        self.pause_event.set()
        return True, 'Pause requested at the next stationary checkpoint'

    def resume(self):
        self.pause_event.clear()
        return True, 'Resume requested'

    def checkpoint(self):
        if self.abort_event.is_set():
            raise InterruptedError('Operator abort')
        self.backend.check()
        while self.pause_event.is_set():
            self.update('PAUSED')
            if self.abort_event.wait(0.05):
                raise InterruptedError('Operator abort')
            self.backend.check()

    def run(self):
        result, failure = None, None
        try:
            targets = self.backend.prepare(self.checkpoint)
            if len(targets) != 10:
                raise RuntimeError('Automatic calibration requires exactly ten independent targets')
            # Audit the entire requested sequence before the first command.
            for previous, target in zip(targets, targets[1:]):
                self.checkpoint()
                self.backend.validate(previous, target)
            for index, target in enumerate(targets, 1):
                self.checkpoint()
                self.update('MOVING', current_pose=index, target_xyz_mm=(target[:3, 3] * 1000).tolist())
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
            self.update('SOLVING')
            result = self.backend.solve(self.checkpoint)
            self.checkpoint()
            if result.get('state') != 'CANDIDATE_VERIFIED':
                raise RuntimeError('Automatic solution failed independent/reload verification')
        except Exception as error:
            failure = str(error)
            self.backend.stop()
        finally:
            try:
                self.backend.close()
            except Exception as error:
                failure = 'CLEANUP_FAILED: ' + str(error)
            if self.abort_event.is_set() and failure is None:
                failure = 'Operator abort'
            if failure is not None:
                self.update('SAFE_STOP' if self.abort_event.is_set() else 'FAULT', reason=failure)
            else:
                self.update('CANDIDATE_VERIFIED', result=result,
                            reason='Automatic collection and independent verification passed')
