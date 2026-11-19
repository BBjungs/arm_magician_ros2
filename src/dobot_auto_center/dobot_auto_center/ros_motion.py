"""ROS action transport for the private, capability-gated motion controller."""

from action_msgs.msg import GoalStatus
from rclpy.action import ActionClient, ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.task import Future

from dobot_auto_center.action import GuardedMove

from .motion import Result


class PendingAction:
    def __init__(self, response, deadline):
        self.response = response
        self.handle = None
        self.result = None
        self.cancel_sent = False
        self.cancel_requested = False
        self.deadline = deadline

    def cancel(self):
        self.cancel_requested = True
        if self.handle and not self.cancel_sent:
            self.handle.cancel_goal_async()
            self.cancel_sent = True

    def poll(self, now):
        self.connect_response()
        if not self.response.done():
            return self.on_timeout(now)
        if self.handle is None or not self.handle.accepted:
            return Result('rejected', 'Guarded action rejected', (), now)
        if self.result is None or not self.result.done():
            return self.on_timeout(now)
        try:
            wrapped = self.result.result()
        except Exception:
            return Result('fault', 'Action result unavailable', (), now)
        msg = wrapped.result
        if wrapped.status == GoalStatus.STATUS_SUCCEEDED and msg.code != 'ok':
            return Result('fault', 'Inconsistent action completion', (), now)
        if wrapped.status != GoalStatus.STATUS_SUCCEEDED and msg.code == 'ok':
            return Result('fault', 'Action did not complete successfully', (), now)
        return Result(msg.code, msg.diagnostic, tuple(msg.tcp_mm_deg), msg.settled_stamp)

    def connect_response(self):
        if not self.response.done() or self.handle is not None:
            return
        try:
            self.handle = self.response.result()
        except Exception:
            return
        if self.handle is not None and self.handle.accepted:
            self.result = self.handle.get_result_async()
            if self.cancel_requested:
                self.cancel()

    def on_timeout(self, now):
        if now <= self.deadline:
            return None
        self.cancel()
        self.response.add_done_callback(lambda _: self.connect_response())
        return Result('fault', 'Action response timed out. Motion state requires inspection', (), now)


class ActionBridge:
    def __init__(self, node, motion, lock, clock):
        self.motion = motion
        self.lock = lock
        self.clock = clock
        self.active = None
        self.workflow = None
        group = ReentrantCallbackGroup()
        name = '~/guarded_move'
        self.server = ActionServer(node, GuardedMove, name, execute_callback=self.execute,
                                   goal_callback=self.accept, cancel_callback=self.cancel,
                                   callback_group=group)
        self.client = ActionClient(node, GuardedMove, name, callback_group=group)

    def submit(self, permit, operation, tcp, speed, now):
        if not self.client.server_is_ready():
            raise RuntimeError('Motion action server unavailable')
        goal = GuardedMove.Goal(permit=permit, operation=operation,
                               tcp_mm_deg=list(map(float, tcp)), speed_mm_s=float(speed))
        return PendingAction(self.client.send_goal_async(goal),
                             now + 3 * self.motion.config['timeout'])

    def accept(self, goal):
        with self.lock:
            allowed = self.motion.authorized_goal(goal.permit, goal.operation,
                                                  goal.tcp_mm_deg, goal.speed_mm_s, self.clock())
        return GoalResponse.ACCEPT if allowed else GoalResponse.REJECT

    def cancel(self, _handle):
        return CancelResponse.ACCEPT

    async def execute(self, handle):
        with self.lock:
            goal = handle.request
            result = self.motion.begin(goal.permit, goal.operation, goal.tcp_mm_deg,
                                       goal.speed_mm_s, self.clock(), self.workflow.guard)
            if result is None:
                completion = Future()
                self.active = handle, completion
        if result is None:
            result = await completion
        if result.code == 'ok' and not handle.is_cancel_requested:
            handle.succeed()
        elif handle.is_cancel_requested:
            handle.canceled()
            if result.code == 'ok':
                result = Result('stopped', 'Action canceled after the robot settled',
                                result.pose, result.stamp)
        else:
            handle.abort()
        return GuardedMove.Result(code=result.code, diagnostic=result.reason,
                                  tcp_mm_deg=list(result.pose), settled_stamp=result.stamp)

    def tick(self):
        if self.active is None:
            return
        handle, completion = self.active
        if handle.is_cancel_requested and self.motion.active and not self.motion.active.stopped:
            self.workflow.stop(self.clock(), 'Motion action canceled')
        if self.motion.result is not None:
            completion.set_result(self.motion.result)
            self.active = None
            return
        snapshot = self.motion.snapshot
        phase = ('STOPPING' if self.motion.active.stopped else
                 'MOVING' if snapshot.moving else 'SETTLING')
        handle.publish_feedback(GuardedMove.Feedback(phase=phase, tcp_mm_deg=list(snapshot.pose)))

    def destroy(self):
        self.server.destroy()
        self.client.destroy()
