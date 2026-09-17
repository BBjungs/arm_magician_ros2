import copy
import numpy as np
import pytest

from dobot_calibration.bootstrap_geometry import validate_calibration_bootstrap_geometry
from dobot_calibration.geometry import fingerprint
from dobot_calibration.bundle import VerifiedBundle
from dobot_calibration.geometry import CalibrationError
from dobot_calibration.real_motion_adapter import RealMotionAdapter, RealMotionRejected


def config():
    return {'geometry_verified': False, 'rigid_to_rotating_tool': True,
            'translation_verified': True, 'translation_units': 'm',
            'measurement_source': 'measured', 'translation_error_bound_m': .001,
            'envelope_radius_m': .1526,
            'initial_mount_constraint': {'tool_to_camera_reference': [.050, 0., -.035]}}


def validate(value=None, tf=np.eye(4), fingerprint_ok=True):
    value = config() if value is None else value
    return validate_calibration_bootstrap_geometry(
        value, tf, camera_reference_frame='camera_link',
        camera_frame='camera_color_optical_frame',
        expected_mount_fingerprint=fingerprint(value) if fingerprint_ok else 'wrong')


def test_unverified_geometry_with_measured_evidence_is_bootstrap_eligible():
    result = validate()
    assert result.eligible and result.translation_m == (.05, .0, -.035)
    assert result.translation_error_bound_m == .001 and result.conservative_envelope_radius_m == .1526


def test_translation_missing_is_rejected():
    value = config(); del value['initial_mount_constraint']['tool_to_camera_reference']
    assert 'MEASURED_TRANSLATION_MISSING' in validate(value).blockers


def test_translation_not_verified_is_rejected():
    value = config(); value['translation_verified'] = False
    assert 'TRANSLATION_NOT_VERIFIED' in validate(value).blockers


def test_envelope_missing_is_rejected():
    value = config(); del value['envelope_radius_m']
    assert 'CONSERVATIVE_ENVELOPE_INVALID' in validate(value).blockers


def test_invalid_translation_bound_is_rejected():
    value = config(); value['translation_error_bound_m'] = .01
    assert 'TRANSLATION_ERROR_BOUND_INVALID' in validate(value).blockers


def test_invalid_factory_tf_or_camera_parent_is_rejected():
    assert 'CAMERA_FACTORY_OPTICAL_TF_INVALID' in validate(tf=np.zeros((4, 4))).blockers
    assert not validate_calibration_bootstrap_geometry(
        config(), np.eye(4), camera_reference_frame='', camera_frame='camera_color_optical_frame').eligible


def test_mount_session_fingerprint_is_required():
    assert 'MOUNT_SESSION_FINGERPRINT_MISMATCH' in validate(fingerprint_ok=False).blockers


def test_eligible_commissioning_software_gate_can_proceed_to_next_gate():
    assert validate().eligible
    adapter = RealMotionAdapter(token_valid=lambda _t, _p: True, hard_gates=lambda _p: '',
                                ptp_readback=lambda: {'velocity_percent': 5, 'acceleration_percent': 5},
                                dispatch=lambda _p, _t: 'not-called', safe_stop=lambda: None)
    adapter.enable_authorized_commissioning_run()
    adapter._check({'scope': 'POSE_1_TO_2_ONLY'}, 1)


def test_commissioning_scope_rejects_pose_three():
    adapter = RealMotionAdapter(token_valid=lambda _t, _p: True, hard_gates=lambda _p: '',
                                ptp_readback=lambda: {'velocity_percent': 5, 'acceleration_percent': 5},
                                dispatch=lambda _p, _t: None, safe_stop=lambda: None)
    adapter.enable_authorized_commissioning_run()
    with pytest.raises(RealMotionRejected, match='POSE_SCOPE_VIOLATION'):
        adapter._check({'scope': 'POSE_1_TO_2_ONLY'}, 3)


def test_production_bundle_still_requires_verified_geometry(tmp_path):
    with pytest.raises(CalibrationError, match='geometry_verified'):
        VerifiedBundle(tmp_path / 'bundle.npz').require_authoritative_status({
            'state': 'READY', 'result': 'PASS', 'ready': True, 'blockers': [],
            'bundle_loaded': True, 'geometry_verified': False, 'verification_status': 'PASS',
            'reload_verification_status': 'PASS'})


def test_geometry_verified_remains_false_through_bootstrap():
    value = config(); result = validate(value)
    assert result.eligible and value['geometry_verified'] is False


def test_conservative_envelope_must_enclose_measured_translation():
    value = config(); value['envelope_radius_m'] = .04
    assert 'CONSERVATIVE_ENVELOPE_INVALID' in validate(value).blockers
