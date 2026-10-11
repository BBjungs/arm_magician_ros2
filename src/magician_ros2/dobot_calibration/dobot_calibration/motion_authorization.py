"""RAM-only, expiring authorization bound to one surveyed plan and one run."""

from dataclasses import dataclass
import math
import time
import uuid

from .geometry import CalibrationError


ACKNOWLEDGEMENTS = ('operator_confirmed', 'estop_tested', 'workspace_clear',
                    'mount_secure', 'workspace_measured', 'collision_reviewed', 'stop_tested')


@dataclass
class RunAuthorization:
    run_id: str
    plan_fingerprint: str
    purpose: str
    deadline: float
    revoked: bool = False

    @classmethod
    def issue(cls, request, *, run_id, plan_fingerprint, purpose, ttl, now=None):
        missing = [name for name in ACKNOWLEDGEMENTS if request.get(name) is not True]
        if missing:
            raise CalibrationError('OPERATOR_AUTHORIZATION_REQUIRED: ' + ','.join(missing))
        if not plan_fingerprint or request.get('plan_fingerprint') != plan_fingerprint:
            raise CalibrationError('AUTHORIZED_PLAN_MISMATCH')
        if not math.isfinite(ttl) or ttl <= 0:
            raise CalibrationError('AUTHORIZATION_TTL_INVALID')
        return cls(run_id, plan_fingerprint, purpose,
                   (time.monotonic() if now is None else now) + ttl)

    def error(self, *, run_id, plan_fingerprint, purpose, abort=False, now=None):
        if self.revoked:
            return 'AUTHORIZATION_REVOKED'
        if abort:
            return 'ABORT_ACTIVE'
        if (self.run_id, self.plan_fingerprint, self.purpose) != (run_id, plan_fingerprint, purpose):
            return 'AUTHORIZED_PLAN_MISMATCH'
        if (time.monotonic() if now is None else now) >= self.deadline:
            return 'AUTHORIZATION_EXPIRED'
        return ''


def new_run_id():
    return uuid.uuid4().hex
