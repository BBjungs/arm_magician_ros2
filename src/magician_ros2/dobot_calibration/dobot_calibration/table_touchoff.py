"""Passive table touch-off calculation; it deliberately contains no motion API."""

from dataclasses import dataclass, field
import math
import statistics


TOOL_TO_SUCTION_TCP_Z_MM = -70.0
MAX_SCALAR_SPREAD_MM = 2.0


@dataclass
class TableTouchoff:
    gauge_height_mm: float = 0.0
    samples: list = field(default_factory=list)

    def __post_init__(self):
        self.gauge_height_mm = float(self.gauge_height_mm)
        if not math.isfinite(self.gauge_height_mm) or self.gauge_height_mm < 0:
            raise ValueError('gauge height must be finite and non-negative')

    def add(self, measured_tool_z_mm):
        tool_z = float(measured_tool_z_mm)
        if not math.isfinite(tool_z):
            raise ValueError('measured tool Z must be finite')
        # suction Z = tool Z - 70 mm; a positive gauge raises the contact
        # surface by that amount, hence it is subtracted from the datum.
        table_z = tool_z + TOOL_TO_SUCTION_TCP_Z_MM - self.gauge_height_mm
        self.samples.append({'measured_tool_z_mm': tool_z,
                             'table_z_mm': table_z})
        return table_z

    def clear(self):
        self.samples.clear()

    def summary(self):
        values = [float(sample['table_z_mm']) for sample in self.samples]
        spread = max(values) - min(values) if values else None
        accepted = len(values) >= 3 and spread <= MAX_SCALAR_SPREAD_MM
        return {
            'mode': 'manual_passive_table_touch_off',
            'tool_to_suction_tcp_z_mm': TOOL_TO_SUCTION_TCP_Z_MM,
            'gauge_height_mm': self.gauge_height_mm,
            'sample_count': len(values),
            'samples': list(self.samples),
            'spread_mm': spread,
            'scalar_table_height_accepted': accepted,
            'table_surface_z_in_magician_base_link_mm': (
                float(statistics.median(values)) if accepted else None),
            'next_action': (
                'use_median_scalar_table_height' if accepted else
                'capture_at_least_three_points' if len(values) < 3 else
                'fit_table_plane_from_touch_off_points'),
        }
