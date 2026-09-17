import json
import math
import time

import rclpy
from dobot_msgs.srv import EvaluatePTPTrajectory
from rcl_interfaces.msg import ParameterDescriptor, SetParametersResult
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray

from dobot_kinematics.collision_detection_server import PyBulletCollisionServer
from dobot_kinematics.dobot_forward_kin import calc_FwdKin
from dobot_kinematics.dobot_inv_kin import calc_inv_kin


class PoseValidatorService(Node):

    def __init__(self):
        super().__init__('dobot_trajectory_validation_server')
        self.create_service(
            EvaluatePTPTrajectory,
            'dobot_PTP_validation_service',
            self.PTP_trajectory_callback,
        )
        self.create_service(
            EvaluatePTPTrajectory,
            'dobot_calibration_validation_service',
            self.calibration_trajectory_callback,
        )
        self.create_subscription(
            Float64MultiArray,
            'dobot_pose_raw',
            self.tcp_position_callback,
            10,
        )
        self.collision_server = PyBulletCollisionServer()
        self.dobot_pose = []
        self.pose_received_monotonic = 0.0

        self._declare_axis_parameter(
            'axis_1_range',
            [-120, 120],
            'Allowed first-axis range in degrees.',
        )
        self._declare_axis_parameter(
            'axis_2_range',
            [-5, 90],
            'Allowed second-axis range in degrees.',
        )
        self._declare_axis_parameter(
            'axis_3_range',
            [-15, 90],
            'Allowed third-axis range in degrees.',
        )
        self._declare_axis_parameter(
            'axis_4_range',
            [-140, 140],
            'Allowed fourth-axis range in degrees.',
        )
        self.declare_parameter('enable_collision_check', True)
        self.declare_parameter('detect_ground_collision', True)
        self.declare_parameter('collision_step_mm', 2.0)
        self.declare_parameter('collision_joint_step_deg', 2.0)

        self.axis_1_range = self._range_from_parameter('axis_1_range')
        self.axis_2_range = self._range_from_parameter('axis_2_range')
        self.axis_3_range = self._range_from_parameter('axis_3_range')
        self.axis_4_range = self._range_from_parameter('axis_4_range')
        self.enable_collision_check = bool(
            self.get_parameter('enable_collision_check').value
        )
        self.detect_ground_collision = bool(
            self.get_parameter('detect_ground_collision').value
        )
        self.collision_step_mm = float(
            self.get_parameter('collision_step_mm').value
        )
        self.collision_joint_step_deg = float(
            self.get_parameter('collision_joint_step_deg').value
        )
        self.add_on_set_parameters_callback(self.parameters_callback)

    def _declare_axis_parameter(self, name, default, description):
        self.declare_parameter(
            name,
            default,
            ParameterDescriptor(description=description),
        )

    def _range_from_parameter(self, name):
        values = list(self.get_parameter(name).value)
        if len(values) != 2 or values[0] >= values[1]:
            raise ValueError(f'{name} must be [minimum, maximum]')
        return {'min': values[0], 'max': values[1]}

    def parameters_callback(self, params):
        ranges = {
            'axis_1_range': self.axis_1_range,
            'axis_2_range': self.axis_2_range,
            'axis_3_range': self.axis_3_range,
            'axis_4_range': self.axis_4_range,
        }
        try:
            for param in params:
                if param.name in ranges:
                    values = list(param.value)
                    if len(values) != 2 or values[0] >= values[1]:
                        raise ValueError(f'{param.name} must be [minimum, maximum]')
                    ranges[param.name].update(min=values[0], max=values[1])
                elif param.name == 'enable_collision_check':
                    self.enable_collision_check = bool(param.value)
                elif param.name == 'detect_ground_collision':
                    self.detect_ground_collision = bool(param.value)
                elif param.name == 'collision_step_mm':
                    if float(param.value) <= 0:
                        raise ValueError('collision_step_mm must be positive')
                    self.collision_step_mm = float(param.value)
                elif param.name == 'collision_joint_step_deg':
                    if float(param.value) <= 0:
                        raise ValueError('collision_joint_step_deg must be positive')
                    self.collision_joint_step_deg = float(param.value)
                else:
                    return SetParametersResult(
                        successful=False,
                        reason=f'Unsupported parameter: {param.name}',
                    )
        except (TypeError, ValueError) as exc:
            return SetParametersResult(successful=False, reason=str(exc))
        return SetParametersResult(successful=True)

    def tcp_position_callback(self, msg):
        if len(msg.data) < 4:
            return
        self.dobot_pose = [
            float(msg.data[0]) * 1000,
            float(msg.data[1]) * 1000,
            float(msg.data[2]) * 1000,
            float(msg.data[3]),
        ]
        self.pose_received_monotonic = time.monotonic()

    def PTP_trajectory_callback(self, request, response):
        response.is_valid, response.message = self.is_target_valid(
            list(request.target),
            int(request.motion_type),
        )
        return response

    def calibration_trajectory_callback(self, request, response):
        """Validate calibration MOVL targets without weakening normal safety."""
        response.is_valid = False
        target = list(request.target)
        if (
            int(request.motion_type) != 2
            or len(target) != 4
            or len(self.dobot_pose) != 4
            or time.monotonic() - self.pose_received_monotonic > 0.3
            or not all(math.isfinite(value) for value in target)
            or not all(math.isfinite(value) for value in self.dobot_pose)
        ):
            response.message = (
                'Calibration requires finite MOVL targets and fresh robot telemetry'
            )
            return response

        response.is_valid, response.message = self.is_target_valid(target, 2)
        return response

    def are_angles_in_range_joint(self, angles):
        if not isinstance(angles, (list, tuple)) or len(angles) < 4:
            return False
        return (
            self.axis_1_range['min'] < angles[0] < self.axis_1_range['max']
            and self.axis_2_range['min'] < angles[1] < self.axis_2_range['max']
            and self.axis_3_range['min'] < angles[2] < self.axis_3_range['max']
            and self.axis_4_range['min'] < angles[3] < self.axis_4_range['max']
        )

    def are_angles_in_range_cartesian(self, angles, position):
        if angles is False or len(angles) < 4 or len(position) < 2:
            return False
        joint_1_from_position = math.degrees(
            math.atan2(position[1], position[0])
        )
        joint_2 = angles[1]
        offset = max(0.0, joint_2 - 40.0)
        return (
            self.axis_1_range['min'] < angles[0] < self.axis_1_range['max']
            and self.axis_2_range['min'] < angles[1] < self.axis_2_range['max']
            and self.axis_3_range['min'] + offset
            < angles[2]
            < self.axis_3_range['max']
            and self.axis_4_range['min'] + joint_1_from_position
            < angles[3]
            < self.axis_4_range['max'] + joint_1_from_position
        )

    def _cartesian_limit_diagnostic(self, angles, position, sample_index,
                                    start_joint_vector, target_joint_vector):
        """Return the first failing joint with all data needed for a dry-run audit.

        `calc_inv_kin` presently exposes one analytic Dobot-convention branch;
        reporting that explicitly avoids claiming that another IK branch was tried.
        Start/target vectors are IK estimates from Cartesian telemetry, not a
        substitute for measured joint-state telemetry.
        """
        yaw = math.degrees(math.atan2(position[1], position[0]))
        ranges = [self.axis_1_range, self.axis_2_range, self.axis_3_range,
                  {'min': self.axis_4_range['min'] + yaw,
                   'max': self.axis_4_range['max'] + yaw}]
        # The Dobot Cartesian validator additionally constrains axis 3 as a
        # function of axis 2. Preserve the effective bound in the diagnostic.
        ranges[2] = dict(ranges[2])
        ranges[2]['min'] += max(0.0, angles[1] - 40.0)
        violated = next((index for index, (angle, limit) in enumerate(zip(angles, ranges))
                         if not limit['min'] < angle < limit['max']), None)
        if violated is None:
            return None
        return {
            'validator': 'dobot_kinematics.trajectory_validator_server.PoseValidatorService',
            'ik_implementation': 'dobot_kinematics.dobot_inv_kin.calc_inv_kin',
            'ik_branch': 'analytic_single_branch',
            'sample_index': int(sample_index),
            'cartesian_sample_xyzw_mm_deg': [float(value) for value in position],
            'violated_joint': f'axis_{violated + 1}',
            'sampled_joint_deg': float(angles[violated]),
            'configured_min_deg': float(ranges[violated]['min']),
            'configured_max_deg': float(ranges[violated]['max']),
            'sampled_joint_vector_deg': [float(value) for value in angles],
            'start_joint_vector_deg': [float(value) for value in start_joint_vector],
            'target_joint_vector_deg': [float(value) for value in target_joint_vector],
            'joint_vector_source': 'IK estimated from start/target Cartesian telemetry',
        }

    @staticmethod
    def _diagnostic_message(prefix, diagnostic):
        return prefix + ': ' + json.dumps(diagnostic, sort_keys=True)

    def _collision_safe(self, motion_type, target):
        if not self.enable_collision_check:
            return True, ''
        if len(self.dobot_pose) != 4:
            return False, 'Current TCP pose is unavailable for path validation'
        try:
            safe = self.collision_server.validate_trajectory(
                motion_type=motion_type,
                current_pose=self.dobot_pose,
                target_point=target,
                detect_ground=self.detect_ground_collision,
                step_len=self.collision_step_mm,
                joint_step_deg=self.collision_joint_step_deg,
            )
        except Exception as exc:
            return False, f'Collision validation failed: {exc}'
        if not safe:
            return False, 'A collision was detected during trajectory validation'
        return True, ''

    def _linear_waypoints(self, target):
        if len(self.dobot_pose) != 4:
            raise ValueError('Current TCP pose is unavailable for linear motion')
        return self.collision_server.linear_trajecory_to_discrete_waypoints(
            self.dobot_pose,
            target,
            step_len=self.collision_step_mm,
        )

    def is_target_valid(self, target, target_type):
        if len(target) != 4 or not all(math.isfinite(value) for value in target):
            return False, 'Target must contain four finite numeric values'

        collision_type = target_type
        collision_target = target

        if target_type == 4:
            if not self.are_angles_in_range_joint(target):
                return False, 'Joint limits violated'

        elif target_type == 5:
            cartesian_target = calc_FwdKin(target[0], target[1], target[2])
            collision_target = [
                float(cartesian_target[0]),
                float(cartesian_target[1]),
                float(cartesian_target[2]),
                target[3],
            ]
            try:
                waypoints = self._linear_waypoints(collision_target)
            except ValueError as exc:
                return False, str(exc)
            for point in waypoints:
                point.append(target[3])
                angles = calc_inv_kin(*point)
                if angles is False:
                    return False, 'Inverse kinematics solving error'
                if not self.are_angles_in_range_joint(angles):
                    return False, 'Joint limits violated along trajectory'
            collision_type = 2

        elif target_type == 1:
            angles = calc_inv_kin(*target)
            if angles is False:
                return False, 'Inverse kinematics solving error'
            if not self.are_angles_in_range_cartesian(angles, target):
                return False, 'Joint limits violated'

        elif target_type == 2:
            try:
                waypoints = self._linear_waypoints(target)
            except ValueError as exc:
                return False, str(exc)
            start_angles = calc_inv_kin(*self.dobot_pose)
            target_angles = calc_inv_kin(*target)
            if start_angles is False or target_angles is False:
                return False, 'Inverse kinematics solving error for trajectory endpoint'
            for sample_index, point in enumerate(waypoints):
                point.append(target[3])
                angles = calc_inv_kin(*point)
                if angles is False:
                    return False, 'Inverse kinematics solving error'
                if not self.are_angles_in_range_cartesian(angles, point):
                    diagnostic = self._cartesian_limit_diagnostic(
                        angles, point, sample_index, start_angles, target_angles)
                    return False, self._diagnostic_message(
                        'Joint limits violated along trajectory', diagnostic)

        else:
            return False, 'Unsupported trajectory type'

        collision_safe, reason = self._collision_safe(
            collision_type,
            collision_target,
        )
        if not collision_safe:
            return False, reason
        return True, 'Trajectory passed kinematics, limits, and collision checks'


def main(args=None):
    rclpy.init(args=args)
    node = PoseValidatorService()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
