"""Least-privilege real-motion gate for calibration commissioning.

The adapter owns the decision to dispatch a calibration PTP action.  Transport
is injected so the identical policy can be tested without ROS or hardware.
"""

from dataclasses import dataclass


class RealMotionRejected(RuntimeError):
    pass


@dataclass
class MotionReceipt:
    pose_index: int
    result: object


class RealMotionAdapter:
    """Permit exactly Poses 1 and 2 under an explicit, valid token."""

    COMMISSIONING_SCOPE = 'POSE_1_TO_2_ONLY'

    def __init__(self, *, token_valid, hard_gates, ptp_readback, dispatch, safe_stop):
        self._token_valid = token_valid
        self._hard_gates = hard_gates
        self._ptp_readback = ptp_readback
        self._dispatch = dispatch
        self._safe_stop = safe_stop
        self.dispatch_enabled = False
        self.commissioned = False

    def enable_authorized_commissioning_run(self):
        """Ephemeral permission, issued only within one explicit service call."""
        self.dispatch_enabled = True

    def disable(self):
        self.dispatch_enabled = False

    def mark_commissioned(self):
        """Record success only after both poses and cleanup have succeeded."""
        self.commissioned = True

    def _check(self, token, pose_index):
        if not self.dispatch_enabled:
            raise RealMotionRejected('REAL_MOTION_ADAPTER_NOT_COMMISSIONED')
        if pose_index not in (1, 2):
            raise RealMotionRejected('POSE_SCOPE_VIOLATION')
        if token.get('scope') != self.COMMISSIONING_SCOPE:
            raise RealMotionRejected('TOKEN_SCOPE_VIOLATION')
        if not self._token_valid(token, pose_index):
            raise RealMotionRejected('TOKEN_INVALID_OR_EXPIRED')
        reason = self._hard_gates(pose_index)
        if reason:
            raise RealMotionRejected('HARD_GATE_FAILED:' + str(reason))
        params = self._ptp_readback()
        if params != {'velocity_percent': 5, 'acceleration_percent': 5}:
            raise RealMotionRejected('PTP_READBACK_NOT_5_5')

    def execute(self, token, pose_index, target):
        """Run one action through the existing transport and fail closed."""
        self._check(token, pose_index)
        try:
            result = self._dispatch(pose_index, target)
            # Dispatch must not report success if a token/gate changed while
            # the action was in flight; its monitor invokes safe_stop first.
            self._check(token, pose_index)
            return MotionReceipt(pose_index, result)
        except Exception:
            self._safe_stop()
            raise
