import threading
from types import SimpleNamespace

import numpy as np
import pytest
import yaml

from dobot_calibration.autonomous import AutomaticCalibration
from dobot_calibration.autonomous_backend import AutomaticBackend
from dobot_calibration.calibration_workspace import CalibrationWorkspace, automatic_plan
from dobot_calibration.geometry import CalibrationError, transform


class Backend:
    def __init__(self):
        self.events = []
        self.failure = None

    def event(self, name):
        self.events.append(name)
        if name == self.failure:
            raise RuntimeError('injected ' + name)

    def prepare(self, checkpoint):
        self.event('prepare')
        return automatic_plan(transform(translation=[.15, 0, .10]))

    def wait_for_authorization(self, checkpoint):
        # Explicit test double: no hardware transport exists in this backend.
        pass

    def validate(self, first, second):
        self.event('validate')

    def check(self):
        pass

    def move(self, target):
        self.event('move')

    def settle(self, target, checkpoint):
        self.event('settle')

    def capture(self, target):
        self.event('capture')
        return object()

    def accept(self, capture, index):
        self.event('accept')

    def solve(self, checkpoint):
        self.event('solve')
        return {'state': 'CANDIDATE_VERIFIED'}

    def persist_status(self, status):
        pass

    def stop(self):
        self.event('stop')

    def close(self):
        self.event('close')


def test_ten_pose_sequence_needs_no_operator_capture_calls():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    engine.run()
    assert backend.events[:10] == ['prepare'] + ['validate'] * 9
    assert backend.events[10:-2] == ['move', 'settle', 'capture', 'accept'] * 10
    assert backend.events[-2:] == ['solve', 'close']
    assert engine.snapshot()['accepted_pose_count'] == 10
    assert engine.snapshot()['state'] == 'CANDIDATE_VERIFIED'
    assert engine.snapshot()['production_ready'] is False


@pytest.mark.parametrize('failure', ['prepare', 'validate', 'move', 'settle', 'capture', 'accept', 'solve', 'close'])
def test_every_stage_failure_prevents_success_and_closes(failure):
    backend = Backend()
    backend.failure = failure
    engine = AutomaticCalibration(backend)
    engine.run()
    assert engine.snapshot()['state'] == 'FAULT'
    assert backend.events[-1] == 'close'
    if failure in ('prepare', 'validate'):
        assert 'move' not in backend.events


def test_abort_at_movement_boundary_prevents_capture_and_next_move():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    def move(target):
        backend.events.append('move')
        engine.abort_event.set()
    backend.move = move
    engine.run()
    assert engine.snapshot()['state'] == 'SAFE_STOP'
    assert 'capture' not in backend.events
    assert backend.events.count('move') == 1


def test_pause_resume_and_double_start():
    backend = Backend()
    engine = AutomaticCalibration(backend)
    paused = threading.Event()
    def check():
        if engine.pause_event.is_set():
            paused.set()
    def move(target):
        backend.events.append('move')
        if backend.events.count('move') == 1:
            engine.pause()
    backend.check, backend.move = check, move
    assert engine.start()[0]
    assert paused.wait(2)
    assert not engine.start()[0]
    assert backend.events.count('move') == 1
    engine.resume()
    engine.worker.join(2)
    assert not engine.worker.is_alive()
    assert backend.events.count('capture') == 10


def workspace_data():
    return dict(schema_version=1, installation_verified=True, whole_robot_environment_verified=True,
                measurement_source='synthetic test fixture, never deployed', base_frame='base',
                camera_id='test-camera', mount_fingerprint='test-mount', table_surface_z_m=-.2,
                free_volume_min_m=[-.3, -.4, -.2], free_volume_max_m=[.6, .4, .6],
                minimum_clearance_m=.025)


def load_workspace(tmp_path, data):
    path = tmp_path / 'workspace.yaml'
    path.write_text(yaml.safe_dump(data))
    return CalibrationWorkspace.load(path, base_frame='base', camera_id='test-camera',
                                     mount_fingerprint='test-mount')


@pytest.mark.parametrize('key,value', [
    ('installation_verified', False), ('whole_robot_environment_verified', False),
    ('camera_id', 'wrong'), ('mount_fingerprint', 'wrong'), ('base_frame', 'wrong'),
    ('table_surface_z_m', None), ('table_surface_z_m', float('nan')),
    ('measurement_source', ''), ('minimum_clearance_m', 0),
    ('free_volume_min_m', [0, 0]), ('free_volume_max_m', [-1, -1, -1]),
])
def test_unmeasured_or_mismatched_installation_is_rejected(tmp_path, key, value):
    data = workspace_data()
    data[key] = value
    with pytest.raises(CalibrationError, match='WORKSPACE_INVALID'):
        load_workspace(tmp_path, data)


def test_workspace_does_not_require_camera_rotation_but_checks_swept_sphere(tmp_path):
    workspace = load_workspace(tmp_path, workspace_data())
    mount = SimpleNamespace(envelope_radius_m=.1526, translation_error_bound_m=.001,
                            rotation_seed_verified=False)
    start = transform(translation=[.15, 0, .10])
    target = transform(translation=[.185, 0, .10])
    workspace.check_segment(start, target, mount)
    data = workspace_data()
    data['table_surface_z_m'] = 0.
    workspace = load_workspace(tmp_path, data)
    with pytest.raises(CalibrationError, match='CLEARANCE'):
        workspace.check_segment(start, target, mount)


def test_automatic_plan_tracks_current_pose_not_old_pose_two():
    anchor = transform(translation=[.205, .01, .08])
    plan = automatic_plan(anchor)
    np.testing.assert_allclose(plan[0], anchor)
    np.testing.assert_allclose(plan[1][:3, 3], [.240, .01, .08])


def test_planner_selects_feasible_variant_around_joint_limit(tmp_path):
    backend = AutomaticBackend(SimpleNamespace(
        mount=SimpleNamespace(envelope_radius_m=.105, translation_error_bound_m=.001),
        settings={'planning_soft_margin_deg': 2.0}))
    backend.workspace = load_workspace(tmp_path, workspace_data())
    anchor = transform(translation=[.19, 0, .125])
    plan = backend.select_plan(anchor)
    assert len(plan) == 10
    assert not np.allclose(plan[5], automatic_plan(anchor)[5])
    for first, second in zip(plan, plan[1:]):
        backend.validate(first, second)


def test_settling_uses_bracketed_robot_timestamp():
    pose = transform(translation=[.15, 0, .1])
    history = [(float(t), pose, np.zeros(4)) for t in np.linspace(10, 10.8, 41)]
    node = SimpleNamespace(history=history, lock=threading.RLock(), now_s=lambda: 10.81,
                           after_motion_stamp=9., stop=threading.Event())
    AutomaticBackend(node).settle(pose, lambda: None)
