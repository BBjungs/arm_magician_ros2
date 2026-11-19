"""Load and validate independent deployment configuration files."""

import math
from pathlib import Path

import yaml


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be finite')
    return value


def vector(value, size, name):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError(f'{name} must have {size} entries')
    return [number(entry, name) for entry in value]


def box(lower, upper, size, name):
    if not all(a < b for a, b in zip(vector(lower, size, name), vector(upper, size, name))):
        raise ValueError(f'{name} bounds must be in ascending order')


def load(directory):
    sections = ('hardware', 'camera', 'vision', 'visual_servo', 'motion', 'safety', 'web')
    config = {}
    for section in sections:
        with (Path(directory) / f'{section}.yaml').open() as file:
            config[section] = yaml.safe_load(file)
        if not isinstance(config[section], dict):
            raise ValueError(f'{section}.yaml must contain a mapping')
    validate(config)
    return config


def validate(config):
    hardware, motion, safety = (config[key] for key in ('hardware', 'motion', 'safety'))
    for section, flags in (
            (hardware, ('simulation_mode', 'real_motion_enabled', 'autostart_motion')),
            (safety, ('simulation_workcell_ready', 'simulation_estop_available',
                      'physical_workcell_commissioned'))):
        for flag in flags:
            if type(section.get(flag)) is not bool:
                raise ValueError(f'{flag} must be a YAML boolean')
    if hardware['real_motion_enabled'] or hardware['autostart_motion']:
        raise ValueError('The installed runtime supports explicit mock motion only')

    positive = {
        'hardware': 'telemetry_timeout',
        'camera': 'freshness max_depth_skew mock_depth_m mock_fps selection_history_seconds',
        'vision': 'minimum_area tracking_radius_pixels tracking_area_ratio tracking_hue_tolerance',
        'visual_servo': ('tolerance_pixels probe_mm damping gain minimum_singular_value '
                         'maximum_condition_number maximum_duration error_jitter_pixels '
                         'maximum_xy_excursion_mm'),
        'motion': ('max_step_mm max_setup_travel_mm speed_mm_s max_speed_mm_s timeout '
                   'settle_seconds position_tolerance_mm rotation_tolerance_deg'),
        'safety': 'clearance_mm link_radius_mm minimum_depth_m maximum_depth_m',
        'web': 'lease_seconds confirmation_seconds',
    }
    for section, keys in positive.items():
        for key in keys.split():
            if number(config[section][key], key) <= 0:
                raise ValueError(f'{key} must be positive')
    integers = {
        'camera': 'width height',
        'vision': 'border_pixels depth_sample_radius',
        'visual_servo': 'stable_frames maximum_corrections maximum_error_increases',
        'web': 'request_history_size',
    }
    for section, keys in integers.items():
        for key in keys.split():
            value = config[section][key]
            if type(value) is not int or value < 1:
                raise ValueError(f'{key} must be a positive integer')
    for section, key in (('vision', 'minimum_confidence'), ('vision', 'depth_minimum_fraction'),
                         ('camera', 'minimum_valid_depth_fraction')):
        if not 0 < number(config[section][key], key) <= 1:
            raise ValueError(f'{key} must be in (0, 1]')

    if motion['speed_mm_s'] > motion['max_speed_mm_s'] or motion['settle_seconds'] >= motion['timeout']:
        raise ValueError('Motion speed or settling exceeds its limit')
    if config['visual_servo']['probe_mm'] > motion['max_step_mm']:
        raise ValueError('Identification probe exceeds the step limit')
    if not safety['minimum_depth_m'] < safety['maximum_depth_m']:
        raise ValueError('Target depth bounds are inverted')
    box(safety['workspace_min_mm'], safety['workspace_max_mm'], 3, 'Workspace')
    box(safety['joint_min_deg'], safety['joint_max_deg'], 4, 'Joint limits')
    if min(vector(safety['assembly_half_extent_mm'], 3, 'Assembly envelope')) <= 0:
        raise ValueError('Assembly half extents must be positive')
    number(safety['table_height_mm'], 'Table height')
    for obstacle in safety['obstacles_mm']:
        if not isinstance(obstacle, list) or len(obstacle) != 2:
            raise ValueError('An obstacle requires lower and upper bounds')
        box(*obstacle, 3, 'Obstacle')
    for pose in ('home', 'observation'):
        vector(motion[pose], 4, pose)
    box(config['vision']['hsv_lower'], config['vision']['hsv_upper'], 3, 'HSV threshold')
    for entry, maximum in zip(config['vision']['hsv_upper'], (179, 255, 255)):
        if type(entry) is not int or entry > maximum:
            raise ValueError('HSV upper value lies outside the valid range')
    if any(type(entry) is not int or entry < 0 for entry in config['vision']['hsv_lower']):
        raise ValueError('HSV lower value lies outside the valid range')
    if type(config['web']['port']) is not int or not 0 <= config['web']['port'] <= 65535:
        raise ValueError('Invalid web port')
