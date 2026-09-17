"""Safety-supervised automatic calibration state machine.

Real motion is deliberately unavailable until the complete dry-run plan passes.
"""

from dataclasses import dataclass, field
import threading
import time


STATES = ('IDLE', 'PREFLIGHT', 'MOVING', 'SETTLING', 'CAPTURING',
          'VALIDATING', 'NEXT_POSE', 'SOLVING', 'VALIDATING_SOLUTION',
          'COMPLETE', 'SAFE_STOP', 'PAUSED', 'FAULT')


@dataclass
class AutoStatus:
    state: str = 'IDLE'
    dry_run: bool = True
    real_motion_enabled: bool = False
    current_pose: int = 0
    total_poses: int = 10
    target: dict | None = None
    readiness: str = ''
    safety_status: str = ''
    motion_progress: float = 0.0
    capture_result: str = ''
    registration_quality: dict = field(default_factory=dict)
    blockers: list = field(default_factory=list)
    history: list = field(default_factory=list)

    def as_dict(self):
        return {
            'state': self.state, 'dry_run': self.dry_run,
            'real_motion_enabled': self.real_motion_enabled,
            'current_pose': self.current_pose, 'total_poses': self.total_poses,
            'target': self.target, 'readiness': self.readiness,
            'safety_status': self.safety_status,
            'motion_progress': self.motion_progress,
            'capture_result': self.capture_result,
            'registration_quality': self.registration_quality,
            'blockers': list(self.blockers), 'history': list(self.history),
        }


class SupervisedAutoCalibration:
    """Orchestrates gates only; motion is injected only after explicit enablement."""

    def __init__(self, preflight, validate_target, *, real_motion_enabled=False):
        self.preflight = preflight
        self.validate_target = validate_target
        self.real_motion_enabled = bool(real_motion_enabled)
        self.status = AutoStatus(real_motion_enabled=self.real_motion_enabled)
        self._pause = threading.Event()
        self._abort = threading.Event()
        self._lock = threading.Lock()
        self.worker = None

    def snapshot(self):
        with self._lock:
            return self.status.as_dict()

    def _transition(self, state, **values):
        if state not in STATES:
            raise ValueError('Unknown supervised calibration state')
        with self._lock:
            self.status.state = state
            for key, value in values.items():
                setattr(self.status, key, value)
            self.status.history.append({'state': state, 'time': time.time()})

    def start(self, targets, accepted_count=0, dry_run=True):
        if self.worker and self.worker.is_alive():
            return False, 'Supervised calibration is already running'
        if not dry_run and not self.real_motion_enabled:
            return False, 'Real automatic calibration is disabled until dry-run passes'
        self._pause.clear()
        self._abort.clear()
        self.status = AutoStatus(dry_run=bool(dry_run),
                                 real_motion_enabled=self.real_motion_enabled,
                                 current_pose=int(accepted_count),
                                 total_poses=len(targets))
        self.worker = threading.Thread(target=self._run,
                                       args=(list(targets), int(accepted_count)),
                                       daemon=True)
        self.worker.start()
        return True, 'Supervised dry-run started' if dry_run else 'Supervised calibration started'

    def pause(self):
        self._pause.set()
        return True, 'Pause requested'

    def resume(self):
        self._pause.clear()
        return True, 'Resume requested'

    def abort(self):
        self._abort.set()
        return True, 'Abort requested; no new motion may start'

    def _checkpoint(self):
        if self._abort.is_set():
            self._transition('SAFE_STOP', blockers=['Operator abort'])
            return False
        while self._pause.is_set():
            self._transition('PAUSED')
            if self._abort.wait(0.05):
                self._transition('SAFE_STOP', blockers=['Operator abort while paused'])
                return False
        return True

    def _run(self, targets, accepted_count):
        try:
            self._transition('PREFLIGHT')
            blockers, readiness = self.preflight()
            if blockers:
                self._transition('FAULT', blockers=list(blockers), readiness=readiness,
                                 safety_status='PREFLIGHT_FAILED')
                return
            for index in range(accepted_count, len(targets)):
                if not self._checkpoint():
                    return
                target = targets[index]
                self._transition('PREFLIGHT', current_pose=index + 1, target=target,
                                 readiness='READY', safety_status='CHECKING_TARGET')
                blockers = self.validate_target(target)
                if blockers:
                    self._transition('FAULT', blockers=list(blockers),
                                     safety_status='TARGET_REJECTED')
                    return
                self._transition('MOVING', motion_progress=0.0,
                                 safety_status='DRY_RUN_NO_MOTION')
                if not self.status.dry_run:
                    raise RuntimeError('Real-motion adapter has not been commissioned')
                self._transition('SETTLING', motion_progress=1.0,
                                 safety_status='DRY_RUN_SIMULATED')
                self._transition('CAPTURING', capture_result='DRY_RUN_NOT_CAPTURED')
                self._transition('VALIDATING', registration_quality={'status': 'DRY_RUN'})
                self._transition('NEXT_POSE')
            self._transition('SOLVING', capture_result='DRY_RUN_NO_DATASET_MUTATION')
            self._transition('VALIDATING_SOLUTION')
            self._transition('COMPLETE', safety_status='DRY_RUN_PASS')
        except Exception as error:
            self._transition('FAULT', blockers=[str(error)], safety_status='EXCEPTION')
