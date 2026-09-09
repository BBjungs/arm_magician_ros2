import math
from threading import Event, Lock
import time

from dobot_driver.dobot_handle import bot
from dobot_msgs.action import PointToPoint
from dobot_msgs.msg import DobotAlarmCodes
from dobot_msgs.srv import EvaluatePTPTrajectory
import rclpy
from rcl_interfaces.msg import SetParametersResult
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64MultiArray

from .PTP_params_class import declare_PTP_params


class DobotPTPServer(Node):

    def __init__(self):
        super().__init__('dobot_PTP_server')

        self.declare_parameter('validation_timeout_sec', 15.0)
        self.declare_parameter('pose_wait_timeout_sec', 5.0)
        self.declare_parameter('motion_timeout_sec', 60.0)
        self.declare_parameter('state_timeout_sec', 1.0)

        self.validation_timeout_sec = float(
            self.get_parameter('validation_timeout_sec').value
        )
        self.pose_wait_timeout_sec = float(
            self.get_parameter('pose_wait_timeout_sec').value
        )
        self.motion_timeout_sec = float(
            self.get_parameter('motion_timeout_sec').value
        )

        self.state_timeout_sec = float(self.get_parameter('state_timeout_sec').value)
        if not math.isfinite(self.state_timeout_sec) or self.state_timeout_sec <= 0:
            raise ValueError('state_timeout_sec must be finite and positive')

        callback_group = ReentrantCallbackGroup()
        self._action_server = ActionServer(
            self,
            PointToPoint,
            'PTP_action',
            execute_callback=self.execute_callback,
            callback_group=callback_group,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
        )

        self.create_subscription(
            JointState,
            'dobot_joint_states',
            self.joints_positions_callback,
            10,
        )
        self.create_subscription(
            Float64MultiArray,
            'dobot_pose_raw',
            self.tcp_position_callback,
            10,
        )
        self.create_subscription(
            DobotAlarmCodes,
            'dobot_alarms',
            self.active_alarms_callback,
            10,
        )

        self.client_validate_goal = self.create_client(
            srv_type=EvaluatePTPTrajectory,
            srv_name='dobot_PTP_validation_service',
            callback_group=callback_group,
        )
        if not self.client_validate_goal.wait_for_service(timeout_sec=15.0):
            raise RuntimeError('Trajectory validation service is not available')

        self.motion_types_list = [1, 2, 4, 5]
        self.motion_type = None
        self.dobot_pose = []
        self.active_alarms = False
        self._pose_received_at = None
        self._alarms_received_at = None
        self._pose_event = Event()
        self._state_lock = Lock()
        self._goal_reserved = False

        declare_PTP_params(self)
        self._load_declared_parameter_values()
        self.allow_dynamic_reconfigure_joints = False
        self.allow_dynamic_reconfigure_cartesian = False
        self.add_on_set_parameters_callback(self.parameters_callback)

    def _load_declared_parameter_values(self):
        self.joint_params_dict = {
            name: self.get_parameter(name).value for name in self.joint_params_names
        }
        self.cartesian_params_dict = {
            name: self.get_parameter(name).value
            for name in self.cartesian_params_names
        }

    def set_initial_params_values(self):
        self.send_joint_parameters()
        self.send_cartesian_parameters()
        self.allow_dynamic_reconfigure_joints = True
        self.allow_dynamic_reconfigure_cartesian = True

    def send_joint_parameters(self):
        params = [self.joint_params_dict[name] for name in self.joint_params_names]
        if any(value is None for value in params):
            raise RuntimeError('PTP joint parameters are incomplete')
        bot.set_point_to_point_joint_params(params[0:4], params[4:8])

    def send_cartesian_parameters(self):
        params = [
            self.cartesian_params_dict[name]
            for name in self.cartesian_params_names
        ]
        if any(value is None for value in params):
            raise RuntimeError('PTP Cartesian parameters are incomplete')
        bot.set_point_to_point_coordinate_params(*params)

    def parameters_callback(self, params):
        joint_changed = False
        cartesian_changed = False
        for param in params:
            if param.name in self.joint_params_names:
                self.joint_params_dict[param.name] = param.value
                joint_changed = True
            elif param.name in self.cartesian_params_names:
                self.cartesian_params_dict[param.name] = param.value
                cartesian_changed = True
            elif param.name in {
                'validation_timeout_sec',
                'pose_wait_timeout_sec',
                'motion_timeout_sec',
                'state_timeout_sec',
            }:
                if not math.isfinite(float(param.value)) or float(param.value) <= 0:
                    return SetParametersResult(successful=False)
                setattr(self, param.name, float(param.value))
            else:
                return SetParametersResult(successful=False)

        try:
            if joint_changed and self.allow_dynamic_reconfigure_joints:
                self.send_joint_parameters()
            if cartesian_changed and self.allow_dynamic_reconfigure_cartesian:
                self.send_cartesian_parameters()
        except Exception as exc:
            return SetParametersResult(successful=False, reason=str(exc))
        return SetParametersResult(successful=True)

    def send_request_check_trajectory(self, target_point, motion_type):
        request = EvaluatePTPTrajectory.Request()
        request.target = target_point
        request.motion_type = motion_type
        future = self.client_validate_goal.call_async(request)
        completed = Event()
        future.add_done_callback(lambda _future: completed.set())
        if not completed.wait(timeout=self.validation_timeout_sec):
            raise TimeoutError('Trajectory validation timed out')
        return future.result()

    def joints_positions_callback(self, msg):
        with self._state_lock:
            if self.motion_type not in [3, 4, 5, 6] or len(msg.position) < 4:
                return
            if not all(math.isfinite(v) for v in msg.position[:4]):
                self._pose_received_at = None
                return
            self.dobot_pose = [
                math.degrees(msg.position[0]),
                math.degrees(msg.position[1]),
                math.degrees(msg.position[2]),
                math.degrees(msg.position[3]),
            ]
            self._pose_received_at = time.monotonic()
            self._pose_event.set()

    def tcp_position_callback(self, msg):
        with self._state_lock:
            if self.motion_type not in [0, 1, 2, 7, 8, 9] or len(msg.data) < 4:
                return
            if not all(math.isfinite(v) for v in msg.data[:4]):
                self._pose_received_at = None
                return
            self.dobot_pose = [
                float(msg.data[0]) * 1000,
                float(msg.data[1]) * 1000,
                float(msg.data[2]) * 1000,
                float(msg.data[3]),
            ]
            self._pose_received_at = time.monotonic()
            self._pose_event.set()

    def active_alarms_callback(self, msg):
        with self._state_lock:
            self.active_alarms = bool(msg.alarms_list)
            self._alarms_received_at = time.monotonic()

    def _state_is_fresh(self):
        with self._state_lock:
            now = time.monotonic()
            return (
                self._pose_received_at is not None
                and self._alarms_received_at is not None
                and 0 <= now - self._pose_received_at <= self.state_timeout_sec
                and 0 <= now - self._alarms_received_at <= self.state_timeout_sec
                and len(self.dobot_pose) == 4
                and all(math.isfinite(v) for v in self.dobot_pose)
            )

    def _reserve_goal(self, motion_type):
        with self._state_lock:
            if self._goal_reserved:
                return False
            self._goal_reserved = True
            self.motion_type = motion_type
            self._pose_received_at = None
            self._pose_event.clear()
            return True

    def _release_goal(self):
        with self._state_lock:
            self._goal_reserved = False
            self.motion_type = None
            self._pose_event.clear()

    def _current_pose(self):
        with self._state_lock:
            return list(self.dobot_pose)

    @staticmethod
    def is_ratio_valid(ratio):
        return 0.0 < ratio <= 1.0 and int(ratio * 100) != 0

    def goal_callback(self, goal_request):
        """Accept one validated motion goal at a time."""
        motion_type = int(goal_request.motion_type)
        target = list(goal_request.target_pose)

        if motion_type not in self.motion_types_list:
            self.get_logger().warn('Goal rejected: unsupported motion type')
            return GoalResponse.REJECT
        if not self.is_ratio_valid(goal_request.velocity_ratio):
            self.get_logger().warn('Goal rejected: invalid velocity ratio')
            return GoalResponse.REJECT
        if not self.is_ratio_valid(goal_request.acceleration_ratio):
            self.get_logger().warn('Goal rejected: invalid acceleration ratio')
            return GoalResponse.REJECT
        if self.active_alarms:
            self.get_logger().warn('Goal rejected because robot alarms are active')
            return GoalResponse.REJECT
        if not self._reserve_goal(motion_type):
            self.get_logger().warn('Goal rejected because another goal is active')
            return GoalResponse.REJECT

        accepted = False
        try:
            validation = self.send_request_check_trajectory(target, motion_type)
            if validation is None or not validation.is_valid:
                message = getattr(validation, 'message', 'no validation response')
                self.get_logger().warn(f'Goal rejected: {message}')
                return GoalResponse.REJECT

            if not self._pose_event.wait(timeout=self.pose_wait_timeout_sec):
                self.get_logger().warn('Goal rejected: current robot pose is stale')
                return GoalResponse.REJECT

            if self.active_alarms or not self._state_is_fresh():
                self.get_logger().warn('Goal rejected: alarms or stale robot state')
                return GoalResponse.REJECT
            velocity = int(goal_request.velocity_ratio * 100)
            acceleration = int(goal_request.acceleration_ratio * 100)
            bot.set_point_to_point_common_params(velocity, acceleration)
            accepted = True
            self.get_logger().info(
                f'Goal accepted: motion_type={motion_type}, target={target}'
            )
            return GoalResponse.ACCEPT
        except Exception as exc:
            self.get_logger().error(f'Goal validation failed: {exc}')
            return GoalResponse.REJECT
        finally:
            if not accepted:
                self._release_goal()

    def cancel_callback(self, _goal_handle):
        self.get_logger().info('Received cancel request')
        return CancelResponse.ACCEPT

    @staticmethod
    def is_goal_reached(target_pose, current_pose, threshold):
        if len(target_pose) != 4 or len(current_pose) != 4:
            return False
        return all(
            abs(target_pose[index] - current_pose[index]) <= threshold
            for index in range(4)
        )

    @staticmethod
    def is_pose_stable(pose_history, threshold=0.05):
        if len(pose_history) < 2:
            return False
        return all(
            abs(pose_history[-1][index] - pose_history[-2][index]) <= threshold
            for index in range(4)
        )

    def _stop_motion(self):
        try:
            bot.stop_queue(force=True)
            bot.clear_queue()
            bot.start_queue()
            return True
        except Exception as exc:
            self.get_logger().error(f'Failed to stop Dobot queue: {exc}')
            return False

    def execute_callback(self, goal_handle):
        """Execute a reserved goal with cancellation and a motion watchdog."""
        target = list(goal_handle.request.target_pose)
        motion_type = int(goal_handle.request.motion_type)
        result = PointToPoint.Result()
        pose_history = []
        deadline = time.monotonic() + self.motion_timeout_sec

        try:
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
                result.achieved_pose = self._current_pose() or [0.0] * 4
                return result
            if self.active_alarms or not self._state_is_fresh():
                goal_handle.abort()
                result.achieved_pose = self._current_pose() or [0.0] * 4
                self.get_logger().error('Goal aborted before dispatch: unsafe robot state')
                return result
            bot.set_point_to_point_command(motion_type, *target)

            while time.monotonic() < deadline:
                current_pose = self._current_pose()
                if goal_handle.is_cancel_requested:
                    if self._stop_motion():
                        goal_handle.canceled()
                        self.get_logger().info('Goal canceled')
                    else:
                        goal_handle.abort()
                        self.get_logger().error('Cancel failed: queue stop failed')
                    result.achieved_pose = current_pose or [0.0] * 4
                    return result

                if self.active_alarms:
                    self._stop_motion()
                    goal_handle.abort()
                    result.achieved_pose = current_pose or [0.0] * 4
                    self.get_logger().error('Goal aborted because robot alarms are active')
                    return result

                if not self._state_is_fresh():
                    self._stop_motion()
                    goal_handle.abort()
                    result.achieved_pose = current_pose or [0.0] * 4
                    self.get_logger().error('Goal aborted because robot state is stale')
                    return result

                if (
                    self.is_goal_reached(target, current_pose, 0.2)
                    and self.is_pose_stable(pose_history)
                ):
                    goal_handle.succeed()
                    result.achieved_pose = current_pose
                    self.get_logger().info(f'Goal reached: {current_pose}')
                    return result

                if len(current_pose) == 4:
                    feedback = PointToPoint.Feedback()
                    feedback.current_pose = current_pose
                    goal_handle.publish_feedback(feedback)
                    pose_history.append(current_pose)
                    pose_history = pose_history[-2:]

                time.sleep(0.1)

            self._stop_motion()
            goal_handle.abort()
            result.achieved_pose = self._current_pose() or [0.0] * 4
            self.get_logger().error('Goal aborted because motion timed out')
            return result
        except Exception as exc:
            self._stop_motion()
            goal_handle.abort()
            result.achieved_pose = self._current_pose() or [0.0] * 4
            self.get_logger().error(f'Goal execution failed: {exc}')
            return result
        finally:
            self._release_goal()

    def destroy(self):
        self._action_server.destroy()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    action_server = DobotPTPServer()
    action_server.set_initial_params_values()
    executor = MultiThreadedExecutor()
    try:
        rclpy.spin(action_server, executor=executor)
    finally:
        action_server.destroy()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
