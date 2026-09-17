import inspect
from dobot_calibration.node import CalibrationNode
def test_smoke_validator_precedes_any_arm_or_adapter_path():
 source=inspect.getsource(CalibrationNode.start_smoke_test_service)
 assert source.index('validate_authoritative_scene_baseline_for_preflight') < source.index('arm_real_motion_service')
 assert "'reason': baseline_gate" in source
