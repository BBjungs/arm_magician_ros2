#!/usr/bin/env python3
"""Report the geometric extent of the repository suction mesh.

This is an audit aid, not a source of verified TCP geometry.  The DAE has no
vendor TCP datum and its provenance is the upstream ROS description package.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}


def transform_point(matrix: list[list[float]], point: tuple[float, float, float]):
    vector = (*point, 1.0)
    return tuple(sum(matrix[row][col] * vector[col] for col in range(4)) for row in range(3))


def audit(path: Path) -> dict[str, object]:
    root = ET.parse(path).getroot()
    position_array = next(
        node
        for node in root.findall(".//c:float_array", NS)
        if "positions-array" in node.attrib.get("id", "")
    )
    values = [float(value) for value in (position_array.text or "").split()]
    points = list(zip(values[0::3], values[1::3], values[2::3]))

    matrix_node = root.find(".//c:visual_scene//c:matrix", NS)
    if matrix_node is None:
        raise ValueError("DAE visual scene has no transform matrix")
    flat_matrix = [float(value) for value in (matrix_node.text or "").split()]
    matrix = [flat_matrix[index : index + 4] for index in range(0, 16, 4)]
    transformed = [transform_point(matrix, point) for point in points]
    minimum = [min(point[axis] for point in transformed) for axis in range(3)]
    maximum = [max(point[axis] for point in transformed) for axis in range(3)]

    return {
        "mesh": str(path),
        "units": "m",
        "bbox_min": minimum,
        "bbox_max": maximum,
        "extent": [maximum[axis] - minimum[axis] for axis in range(3)],
        "bottom_z_mm": minimum[2] * 1000.0,
        "top_z_mm": maximum[2] * 1000.0,
        "tcp_verified": False,
        "reason": "mesh extent is not a vendor-labelled suction TCP datum",
    }


def main() -> None:
    default = (
        Path(__file__).resolve().parents[1]
        / "src/magician_ros2/dobot_description/meshes/dae/suction_cup.dae"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("mesh", nargs="?", type=Path, default=default)
    args = parser.parse_args()
    print(json.dumps(audit(args.mesh), indent=2))


if __name__ == "__main__":
    main()
