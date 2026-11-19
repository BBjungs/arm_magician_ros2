"""Synthetic static workcell viewed from a translated camera."""

import cv2
import numpy as np


SCENARIOS = {
    'left': [(-115, 0)], 'right': [(115, 0)], 'up': [(0, -105)],
    'down': [(0, 105)], 'centered': [(0, 0)], 'corner': [(-125, 95)],
    'lost': [], 'multiple': [(-115, -38), (108, 48)],
}
JACOBIANS = {
    'normal': [[4.8, 0.], [0., 4.6]],
    'reversed': [[-4.8, 0.], [0., -4.6]],
    'coupled': [[-4.8, 1.35], [1.1, 4.6]],
    'singular': [[4.8, 4.8], [0., 0.]],
}


class MockCamera:
    def __init__(self, config):
        camera, servo = config['camera'], config['visual_servo']
        self.width = camera['width']
        self.height = camera['height']
        self.jacobian = np.asarray(JACOBIANS[servo['mock_jacobian']])
        self.scenario = servo['mock_scenario']
        self.reference = np.asarray(config['motion']['observation'][:2])
        self.depth_mm = round(camera['mock_depth_m'] * 1000)
        self.depth_enabled = True
        self.depth_valid = True

    def render(self, pose):
        width, height = self.width, self.height
        shift = self.jacobian @ (np.asarray(pose[:2]) - self.reference)
        image = np.full((height, width, 3), (29, 31, 32), np.uint8)
        depth = np.full((height, width), self.depth_mm + 30, np.uint16)
        for x in range(int(shift[0]) % 32, width, 32):
            cv2.line(image, (x, 0), (x, height-1), (43, 45, 46), 1)
        for y in range(int(shift[1]) % 32, height, 32):
            cv2.line(image, (0, y), (width-1, y), (43, 45, 46), 1)
        for i, (ex, ey) in enumerate(SCENARIOS[self.scenario]):
            u, v = round(width / 2 + ex + shift[0]), round(height / 2 + ey + shift[1])
            w, h = (27, 20) if i == 0 else (24, 18)
            cv2.rectangle(image, (u-w-4, v-h+5), (u+w+7, v+h+7), (15, 18, 20), -1)
            cv2.rectangle(image, (u-w, v-h), (u+w, v+h), (30, 175, 225), -1)
            cv2.rectangle(image, (u-w+3, v-h+3), (u+w-3, v+h-3), (48, 197, 251), -1)
            cv2.rectangle(depth, (u-w, v-h), (u+w, v+h), self.depth_mm, -1)
        if not self.depth_valid:
            depth.fill(0)
        return image, depth
