import asyncio
import re
import shutil
import subprocess
import threading
import time
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from dobot_vision_yolo.aruco_board import default_aruco_board, marker_corners_board
from dobot_web_interface.calibration_capture import validate_stationary_capture
from dobot_web_interface.calibration_print import calibration_print_page
from dobot_web_interface.web_interface import DobotWebNode, create_app


class PrintNode:
    api_token = ''
    get_calibration_board_svg = DobotWebNode.get_calibration_board_svg

    def _eye_in_hand(self):
        return SimpleNamespace(load=lambda: {'aruco': {'board': default_aruco_board()}})


def get_response(url):
    async def request():
        path, _, query = url.partition('?')
        events = []

        async def receive():
            return {'type': 'http.request', 'body': b'', 'more_body': False}

        async def send(event):
            events.append(event)

        await create_app(PrintNode())({
            'type': 'http', 'http_version': '1.1', 'method': 'GET', 'scheme': 'http',
            'path': path, 'raw_path': path.encode(), 'query_string': query.encode(),
            'root_path': '', 'headers': [], 'server': ('test', 80), 'client': ('test', 1),
        }, receive, send)
        start = next(e for e in events if e['type'] == 'http.response.start')
        body = b''.join(e.get('body', b'') for e in events if e['type'] == 'http.response.body')
        return SimpleNamespace(
            status_code=start['status'],
            headers={k.decode(): v.decode() for k, v in start['headers']},
            text=body.decode(),
        )
    return asyncio.run(request())


def test_print_route_and_physical_dimensions():
    response = get_response('/api/vision/calibration/print')
    assert response.status_code == 200
    assert response.headers['cache-control'] == 'no-store'
    page = response.text
    assert 'size: A4 portrait; margin: 10mm' in page
    assert 'width="130.000mm" height="210.000mm"' in page
    assert 'center span: 80 × 160 mm' in page
    assert 'BOARD ORIGIN (0,0,0)' in page
    assert 'MUST measure before calibration' in page
    assert 'print ID' in page
    assert page.count('data:image/png;base64,') == 4
    assert 'board X=' in page and 'base X=' not in page
    assert get_response(
        '/api/vision/calibration/print?mode=invalid'
    ).status_code == 400


def record(pose=None, delta=20, **kwargs):
    return dict(tcp_pose_mm_deg=pose or [220, 0, 70, 0],
                frame_to_tcp_receive_delta_ms=delta, **kwargs)


@pytest.mark.parametrize('records', [
    [], [record(delta=None)], [record(delta=501)], [record(delta=float('nan'))],
    [record(motion_active=True)], [record(pose=[220, 0, 70, float('nan')])],
    [record(), record(pose=[222, 0, 70, 0]), record()],
    [record(pose=[220, 0, 70, 0.3])],
])
def test_reject_stale_moving_or_missing_capture(records):
    with pytest.raises(ValueError):
        validate_stationary_capture([220, 0, 70, 0], records)


def test_stationary_capture_and_wrapped_yaw():
    validate_stationary_capture([220, 0, 70, 0], [record()] * 12)
    validate_stationary_capture([220, 0, 70, 180], [record(pose=[220, 0, 70, -180])])


@pytest.mark.parametrize('age,active,info_age', [(None, False, 0), (1, False, 0),
                                                    (0, True, 0), (0, False, 6)])
def test_preflight_rejects_missing_stale_or_active_state(age, active, info_age):
    node = SimpleNamespace(
        status=lambda: {'motion': {'active_goal': active, 'current_tcp_pose_age_sec': age}},
        _frame_condition=threading.Condition(),
        _latest_camera_intrinsics_time=time.monotonic() - info_age,
        _latest_camera_intrinsics={},
    )
    with pytest.raises(ValueError):
        DobotWebNode._stationary_calibration_preflight(node)


def test_auto_requires_explicit_measured_fixture_before_any_capture():
    node = SimpleNamespace(_vision_mode_from_payload=lambda _: 'eye_in_hand')
    for confirmation in (None, False, 'true', 1):
        with pytest.raises(ValueError, match='measured board'):
            DobotWebNode.vision_auto_calibrate(node, {'fixture_measured': confirmation})


def test_actual_browser_pdf_markers_have_correct_scale_and_pnp(tmp_path):
    chrome = shutil.which('google-chrome')
    rasterizer = shutil.which('pdftoppm')
    pdfinfo = shutil.which('pdfinfo')
    if not all((chrome, rasterizer, pdfinfo)):
        pytest.skip('Chrome and Poppler required for physical PDF integration test')
    svg = PrintNode().get_calibration_board_svg('eye_in_hand')
    page = tmp_path / 'board.html'
    page.write_text(calibration_print_page(svg, 'eye_in_hand'), encoding='utf-8')
    pdf = tmp_path / 'board.pdf'
    subprocess.run([
        chrome, '--headless', '--no-sandbox', '--disable-gpu',
        '--no-pdf-header-footer', f'--user-data-dir={tmp_path / "chrome"}',
        f'--print-to-pdf={pdf}', page.as_uri(),
    ], check=True, capture_output=True, timeout=45)
    info = subprocess.check_output([pdfinfo, str(pdf)], text=True)
    assert re.search(r'Pages:\s+1\b', info), info
    assert '(A4)' in info
    subprocess.run([rasterizer, '-r', '254', '-png', '-singlefile', str(pdf),
                    str(tmp_path / 'raster')], check=True, capture_output=True, timeout=30)
    image = cv2.imread(str(tmp_path / 'raster.png'))
    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    if hasattr(cv2.aruco, 'ArucoDetector'):
        corners, ids, _ = cv2.aruco.ArucoDetector(dictionary).detectMarkers(image)
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(image, dictionary)
    assert ids is not None and set(ids.flatten()) == {0, 1, 2, 3}
    points = {int(i): c.reshape(4, 2) for i, c in zip(ids.flatten(), corners)}
    centers = {i: p.mean(axis=0) for i, p in points.items()}
    assert centers[3][1] < centers[0][1] and centers[2][1] < centers[1][1]
    for p in points.values():
        for a, b in zip(p, np.roll(p, -1, axis=0)):
            assert abs(np.linalg.norm(a - b) / 10 - 30) < 0.3
    assert abs(np.linalg.norm(centers[1] - centers[0]) / 10 - 80) < 0.3
    assert abs(np.linalg.norm(centers[3] - centers[0]) / 10 - 160) < 0.3
    board = default_aruco_board()
    obj = np.concatenate([marker_corners_board(board['markers'][str(i)], 30)
                          for i in range(4)]).astype(np.float64)
    img = np.concatenate([points[i] for i in range(4)]).astype(np.float64)
    matrix = np.array([[1000., 0, image.shape[1] / 2],
                       [0, 1000., image.shape[0] / 2], [0, 0, 1.]])
    ok, rvec, tvec = cv2.solvePnP(obj, img, matrix, np.zeros(5))
    assert ok and tvec[2] > 0
    projected, _ = cv2.projectPoints(obj, rvec, tvec, matrix, np.zeros(5))
    assert np.sqrt(np.mean(np.sum((projected.reshape(-1, 2) - img) ** 2, axis=1))) < 1
    rotation, _ = cv2.Rodrigues(rvec)
    assert rotation[2, 2] < -0.99  # Printed front, not a mirrored board.
