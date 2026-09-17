import inspect
from dobot_calibration.node import CalibrationNode
def test_provisional_baseline_guard_precedes_token_creation():
 source=inspect.getsource(CalibrationNode.arm_real_motion_service)
 assert source.index('validate_authoritative_scene_baseline_for_preflight') < source.index('self.real_motion_arm =')
 assert "'reason': baseline_gate" in source
