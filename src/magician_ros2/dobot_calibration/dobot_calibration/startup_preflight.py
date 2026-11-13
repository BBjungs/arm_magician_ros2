"""Check the installed Python/generated-interface combination without ROS init."""
import importlib
import sys

from rclpy.type_support import check_for_type_support
from .node_lifecycle import record_failure


def check_installation():
    for module_name, names in (
        ('dobot_msgs.srv', ('SelectCalibrationObject', 'AuthorizeCalibration',
                            'EvaluatePTPTrajectory', 'GetPTPCommonParams',
                            'SetPTPCommonParams')),
        ('dobot_msgs.action', ('PointToPoint',)),
    ):
        module = importlib.import_module(module_name)
        print(f'[PREFLIGHT] {module_name}: {module.__file__}', flush=True)
        for name in names:
            interface = getattr(module, name)
            check_for_type_support(interface)
    for name in ('dobot_calibration.node', 'dobot_web_interface.web_interface',
                 'dobot_vision_rgbd.object_fusion_node'):
        module = importlib.import_module(name)
        print(f'[PREFLIGHT] {name}: {module.__file__}', flush=True)


def main():
    try:
        check_installation()
    except Exception:
        record_failure('Installed package preflight failed; rebuild matching packages')
        return 78  # EX_CONFIG: retrying cannot repair generated interfaces.
    return 0


if __name__ == '__main__':
    sys.exit(main())
