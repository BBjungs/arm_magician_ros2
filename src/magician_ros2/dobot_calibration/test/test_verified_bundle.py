import json

import numpy as np
import pytest

from dobot_calibration.bundle import VerifiedBundle
from dobot_calibration.geometry import CalibrationError


def _status(path, digest="context-1", **updates):
    value = {
        "architecture": "markerless_hand_eye",
        "state": "READY", "result": "PASS", "ready": True,
        "bundle_loaded": True, "geometry_verified": True,
        "verification_status": "PASS", "reload_verification_status": "PASS",
        "bundle_path": str(path), "context_digest": digest, "blockers": [],
    }
    value.update(updates)
    return value


def _bundle(path, *, verification="PASS", digest="context-1"):
    metadata = {
        "schema": 1, "context_digest": digest,
        "verification": {"result": verification},
    }
    np.savez_compressed(path, metadata=json.dumps(metadata), tool_T_camera=np.eye(4))


def test_valid_saved_reloaded_markerless_bundle_transforms_depth_point(tmp_path):
    path = tmp_path / "calibration.npz"
    _bundle(path)
    xyz = VerifiedBundle(path).camera_point_to_base(
        {"x": 10.0, "y": -20.0, "z": 200.0},
        [0.2, 0.0, 0.1, 0.0], _status(path))
    assert xyz == pytest.approx([210.0, -20.0, 300.0])


@pytest.mark.parametrize("field,value", [
    ("geometry_verified", False),
    ("verification_status", "FAIL"),
    ("reload_verification_status", "MISSING"),
    ("bundle_loaded", False),
])
def test_invalid_markerless_evidence_blocks_ready(tmp_path, field, value):
    path = tmp_path / "calibration.npz"
    _bundle(path)
    with pytest.raises(CalibrationError):
        VerifiedBundle(path).load_transform(_status(path, **{field: value}))


def test_old_or_fake_calibration_file_cannot_authorize_transform(tmp_path):
    path = tmp_path / "old.npz"
    _bundle(path, verification="FAIL")
    with pytest.raises(CalibrationError):
        VerifiedBundle(path).load_transform(_status(path))


def test_marker_fields_have_no_effect_on_markerless_authority(tmp_path):
    path = tmp_path / "calibration.npz"
    _bundle(path)
    status = _status(path, detected_ids=[], required_ids=[0, 1, 2, 3],
                     marker_status={"missing_ids": [1]})
    assert np.allclose(VerifiedBundle(path).load_transform(status), np.eye(4))

