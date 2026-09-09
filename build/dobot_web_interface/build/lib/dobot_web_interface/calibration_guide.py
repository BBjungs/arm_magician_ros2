"""Display-only board geometry. Predicted corners never enter calibration solves."""

import base64

import cv2
import numpy as np

from dobot_vision_yolo.aruco_board import detect_markers, marker_corners_board


GREEN = (70, 190, 35)
RED = (65, 65, 240)
YELLOW = (30, 205, 250)


def measurement_spans(board):
    """Two independent, physical centre-to-centre spans from the configured board."""
    centers = [(int(key), np.asarray(value['center_mm'][:2], dtype=float))
               for key, value in board['markers'].items()]
    spans = []
    for axis in (0, 1):
        candidates = [(a, b) for a in centers for b in centers
                      if b[1][axis] > a[1][axis]
                      and abs(a[1][1 - axis] - b[1][1 - axis]) < 0.01]
        if not candidates:
            raise ValueError('Board needs horizontal and vertical measurement references')
        a, b = max(candidates, key=lambda pair: pair[1][1][axis] - pair[0][1][axis])
        spans.append({'axis': axis, 'ids': [a[0], b[0]],
                      'points_mm': [a[1].tolist(), b[1].tolist()],
                      'expected_mm': float(np.linalg.norm(b[1] - a[1]))})
    return spans


def validate_measurements(board, values):
    if not isinstance(values, list) or len(values) != 2:
        raise ValueError('Measure both marked distances in millimeters')
    for span, value in zip(measurement_spans(board), values):
        if isinstance(value, bool):
            raise ValueError('Enter a measured distance in millimeters')
        measured = float(value)
        # Maximum 1% scale error on either axis; never rescale robot coordinates.
        if not np.isfinite(measured) or abs(measured - span['expected_mm']) > span['expected_mm'] * 0.01:
            raise ValueError('Printed size does not match. Reprint at 100% / Actual size and measure again')
    return [float(value) for value in values]


def board_guide(frame, board, measured=False, axis=0, observation=None):
    observation = observation if observation is not None else detect_markers(cv2, frame, board['dictionary'])
    ids = observation.get('detected_ids', [])
    corners = observation.get('corners', [])
    observed = {int(key): np.asarray(value).reshape(4, 2) for key, value in zip(ids, corners)}
    required = [int(key) for key in board['required_ids']]
    missing = [key for key in required if key not in observed]
    local, pixels = [], []
    for key, points in observed.items():
        marker = board['markers'].get(str(key))
        if marker:
            local.extend(marker_corners_board(marker, board['marker_length_mm'])[:, :2])
            pixels.extend(points)
    transform = None
    if len(local) >= 4:
        transform, _ = cv2.findHomography(np.asarray(local), np.asarray(pixels), cv2.RANSAC, 3.0)

    def project(points):
        if transform is None:
            return None
        result = cv2.perspectiveTransform(np.asarray(points, dtype=float).reshape(1, -1, 2), transform)[0]
        return result.tolist() if np.isfinite(result).all() and np.max(np.abs(result)) < 100000 else None

    image = frame.copy()
    markers = []

    def line(a, b, color, dashed=False):
        a, b = np.asarray(a), np.asarray(b)
        if dashed:
            length = max(1, int(np.linalg.norm(b - a) / 8))
            for step in range(0, length, 2):
                cv2.line(image, tuple((a + (b - a) * step / length).astype(int)),
                         tuple((a + (b - a) * min(step + 1, length) / length).astype(int)), color, 2)
        else:
            cv2.line(image, tuple(a.astype(int)), tuple(b.astype(int)), color, 2)

    for key in sorted(set(required + list(observed))):
        found = key in observed
        points = observed[key].tolist() if found else project(
            marker_corners_board(board['markers'][str(key)], board['marker_length_mm'])[:, :2])
        markers.append({'id': key, 'detected': found, 'corners': points, 'predicted': not found})
        if points:
            color = GREEN if found else RED
            for a, b in zip(points, points[1:] + points[:1]):
                line(a, b, color, not found)
            origin = tuple(np.mean(points, axis=0).astype(int))
            cv2.putText(image, str(key) if found else f'{key} missing (expected)', origin,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    axes = project([[0, 0], [25, 0], [0, 25]])
    if axes:
        for point, label in zip(axes, ['O', 'X', 'Y']):
            line(axes[0], point, YELLOW)
            cv2.putText(image, label, tuple(np.asarray(point, dtype=int)), cv2.FONT_HERSHEY_SIMPLEX, .6, YELLOW, 2)
    # Outline the actual configured board, without inventing hidden observations.
    all_corners = np.concatenate([marker_corners_board(marker, board['marker_length_mm'])[:, :2]
                                  for marker in board['markers'].values()])
    lo, hi = all_corners.min(axis=0), all_corners.max(axis=0)
    outline = project([lo, [hi[0], lo[1]], hi, [lo[0], hi[1]]])
    if outline:
        for a, b in zip(outline, outline[1:] + outline[:1]):
            line(a, b, GREEN if not missing else YELLOW, True)
    spans = measurement_spans(board)
    span = dict(spans[int(axis)])
    span['points_pixel'] = project(span['points_mm'])
    span['validated'] = measured
    # Measurements are requested only with both real endpoints visible.
    span['visible'] = all(key in observed for key in span['ids'])
    if span['points_pixel']:
        a, b = [tuple(np.asarray(point, dtype=int)) for point in span['points_pixel']]
        color = GREEN if measured else YELLOW
        cv2.arrowedLine(image, a, b, color, 3, tipLength=.07)
        cv2.arrowedLine(image, b, a, color, 3, tipLength=.07)
        for point, label in [(a, 'A'), (b, 'B')]:
            cv2.circle(image, point, 6, color, -1)
            cv2.putText(image, label, (point[0] + 8, point[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, .8, color, 2)
        mid = tuple(((np.asarray(a) + b) / 2).astype(int))
        cv2.putText(image, 'Scale OK' if measured else 'Measure from A to B (mm)', mid,
                    cv2.FONT_HERSHEY_SIMPLEX, .55, color, 2)
    ok, jpeg = cv2.imencode('.jpg', image)
    if not ok:
        raise ValueError('Could not encode calibration guide')
    return {'image': 'data:image/jpeg;base64,' + base64.b64encode(jpeg).decode('ascii'),
            'width': image.shape[1], 'height': image.shape[0], 'markers': markers,
            'missing_ids': missing, 'measurement': span, 'axes': axes,
            'instruction': (f'Marker {missing[0]} not detected. Move the board or camera until Marker {missing[0]} is fully visible.'
                            if missing else 'Keep the board and robot still.'),
            'projection_available': transform is not None}
