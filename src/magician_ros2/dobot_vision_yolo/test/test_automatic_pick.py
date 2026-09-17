import pytest

from dobot_vision_yolo.automatic_pick import AutomaticPickConfig
from dobot_vision_yolo.automatic_pick import AutomaticSuctionPickController
from dobot_vision_yolo.automatic_pick import PickState
from dobot_vision_yolo.automatic_pick import bounded_xy_correction
from dobot_vision_yolo.automatic_pick import depth_is_reliable


def _target(x=220.0, y=10.0, depth=True):
    return {
        'selected': True,
        'class_name': 'black_cap',
        'pick_pose': [x, y, -35.0, 0.0],
        'safe_z': 60.0,
        'depth_mm': 500.0 if depth else 100.0,
        'depth_valid': depth,
        'depth_valid_ratio': 0.9 if depth else 0.0,
        'depth_stddev': 1.0 if depth else None,
    }


class _Harness:
    def __init__(self, redetections, pose=None, verification=None):
        self.redetections = iter(redetections)
        self.pose = pose or [220.0, 10.0, 60.0, 0.0]
        self.moves = []
        self.suction = []
        self.verification = verification or {'picked': True}

    def redetect(self, _request):
        return next(self.redetections)

    def move(self, pose, velocity, acceleration, label):
        self.moves.append((label, list(pose), velocity, acceleration))
        self.pose = list(pose)
        return {'accepted': True}

    def set_suction(self, enabled):
        self.suction.append(enabled)
        return {'success': True}

    def verify(self, _target):
        return dict(self.verification)

    def controller(self, **kwargs):
        return AutomaticSuctionPickController(
            redetect_target=self.redetect,
            move=self.move,
            set_suction=self.set_suction,
            verify_pick=self.verify,
            current_pose=lambda: list(self.pose),
            validate_pose=lambda _pose: {'allowed': True},
            **kwargs,
        )


def test_bounded_xy_correction_applies_axis_and_vector_limits():
    assert bounded_xy_correction([20.0, -20.0], 6.0, 8.0) == [5.657, -5.657]


@pytest.mark.parametrize('max_attempts', [0, 1.5, 6, float('nan'), True])
def test_config_rejects_non_integral_or_out_of_range_retry_budgets(max_attempts):
    with pytest.raises(ValueError):
        AutomaticPickConfig(max_attempts=max_attempts)


def test_depth_mode_requires_physical_quality_metrics():
    target = _target()
    config = AutomaticPickConfig()

    assert depth_is_reliable(target, config)
    target['depth_valid_ratio'] = 1.1
    assert not depth_is_reliable(target, config)
    target['depth_valid_ratio'] = 0.9
    target['depth_stddev'] = -0.1
    assert not depth_is_reliable(target, config)


def test_depth_pick_reacquires_then_descends_slowly_and_lifts():
    initial = _target()
    harness = _Harness([_target()])

    result = harness.controller().execute(
        {'object_class': 'black_cap'}, initial_target=initial
    )

    assert result['executed'] is True
    attempt = result['attempts'][0]
    assert attempt['depth_mode'] == 'depth_base_transform'
    assert [state['state'] for state in attempt['states']] == [
        PickState.TARGET.value,
        PickState.APPROACH.value,
        PickState.FINE_ALIGN.value,
        PickState.DESCEND.value,
        PickState.SUCTION_ON.value,
        PickState.LIFT.value,
        PickState.VERIFY_PICK.value,
        PickState.DONE_OR_RETRY.value,
    ]
    assert any(label == 'slow_descend' for label, *_ in harness.moves)
    assert harness.suction == [True]
    assert harness.moves[-1][0] == 'lift_to_safe_approach'
    assert harness.moves[-1][1][2] == 60.0


def test_close_or_invalid_depth_uses_kinematics_plus_2d_visual_alignment():
    initial = _target(depth=False)
    observed = _target(x=222.0, y=12.0, depth=False)
    harness = _Harness([observed], pose=[220.0, 10.0, 60.0, 0.0])

    result = harness.controller().execute(
        {'object_class': 'black_cap'}, initial_target=initial
    )

    attempt = result['attempts'][0]
    assert result['executed'] is True
    assert attempt['depth_mode'] == 'robot_kinematics_2d_visual'
    assert attempt['correction'] == [2.0, 2.0]
    fine_move = next(item for item in harness.moves if item[0] == 'bounded_fine_xy_correction')
    assert fine_move[1][:2] == [222.0, 12.0]


def test_failed_verification_retries_then_returns_safe_abort():
    initial = _target()
    # Attempt one re-detects after approach; attempt two gets a fresh target,
    # then re-detects after its approach.
    harness = _Harness(
        [_target(), _target(), _target()],
        verification={'picked': False, 'reason': 'target remains visible'},
    )
    controller = harness.controller(config=AutomaticPickConfig(max_attempts=2))

    result = controller.execute({'object_class': 'black_cap'}, initial_target=initial)

    assert result['executed'] is False
    assert result['aborted_safely'] is True
    assert result['attempt_count'] == 2
    assert harness.suction == [True, False, True, False]
    assert all(attempt['state'] == PickState.DONE_OR_RETRY.value for attempt in result['attempts'])


def test_large_visual_error_is_rejected_without_descending_or_enabling_suction():
    initial = _target(depth=False)
    observed = _target(x=240.0, y=10.0, depth=False)
    harness = _Harness([observed])
    controller = harness.controller(config=AutomaticPickConfig(max_attempts=1))

    result = controller.execute({'object_class': 'black_cap'}, initial_target=initial)

    assert result['executed'] is False
    assert result['aborted_safely'] is True
    assert harness.suction == []
    assert not any(label == 'slow_descend' for label, *_ in harness.moves)


def test_cancel_after_suction_still_turns_suction_off():
    initial = _target()
    harness = _Harness([_target()])
    canceled = {'value': False}

    def set_suction(enabled):
        harness.suction.append(enabled)
        if enabled:
            canceled['value'] = True
        return {'success': True}

    controller = AutomaticSuctionPickController(
        redetect_target=harness.redetect,
        move=harness.move,
        set_suction=set_suction,
        verify_pick=harness.verify,
        current_pose=lambda: list(harness.pose),
        validate_pose=lambda _pose: {'allowed': True},
        cancel_requested=lambda: canceled['value'],
    )

    result = controller.execute({'object_class': 'black_cap'}, initial_target=initial)

    assert result['executed'] is False
    assert result['reason'] == 'automatic pick canceled'
    assert harness.suction == [True, False]


def test_failed_recovery_is_reported_as_operator_intervention_required():
    initial = _target()
    harness = _Harness([_target()])

    def move(pose, velocity, acceleration, label):
        harness.moves.append((label, list(pose), velocity, acceleration))
        if label in ('lift_to_safe_approach', 'recovery_lift_to_safe_approach'):
            return {'accepted': False, 'message': 'lift failed'}
        harness.pose = list(pose)
        return {'accepted': True}

    controller = AutomaticSuctionPickController(
        config=AutomaticPickConfig(max_attempts=1),
        redetect_target=harness.redetect,
        move=move,
        set_suction=harness.set_suction,
        verify_pick=harness.verify,
        current_pose=lambda: list(harness.pose),
        validate_pose=lambda _pose: {'allowed': True},
    )

    result = controller.execute({'object_class': 'black_cap'}, initial_target=initial)

    assert result['executed'] is False
    assert result['aborted_safely'] is False
    assert 'operator intervention required' in result['reason']
    assert harness.suction == [True, False]
