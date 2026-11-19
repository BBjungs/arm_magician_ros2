import copy
from pathlib import Path
import unittest

import cv2
import numpy as np

from dobot_auto_center.config import load, validate
from dobot_auto_center.mock_camera import JACOBIANS, MockCamera
from dobot_auto_center.motion import Motion, MockTransport
from dobot_auto_center.safety import Safety
from dobot_auto_center.vision import ClassicalDetector, Observation, Tracker, select_roi
from dobot_auto_center.visual_servo import VisualServo
from dobot_auto_center.workflow import State, Workflow


CONFIG = Path(__file__).resolve().parents[2] / 'config'
cv2.setNumThreads(1)


class Simulation:
    def __init__(self, scenario='left', jacobian='coupled'):
        self.config = load(CONFIG)
        self.config['visual_servo'].update(mock_scenario=scenario, mock_jacobian=jacobian)
        self.mock = MockCamera(self.config)
        self.safety = Safety(self.config)
        self.transport = MockTransport(self.config['motion'])
        self.motion = Motion(self.config, self.safety, self.transport)
        self.now = 100.
        self.authorized = True
        self.camera_enabled = True
        self.last_frame = self.now
        self.workflow = Workflow(self.config, self.motion, self.submit,
                                 lambda owner, _: owner == 'operator' and self.authorized)
        self.tick()

    def submit(self, permit, operation, goal, speed, now):
        # Execute on the next control tick as the ROS action adapter does.
        simulation = self

        class Pending:
            started = False
            canceled = False

            def cancel(self):
                self.canceled = True

            def poll(self, current):
                if not self.started:
                    self.started = True
                    return simulation.motion.begin(permit, operation, goal, speed, current,
                                                   simulation.workflow.guard)
                return simulation.motion.result

        return Pending()

    def tick(self):
        self.now += .025
        if self.camera_enabled and self.now - self.last_frame >= .075:
            rgb, raw = self.mock.render(self.transport.pose)
            depth = raw.astype(np.float32) / 1000 if self.mock.depth_enabled else None
            self.workflow.ingest(Observation(self.now, self.now, rgb, depth, self.now, True),
                                 self.now)
            self.last_frame = self.now
        self.workflow.tick(self.now)

    def until(self, condition, seconds=20):
        for _ in range(int(seconds / .025)):
            if condition():
                return
            self.tick()
        raise AssertionError((self.workflow.state, self.workflow.diagnostic))

    def command(self, action, **data):
        self.workflow.command(action, data, 'operator', self.now)

    def prepare(self):
        self.command('camera')
        self.until(lambda: self.workflow.rgbd(self.now))
        self.command('home')
        self.until(lambda: self.workflow.homed)
        self.command('observation')
        self.until(lambda: self.workflow.at_observation)
        self.command('detect')
        self.until(lambda: bool(self.workflow.detections))

    def select(self, index=0):
        x, y, w, h = self.workflow.detections[index].box
        self.command('select', frame_id=self.workflow.frame_id, roi=[x, y, x+w, y+h])

    def start(self):
        self.prepare()
        self.select()
        self.command('center')

    def wait_for_step(self):
        self.until(lambda: len(self.transport.commands) > 2 and self.motion.snapshot.moving)


class VisionTests(unittest.TestCase):
    def setUp(self):
        self.config = load(CONFIG)
        self.mock = MockCamera(self.config)
        self.detector = ClassicalDetector(self.config['vision'])

    def observation(self, scenario):
        self.mock.scenario = scenario
        rgb, depth = self.mock.render(self.config['motion']['observation'])
        return Observation(10., 10., rgb, depth / 1000., 10., True)

    def test_detection_center_confidence_depth_and_error(self):
        d, = self.detector.detect(self.observation('left'))
        np.testing.assert_allclose(d.center, (205, 240), atol=1)
        np.testing.assert_allclose(d.error(640, 480), (-115, 0), atol=1)
        self.assertGreater(d.confidence, .9)
        self.assertAlmostEqual(d.depth, .30)

    def test_stale_skew_and_invalid_registered_depth(self):
        frame = self.observation('centered')
        camera = self.config['camera']
        self.assertTrue(frame.registered(10.1, camera))
        self.assertFalse(frame.registered(10.5, camera))
        frame.depth_stamp = 9.9
        self.assertFalse(frame.registered(10.1, camera))
        self.mock.depth_valid = False
        d, = self.detector.detect(self.observation('centered'))
        self.assertIsNone(d.depth)

    def test_identity_ambiguity_rejected(self):
        d, second = self.detector.detect(self.observation('multiple'))
        tracker = Tracker(self.config['vision'])
        tracker.lock(d)
        self.assertEqual(tracker.update([second, d]), d)
        self.assertIsNone(tracker.update([d, d]))
        self.assertIsNone(tracker.update([d]))

    def test_multiple_selection_requires_unique_roi(self):
        objects = self.detector.detect(self.observation('multiple'))
        with self.assertRaisesRegex(ValueError, 'exactly one'):
            select_roi(objects, [0, 0, 640, 480], 640, 480)
        x, y, w, h = objects[1].box
        self.assertEqual(select_roi(objects, [x, y, x+w, y+h], 640, 480), objects[1])


class ServoTests(unittest.TestCase):
    def test_jacobian_learns_measured_coupled_axes(self):
        servo = VisualServo(load(CONFIG)['visual_servo'])
        matrix = np.asarray(JACOBIANS['coupled'])
        for delta in ([2.7, .1], [.15, 2.5]):
            servo.record_probe([0, 0], delta, [0, 0], matrix @ delta)
        np.testing.assert_allclose(servo.jacobian, matrix)
        error = np.array([90., -50.])
        step = servo.step(error, 8)
        self.assertLessEqual(np.linalg.norm(step), 8.000001)
        self.assertLess(np.linalg.norm(error + matrix @ step), np.linalg.norm(error))

    def test_increasing_error_and_degenerate_travel_are_rejected(self):
        servo = VisualServo(load(CONFIG)['visual_servo'])
        with self.assertRaisesRegex(ValueError, 'increased'):
            for error in ([15, 0], [18, 0], [22, 0]):
                servo.note_correction(error)
        servo.record_probe([0, 0], [2, 0], [0, 0], [5, 0])
        with self.assertRaisesRegex(ValueError, 'independent'):
            servo.record_probe([0, 0], [3, 0], [0, 0], [6, 0])

    def test_simulation_converges_in_all_directions_and_jacobians(self):
        for scenario in ('left', 'right', 'up', 'down', 'corner'):
            for jacobian in ('normal', 'reversed', 'coupled'):
                with self.subTest(scenario=scenario, jacobian=jacobian):
                    simulation = Simulation(scenario, jacobian)
                    simulation.start()
                    simulation.until(lambda: simulation.workflow.state == State.CENTERED)
                    error = simulation.workflow.status(simulation.now)['error']
                    self.assertLessEqual(max(map(abs, error)), 12)
                    goals = simulation.transport.commands
                    for a, b in zip(goals[1:], goals[2:]):
                        self.assertEqual(a[2:], b[2:])
                        self.assertLessEqual(np.linalg.norm(np.subtract(a[:2], b[:2])), 8.000001)
                    count = len(goals)
                    for _ in range(18):
                        simulation.tick()
                    self.assertEqual(len(goals), count)

    def test_already_centered_never_moves_during_run(self):
        simulation = Simulation('centered')
        simulation.start()
        simulation.until(lambda: simulation.workflow.state == State.CENTERED)
        self.assertEqual(len(simulation.transport.commands), 2)
        self.assertEqual(simulation.workflow.servo.stable, 5)

    def test_singular_holds_after_probes(self):
        simulation = Simulation('left', 'singular')
        simulation.start()
        simulation.until(lambda: simulation.workflow.state == State.STOPPED)
        self.assertEqual(len(simulation.transport.commands), 4)
        self.assertIn('singular', simulation.workflow.diagnostic)

    def test_lost_target_stops_during_step(self):
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.mock.scenario = 'lost'
        simulation.until(lambda: simulation.workflow.state == State.STOPPED)
        self.assertIsNone(simulation.transport.travel)
        self.assertIn('Target lost', simulation.workflow.diagnostic)
        self.assertEqual(len(simulation.transport.commands), 3)

    def test_multiple_targets_require_operator_selection(self):
        simulation = Simulation('multiple')
        simulation.prepare()
        with self.assertRaisesRegex(ValueError, 'lock a target'):
            simulation.command('center')
        self.assertEqual(len(simulation.transport.commands), 2)
        simulation.select(1)
        simulation.command('center')
        simulation.until(lambda: simulation.workflow.state == State.CENTERED)


class MotionTests(unittest.TestCase):
    def test_configuration_rejects_real_motion_autostart_and_invalid_bounds(self):
        for flag in ('real_motion_enabled', 'autostart_motion'):
            config = load(CONFIG)
            config['hardware'][flag] = True
            with self.assertRaisesRegex(ValueError, 'mock motion only'):
                validate(config)
        config = load(CONFIG)
        config['safety']['workspace_max_mm'][0] = float('nan')
        with self.assertRaisesRegex(ValueError, 'finite'):
            validate(config)

    def test_reject_before_home_and_without_camera(self):
        simulation = Simulation()
        with self.assertRaisesRegex(ValueError, 'Verified HOME'):
            simulation.command('observation')
        with self.assertRaisesRegex(ValueError, 'RGB-D'):
            simulation.command('home')
        self.assertFalse(simulation.transport.commands)

    def test_workspace_axis_joint_speed_and_swept_collision_rejection(self):
        config = load(CONFIG)
        a, b = (200, 0, 120, 0), (205, 0, 120, 0)
        guard = Safety(config)
        guard.path(a, b, 20, 'step')
        with self.assertRaisesRegex(ValueError, 'workspace'):
            guard.path((243, 0, 120, 0), (250, 0, 120, 0), 20, 'step')
        with self.assertRaisesRegex(ValueError, 'fixed Z/R'):
            guard.path(a, (205, 0, 118, 0), 20, 'step')
        with self.assertRaisesRegex(ValueError, 'speed'):
            guard.path(a, b, 100, 'step')
        travel = copy.deepcopy(config)
        travel['safety']['joint_max_deg'][2] = 70
        with self.assertRaisesRegex(ValueError, 'joint'):
            Safety(travel).path(a, b, 20, 'step')
        travel['safety']['joint_max_deg'][2] = 125
        travel['safety']['assembly_half_extent_mm'] = [1, 1, 4]
        travel['safety']['link_radius_mm'] = 0.1
        travel['safety']['obstacles_mm'] = [[[201.9, -.1, 116.4], [202.1, .1, 116.6]]]
        for pose in (a, b):
            Safety(travel).path(pose, pose, 20, 'step')
        with self.assertRaisesRegex(ValueError, 'Swept envelope'):
            Safety(travel).path(a, b, 20, 'step')

    def test_stop_validates_settle_and_revokes_next_motion(self):
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.workflow.stop(simulation.now)
        self.assertEqual(simulation.workflow.state, State.STOPPING)
        simulation.until(lambda: simulation.workflow.state == State.STOPPED)
        self.assertIsNone(simulation.transport.travel)
        for _ in range(30):
            simulation.tick()
        self.assertEqual(len(simulation.transport.commands), 3)

    def test_camera_timeout_invalid_depth_and_lease_loss_stop(self):
        for issue in ('stale', 'depth', 'lease'):
            with self.subTest(issue=issue):
                simulation = Simulation()
                simulation.start()
                simulation.wait_for_step()
                if issue == 'stale':
                    simulation.camera_enabled = False
                elif issue == 'depth':
                    simulation.mock.depth_enabled = False
                else:
                    simulation.authorized = False
                simulation.until(lambda: simulation.workflow.state in (State.STOPPED, State.FAULT))
                self.assertIsNone(simulation.transport.travel)

    def test_controller_disconnect_fault_latches_restart_is_unhomed(self):
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.transport.connected = False
        simulation.until(lambda: simulation.workflow.state == State.FAULT)
        simulation.transport.connected = True
        simulation.tick()
        with self.assertRaisesRegex(ValueError, 'Inspect the fault'):
            simulation.command('home')
        restarted = Simulation()
        self.assertFalse(restarted.workflow.homed)
        self.assertIsNone(restarted.workflow.target)
        self.assertFalse(restarted.transport.commands)

    def test_alarm_readback_mismatch_and_unexpected_idle_motion(self):
        simulation = Simulation()
        simulation.transport.pose[0] += 1
        simulation.tick()
        self.assertEqual(simulation.workflow.state, State.FAULT)
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.transport.readback_offset[0] += .6
        simulation.until(lambda: simulation.workflow.state == State.FAULT)
        self.assertIn('readback', simulation.workflow.diagnostic)
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.transport.alarms = (2,)
        simulation.until(lambda: simulation.workflow.state == State.FAULT)
        self.assertIsNone(simulation.transport.travel)

    def test_stop_timeout_if_transport_keeps_moving(self):
        simulation = Simulation()
        simulation.start()
        simulation.wait_for_step()
        simulation.transport.ignore_stop = True
        a, b, begin, _ = simulation.transport.travel
        simulation.transport.travel = a, b, begin, begin + 20
        simulation.workflow.stop(simulation.now)
        simulation.until(lambda: simulation.workflow.state == State.FAULT)
        self.assertIn('stop could not be verified', simulation.workflow.diagnostic)
