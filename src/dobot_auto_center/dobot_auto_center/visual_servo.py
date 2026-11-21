"""Estimate a local 2D image Jacobian from measured TCP and pixel displacement."""

import numpy as np


class VisualServo:
    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.target_center = self.pixel_error = None
        self.samples = []
        self.jacobian = None
        self.stable = 0
        self.corrections = 0
        self.increases = 0
        self.previous_error = None

    def observe(self, target, width, height):
        self.target_center = target.center if target else None
        self.pixel_error = target.error(width, height) if target else None

    def record_probe(self, before_tcp, after_tcp, before_error, after_error):
        self.samples.append((np.subtract(after_tcp[:2], before_tcp[:2]),
                             np.subtract(after_error, before_error)))
        if len(self.samples) == 2:
            travel, pixels = map(np.asarray, zip(*self.samples))
            if np.linalg.matrix_rank(travel) != 2 or np.linalg.cond(travel) > 8:
                raise ValueError('Identification probes did not span independent TCP axes')
            jacobian = np.linalg.solve(travel, pixels).T
            singular_values = np.linalg.svd(jacobian, compute_uv=False)
            if (singular_values[-1] < self.config['minimum_singular_value']
                    or singular_values[0] / singular_values[-1]
                    > self.config['maximum_condition_number']):
                raise ValueError('Image Jacobian is singular or ill-conditioned')
            self.jacobian = jacobian

    def step(self, error, maximum_step):
        jacobian = self.jacobian
        damping = self.config['damping']
        delta = -self.config['gain'] * jacobian.T @ np.linalg.solve(
            jacobian @ jacobian.T + damping ** 2 * np.eye(2), error)
        magnitude = np.linalg.norm(delta)
        if magnitude > maximum_step:
            delta *= maximum_step / magnitude
        return delta

    def note_correction(self, error):
        magnitude = np.linalg.norm(error)
        if self.previous_error is not None:
            increased = magnitude > self.previous_error + self.config['error_jitter_pixels']
            self.increases = self.increases + 1 if increased else 0
        self.previous_error = magnitude
        if self.increases >= self.config['maximum_error_increases']:
            raise ValueError('Image error increased after consecutive corrections')
