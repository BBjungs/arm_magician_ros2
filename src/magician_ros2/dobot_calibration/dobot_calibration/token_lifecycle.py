"""Auditable two-pose commissioning token; validation never consumes it."""
from dataclasses import dataclass, field
import inspect
import time
import uuid

@dataclass
class CommissioningToken:
    session_id: str; mount_fingerprint: str; generation: int
    scope: tuple = (1, 2); token_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: str = 'WAITING_START'; consumed: bool = False; revoked: bool = False
    revoke_reason: str = ''; arm_deadline: float = 0.; created: float = field(default_factory=time.monotonic)
    audit: list = field(default_factory=list)
    def event(self, name, **data):
        self.audit.append({'event': name, 'monotonic': time.monotonic(), 'caller': inspect.stack()[1].function, **data})

class TokenLifecycle:
    def __init__(self): self.current = None; self.generation = 0
    def create(self, session_id, mount, ttl):
        self.generation += 1
        token = CommissioningToken(session_id, mount, self.generation, arm_deadline=time.monotonic()+ttl)
        token.event('T2_TOKEN_CREATED'); token.event('T3_TOKEN_STORED'); token.event('T4_ARMED')
        self.current = token; return token
    def validate(self, token, session_id, mount, pose, *, abort=False, pause=False, safe_stop=False):
        if token is None or token is not self.current: return 'TOKEN_MISSING'
        token.event('T6_TOKEN_VALIDATE', pose=pose)
        if token.revoked: return 'TOKEN_REVOKED'
        if token.consumed: return 'TOKEN_ALREADY_CONSUMED'
        if token.generation != self.generation: return 'TOKEN_GENERATION_MISMATCH'
        if token.session_id != session_id: return 'TOKEN_SESSION_MISMATCH'
        if token.mount_fingerprint != mount: return 'TOKEN_FINGERPRINT_MISMATCH'
        if pose not in token.scope: return 'POSE_NOT_ALLOWED'
        if abort: return 'ABORT_ACTIVE'
        if pause: return 'PAUSE_ACTIVE'
        if safe_stop: return 'SAFE_STOP_ACTIVE'
        if token.state == 'WAITING_START' and time.monotonic() >= token.arm_deadline: return 'TOKEN_EXPIRED'
        if token.state not in ('WAITING_START','ACTIVE_RUN'): return 'TOKEN_REVOKED'
        return ''
    def activate(self, token): token.state='ACTIVE_RUN'; token.event('POSE_1_ACTIVE_RUN')
    def revoke(self, token, reason):
        if token: token.revoked=True; token.state='REVOKED'; token.revoke_reason=reason; token.event('REVOKE', reason=reason)
