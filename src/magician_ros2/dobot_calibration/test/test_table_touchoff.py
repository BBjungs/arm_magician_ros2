import pytest

from dobot_calibration.table_touchoff import TableTouchoff


def test_three_consistent_manual_touch_offs_use_the_median_scalar_height():
    touch = TableTouchoff(gauge_height_mm=1.5)
    for tool_z in (171.5, 172.0, 172.5):
        touch.add(tool_z)
    result = touch.summary()
    assert result['samples'][0]['table_z_mm'] == pytest.approx(100.0)
    assert result['spread_mm'] == pytest.approx(1.0)
    assert result['scalar_table_height_accepted'] is True
    assert result['table_surface_z_in_magician_base_link_mm'] == pytest.approx(100.5)


def test_spread_above_two_mm_requires_a_fitted_plane_not_a_scalar_height():
    touch = TableTouchoff()
    for tool_z in (170.0, 171.0, 172.1):
        touch.add(tool_z)
    result = touch.summary()
    assert result['spread_mm'] == pytest.approx(2.1)
    assert result['scalar_table_height_accepted'] is False
    assert result['table_surface_z_in_magician_base_link_mm'] is None
    assert result['next_action'] == 'fit_table_plane_from_touch_off_points'
