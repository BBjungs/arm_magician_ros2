import time
import numpy as np
import pybullet as pyb
import pybullet_data
import os.path as path
import sys
from math import radians
from dobot_kinematics.collision_utils import NamedCollisionObject, CollisionDetector
import math
from dobot_kinematics.dobot_inv_kin import calc_inv_kin
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory



global model_config


class PyBulletCollisionServer():


    @staticmethod
    def load_environment(client_id):
        description_share = Path(get_package_share_directory('dobot_description'))
        pyb.setAdditionalSearchPath(
            str(description_share.parent),
            physicsClientId=client_id,
        )

        tool_mounted = os.environ.get('MAGICIAN_TOOL', 'none')
        model_names = {
            'none': '3DOF.urdf',
            'pen': 'pen.urdf',
            'suction_cup': 'suction_cup.urdf',
            'gripper': 'gripper.urdf',
            'extended_gripper': 'extended_gripper.urdf',
        }
        if tool_mounted not in model_names:
            raise ValueError(f'Unsupported MAGICIAN_TOOL: {tool_mounted}')
        path_to_collision_model = (
            description_share
            / 'meshes'
            / 'collision'
            / 'urdf_models'
            / model_names[tool_mounted]
        )


        global model_config
        prefix, model_config = os.path.split(str(path_to_collision_model))

        dobot_magician_id = pyb.loadURDF(
            str(path_to_collision_model),
            [0, 0, 0],
            useFixedBase=True,
            physicsClientId=client_id,
        )

        ground_id = pyb.loadURDF(
            str(Path(pybullet_data.getDataPath()) / 'plane.urdf'),
            [0, 0, -0.131305],
            useFixedBase=True,
            physicsClientId=client_id,
        )

        bodies = {
            "robot": dobot_magician_id,
            "ground": ground_id,
        }

        for id in bodies.values():
            if id <= -1 :
                raise RuntimeError("Could not load URDF collision model")

        return bodies


    @staticmethod
    def set_robot_configuration(angles):
        """Set robot configuration."""
        q = np.zeros(4)
        q[0] = radians(angles[0])
        q[1] = radians(angles[1])
        q[2] = radians(angles[2]) - q[1]
        q[3] = -(q[1]+q[2])
        return q

    @staticmethod
    def update_robot_configuration(robot_id, q, gui_id):
        """Set the robot configuration."""
        for i in range(4):
            pyb.resetJointState(
                robot_id, i+1, q[i], physicsClientId = gui_id
            )


    @staticmethod
    def linear_trajecory_to_discrete_waypoints(start, target, step_len = 0.5):
        if len(start) < 3 or len(target) < 3:
            raise ValueError('start and target poses must contain x, y, z')
        if step_len <= 0:
            raise ValueError('step_len must be positive')
        start_xyz = [float(value) for value in start[:3]]
        target_xyz = [float(value) for value in target[:3]]
        distance = math.dist(start_xyz, target_xyz)
        steps_num = max(2, int(math.ceil(distance / step_len)) + 1)
        return [
            [
                start_xyz[axis]
                + (target_xyz[axis] - start_xyz[axis]) * step / (steps_num - 1)
                for axis in range(3)
            ]
            for step in range(steps_num)
        ]

    
    def validate_trajectory(
        self,
        motion_type,
        current_pose,
        target_point,
        detect_ground,
        step_len=2.0,
        joint_step_deg=2.0,
    ):
        # MOTION_TYPE_MOVJ_XYZ 1
        # MOTION_TYPE_MOVL_XYZ 2
        # MOTION_TYPE_MOVJ_ANGLE 4
        # MOTION_TYPE_MOVL_ANGLE 5
        col_id = pyb.connect(pyb.DIRECT)

        if col_id == -1:
            raise RuntimeError("Could not start PyBullet collision server")

        try:
            collision_bodies = PyBulletCollisionServer.load_environment(col_id)

            robot_id = collision_bodies["robot"]

            end_effector_link = NamedCollisionObject("robot", "magician_link_4")
            if model_config != "3DOF.urdf":
                gripper = NamedCollisionObject("robot", "end_effector_part")
            base = NamedCollisionObject("robot", "magician_base_link")
            link1 = NamedCollisionObject("robot", "magician_link_1")
            ground = NamedCollisionObject("ground")


            pairs = [(end_effector_link, base), (end_effector_link, link1)]
            if detect_ground:
                pairs.append((end_effector_link, ground))
            if model_config != "3DOF.urdf":
                pairs.extend([(gripper, base), (gripper, link1)])
                if detect_ground:
                    pairs.append((gripper, ground))
            col_detector = CollisionDetector(col_id, collision_bodies, pairs)
        

            if motion_type == 1 or motion_type == 4:
                if motion_type == 1:
                    target_angles = calc_inv_kin(*target_point)
                    if target_angles is False:
                        return False
                else:
                    target_angles = [float(value) for value in target_point]
                if len(current_pose) != 4:
                    raise ValueError('Current TCP pose is unavailable for MOVJ validation')
                current_angles = calc_inv_kin(*current_pose)
                if current_angles is False:
                    return False
                if joint_step_deg <= 0:
                    raise ValueError('joint_step_deg must be positive')
                max_delta = max(
                    abs(target_angles[index] - current_angles[index])
                    for index in range(4)
                )
                step_count = max(
                    2,
                    int(math.ceil(max_delta / joint_step_deg)) + 1,
                )
                for step in range(step_count):
                    ratio = step / (step_count - 1)
                    angles = [
                        current_angles[index]
                        + (target_angles[index] - current_angles[index]) * ratio
                        for index in range(4)
                    ]
                    q = self.set_robot_configuration(angles[0:3])
                    self.update_robot_configuration(robot_id, q, gui_id=col_id)
                    pyb.stepSimulation(physicsClientId=col_id)
                    if col_detector.in_collision(q, margin=0.0):
                        return False
                return True

            if motion_type == 2:
                waypoints = self.linear_trajecory_to_discrete_waypoints(
                    current_pose,
                    target_point,
                    step_len=step_len,
                )
                for point in waypoints:
                    point.append(float(target_point[3]))
                    angles = calc_inv_kin(*point)
                    if angles is False:
                        return False
                    q = self.set_robot_configuration(angles[0:3])
                    self.update_robot_configuration(robot_id, q, gui_id=col_id)
                    pyb.stepSimulation(physicsClientId=col_id)
                    if col_detector.in_collision(q, margin=0.0):
                        return False
                return True

            raise ValueError(f'Unsupported collision motion type: {motion_type}')
        finally:
            pyb.disconnect(col_id)
