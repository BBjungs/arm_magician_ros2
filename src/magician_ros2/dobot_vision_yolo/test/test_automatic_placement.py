from dobot_vision_yolo.automatic_placement import AutomaticPlacementConfig
from dobot_vision_yolo.automatic_placement import AutomaticSuctionPlacementController
from dobot_vision_yolo.automatic_placement import PlacementState


def _zone():
    return {
        'zone_id': 'Zone A',
        'pose': [220.0, 160.0, -35.0, 0.0],
        'safe_z': 60.0,
    }


def _inspection(**changes):
    result = {
        'fresh': True,
        'occupancy_valid': True,
        'occupied': False,
        'surface_valid': True,
        'surface_height_mm': -35.0,
        'surface_valid_ratio': 0.9,
        'surface_stddev_mm': 1.0,
        'alignment_valid': True,
        'fine_xy_correction_mm': [2.0, -1.0],
    }
    result.update(changes)
    return result


class _Harness:
    def __init__(self, inspection=None, verification=None):
        self.inspection = inspection or _inspection()
        self.verification = verification or {'released': True}
        self.pose = [220.0, 0.0, 60.0, 0.0]
        self.moves = []
        self.suction = []

    def move(self, pose, velocity, acceleration, label):
        self.moves.append((label, list(pose), velocity, acceleration))
        self.pose = list(pose)
        return {'accepted': True}

    def set_suction(self, enabled):
        self.suction.append(enabled)
        return {'success': True}

    def controller(self, **kwargs):
        return AutomaticSuctionPlacementController(
            resolve_zone=lambda _place_id: _zone(),
            inspect_zone=lambda _zone, _request: dict(self.inspection),
            move=self.move,
            set_suction=self.set_suction,
            verify_release=lambda _zone: dict(self.verification),
            current_pose=lambda: list(self.pose),
            validate_pose=lambda _pose: {'allowed': True},
            **kwargs,
        )


def test_free_zone_is_fine_aligned_released_and_verified():
    harness = _Harness()
    result = harness.controller().execute({'place_id': 'Zone A'})

    assert result['executed'] is True
    assert result['placed'] is True
    assert harness.suction == [False]
    attempt = result['attempt']
    assert [entry['state'] for entry in attempt['states']] == [
        PlacementState.ZONE.value,
        PlacementState.APPROACH.value,
        PlacementState.INSPECT.value,
        PlacementState.FINE_ALIGN.value,
        PlacementState.DESCEND.value,
        PlacementState.SUCTION_OFF.value,
        PlacementState.LIFT.value,
        PlacementState.VERIFY_RELEASE.value,
        PlacementState.DONE_OR_ABORT.value,
    ]
    fine_move = next(move for move in harness.moves if move[0] == 'bounded_fine_placement_xy')
    assert fine_move[1][:2] == [222.0, 159.0]
    assert any(move[0] == 'slow_place_descend' for move in harness.moves)
    assert harness.moves[-1][0] == 'lift_from_placement'


def test_occupied_zone_never_descends_or_disables_suction():
    observation = _inspection(occupied=True, reason='object already in zone')
    for key in (
        'surface_valid',
        'surface_height_mm',
        'surface_valid_ratio',
        'surface_stddev_mm',
    ):
        observation.pop(key)
    harness = _Harness(observation)
    result = harness.controller().execute({'place_id': 'Zone A'})

    assert result['executed'] is False
    assert result['aborted_safely'] is True
    assert result['suction_retained'] is True
    assert harness.suction == []
    assert not any(move[0] == 'slow_place_descend' for move in harness.moves)
    assert any(move[0] == 'recovery_return_with_part' for move in harness.moves)


def test_missing_or_stale_rgbd_inspection_fails_closed():
    harness = _Harness(_inspection(fresh=False))
    result = harness.controller().execute({'place_id': 'Zone A'})

    assert result['executed'] is False
    assert result['suction_retained'] is True
    assert harness.suction == []
    assert not any(move[0] == 'slow_place_descend' for move in harness.moves)


def test_large_fine_placement_error_is_rejected_before_descent():
    harness = _Harness(_inspection(fine_xy_correction_mm=[20.0, 0.0]))
    result = harness.controller().execute({'place_id': 'Zone A'})

    assert result['executed'] is False
    assert harness.suction == []
    assert not any(move[0] == 'slow_place_descend' for move in harness.moves)


def test_failed_release_verification_returns_safe_abort_after_lift():
    harness = _Harness(verification={'released': False, 'reason': 'part still on cup'})
    result = harness.controller().execute({'place_id': 'Zone A'})

    assert result['executed'] is False
    assert result['suction_retained'] is False
    assert result['aborted_safely'] is True
    assert harness.suction == [False]
    assert any(move[0] == 'lift_from_placement' for move in harness.moves)
