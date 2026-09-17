from dobot_web_interface.web_interface import DobotWebNode


def _zone():
    return {'zone_id': 'Zone A', 'place_id': 'Zone A'}


def test_rgbd_zone_observation_uses_the_canonical_zone_key():
    result = DobotWebNode._automatic_placement_observation(
        {
            'placement_inspections': {
                'Zone A': {
                    'occupancy_valid': True,
                    'occupied': False,
                    'surface_valid': True,
                    'surface_height_mm': -35.0,
                }
            }
        },
        _zone(),
    )

    assert result['fresh'] is True
    assert result['zone_id'] == 'Zone A'
    assert result['occupancy_valid'] is True
    assert result['occupied'] is False


def test_missing_zone_observation_is_not_treated_as_empty():
    result = DobotWebNode._automatic_placement_observation({}, _zone())

    assert result['fresh'] is True
    assert result['occupancy_valid'] is False
    assert 'missing' in result['reason']
