"""Fit real operator-collected data without moving or authorizing the robot."""

import numpy as np

from .geometry import CalibrationError, Limits
from .solver import solve, verify
from .workflow import load_bundle, save_bundle


def solve_session(captures, mount, context, path, limits=Limits(), checkpoint=lambda: None):
    # The last three poses are held out BEFORE fitting, never used to tune it.
    if len(captures) != 10:
        raise CalibrationError(f'REAL_POSES_REQUIRED: {len(captures)}/10 accepted poses')
    if any(b.stamp <= a.stamp for a, b in zip(captures, captures[1:])):
        raise CalibrationError('Capture timestamps must be strictly increasing')
    checkpoint()
    solution = solve(captures[:7], mount, limits)
    checkpoint()
    report = verify(solution, captures[0], captures[7:], mount, limits)
    if report['result'] != 'PASS':
        raise CalibrationError('Independent verification failed: ' + report['reason'])
    checkpoint()
    # This is a session candidate, NOT the production calibration path.
    save_bundle(path, solution, captures[0], context, report, limits)
    restored, anchor = load_bundle(path, context, mount, limits)
    if not np.allclose(restored.tool_T_camera, solution.tool_T_camera, atol=1e-12):
        raise CalibrationError('Reloaded transform differs from fitted transform')
    reloaded_report = verify(restored, anchor, captures[7:], mount, limits)
    if reloaded_report['result'] != 'PASS':
        raise CalibrationError('Reload verification failed: ' + reloaded_report['reason'])
    checkpoint()
    return {
        'state': 'CANDIDATE_VERIFIED', 'source': 'real_passive_captures',
        'training_pose_count': 7, 'held_out_pose_count': 3,
        'metrics': solution.metrics, 'observability': solution.observability,
        'independent_verification': report, 'reload_verification': reloaded_report,
        'tool_T_camera': solution.tool_T_camera.tolist(), 'candidate_path': str(path),
        'production_ready': False, 'motion_command_sent': False,
        'reason': 'Candidate only; live safety, repeatability and object validation still required',
    }
