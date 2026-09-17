import numpy as np

from dobot_calibration.passive_guidance import calibration_plan, compute_guidance


def test_pose_two_is_commissioned_target_and_plan_has_ten_poses():
    plan = calibration_plan([150.04065, 0.0, 99.89719], 0.0)
    assert len(plan) == 10
    assert plan[0]['xyz_mm'] == [150.04065, 0.0, 99.89719]
    assert plan[1] == {'pose_index': 2, 'xyz_mm': [185.0, 0.0, 100.0], 'j4_deg': 0.0}


def test_guidance_reports_signed_axes_distance_and_target_reached():
    target = {'pose_index': 2, 'xyz_mm': [185., 0., 100.], 'j4_deg': 0.}
    moving = compute_guidance([-90., -120., 100.], 0., target, True, True)
    assert moving['state'] == 'GUIDE_TO_TARGET'
    assert moving['directions'] == {'X': '+X', 'Y': '+Y', 'Z': 'OK', 'J4': 'OK'}
    assert moving['distance_to_target_mm'] == np.linalg.norm([275., 120., 0.])
    reached = compute_guidance([184., 2., 98.], 1., target, True, True)
    assert reached['state'] == 'TARGET_REACHED'
    assert reached['capture_enabled'] is True
    assert reached['automatic_capture'] is False


def test_reached_position_still_requires_stability_and_hardware():
    target = {'pose_index': 2, 'xyz_mm': [185., 0., 100.], 'j4_deg': 0.}
    assert compute_guidance([185., 0., 100.], 0., target, False, True)['state'] == 'WAIT_ROBOT_STABLE'
    assert compute_guidance([185., 0., 100.], 0., target, True, False)['state'] == 'WAIT_HARDWARE_READY'
