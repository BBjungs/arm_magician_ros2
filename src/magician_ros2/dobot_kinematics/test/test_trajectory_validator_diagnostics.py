import json

from dobot_kinematics.trajectory_validator_server import PoseValidatorService


def test_cartesian_limit_diagnostic_exposes_the_effective_limit_and_ik_provenance():
    validator = PoseValidatorService.__new__(PoseValidatorService)
    validator.axis_1_range = {'min': -120.0, 'max': 120.0}
    validator.axis_2_range = {'min': -5.0, 'max': 90.0}
    validator.axis_3_range = {'min': -15.0, 'max': 90.0}
    validator.axis_4_range = {'min': -140.0, 'max': 140.0}

    diagnostic = validator._cartesian_limit_diagnostic(
        [0.0, 5.0, -15.1, 0.0], [150.0, 0.0, 174.0, 0.0], 38,
        [0.0, 3.0, 13.7, 0.0], [0.0, 5.9, -22.2, 0.0])

    assert diagnostic['violated_joint'] == 'axis_3'
    assert diagnostic['configured_min_deg'] == -15.0
    assert diagnostic['sample_index'] == 38
    assert diagnostic['ik_branch'] == 'analytic_single_branch'
    message = validator._diagnostic_message('Joint limits violated along trajectory', diagnostic)
    assert json.loads(message.split(': ', 1)[1]) == diagnostic
