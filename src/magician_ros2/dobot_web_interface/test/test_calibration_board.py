from types import SimpleNamespace
import re

import pytest

from dobot_vision_yolo.camera_calibration_tool import CalibrationStore
from dobot_web_interface.web_interface import DobotWebNode
from dobot_web_interface.web_interface import _intrinsics_from_camera_info


class BoardNode:
    def __init__(self, calibration_store):
        self.calibration_store = calibration_store

    def _calibration(self):
        return self.calibration_store


def test_printable_board_uses_physical_units_and_all_required_markers(tmp_path):
    node = BoardNode(CalibrationStore(str(tmp_path / "camera_to_robot.yaml")))

    svg = DobotWebNode.get_calibration_board_svg(node).decode("utf-8")

    assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg
    assert 'width="130.000mm"' in svg
    assert 'height="210.000mm"' in svg
    assert svg.count("data:image/png;base64,") == 4
    assert "30 mm check ruler" in svg
    assert "DICT_4X4_50" in svg
    assert "+X: ID0→ID1   +Y: ID0→ID3 (ขึ้นบนแผ่น)" in svg
    image_positions = [
        (float(x), float(y))
        for x, y in re.findall(r'<image x="([0-9.]+)" y="([0-9.]+)"', svg)
    ]
    assert len(image_positions) == 4
    # Elements are emitted in ID order. Positive Cartesian board Y is drawn
    # upward, so IDs 3/2 are above IDs 0/1 in SVG pixel coordinates.
    assert image_positions[3][1] < image_positions[0][1]
    assert image_positions[2][1] < image_positions[1][1]


def test_factory_camera_info_is_converted_without_manual_entry():
    intrinsics = _intrinsics_from_camera_info(
        SimpleNamespace(
            width=1280,
            height=720,
            k=[900.0, 0.0, 640.0, 0.0, 905.0, 360.0, 0.0, 0.0, 1.0],
            d=[0.1, -0.2, 0.0, 0.0, 0.01],
        )
    )

    assert intrinsics["fx"] == 900.0
    assert intrinsics["fy"] == 905.0
    assert intrinsics["image_width"] == 1280
    assert intrinsics["distortion_coefficients"] == [0.1, -0.2, 0.0, 0.0, 0.01]


def test_invalid_factory_camera_info_is_rejected():
    with pytest.raises(ValueError, match="invalid"):
        _intrinsics_from_camera_info(
            SimpleNamespace(
                width=0,
                height=720,
                k=[0.0] * 9,
                d=[],
            )
        )
