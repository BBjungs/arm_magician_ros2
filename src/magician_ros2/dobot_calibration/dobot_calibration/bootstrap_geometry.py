"""Minimum, conservative geometry evidence for calibration-only bootstrap."""

from dataclasses import dataclass
import numpy as np

from .geometry import Limits, checked_transform, fingerprint


@dataclass(frozen=True)
class BootstrapGeometryEligibility:
    eligible: bool
    blockers: tuple[str, ...]
    translation_m: tuple[float, float, float] | None = None
    translation_error_bound_m: float | None = None
    conservative_envelope_radius_m: float | None = None


def validate_calibration_bootstrap_geometry(config, camera_reference_T_optical,
                                            *, camera_reference_frame, camera_frame,
                                            expected_mount_fingerprint=None,
                                            limits=Limits(), carrier_frame=''):
    """Validate evidence for calibration scope without certifying rotation.

    This intentionally returns no tool-to-camera rotation.  Callers must use
    the returned spherical envelope together with translation uncertainty for
    every calibration/commissioning path check.
    """
    blockers = []
    if not isinstance(config, dict):
        return BootstrapGeometryEligibility(False, ('MOUNT_CONFIG_INVALID',))
    rigidity = 'rigid_to_camera_carrier' if carrier_frame else 'rigid_to_rotating_tool'
    if config.get(rigidity) is not True:
        blockers.append('CAMERA_PARENT_RIGIDITY_NOT_VERIFIED')
    if config.get('translation_verified') is not True:
        blockers.append('TRANSLATION_NOT_VERIFIED')
    if config.get('translation_units') != 'm' or not config.get('measurement_source'):
        blockers.append('MEASURED_TRANSLATION_METADATA_INVALID')
    try:
        translation = np.asarray(config.get('initial_mount_constraint', {}).get(
            'tool_to_camera_reference'), dtype=float)
        if translation.shape != (3,) or not np.isfinite(translation).all():
            raise ValueError
    except (TypeError, ValueError):
        translation = None
        blockers.append('MEASURED_TRANSLATION_MISSING')
    try:
        bound = float(config.get('translation_error_bound_m'))
        if not np.isfinite(bound) or not 0 < bound <= limits.max_mount_translation_error_m:
            raise ValueError
    except (TypeError, ValueError):
        bound = None
        blockers.append('TRANSLATION_ERROR_BOUND_INVALID')
    try:
        envelope = float(config.get('envelope_radius_m'))
        minimum = 0.0 if translation is None else float(np.linalg.norm(translation))
        if not np.isfinite(envelope) or not minimum < envelope < 0.30:
            raise ValueError
    except (TypeError, ValueError):
        envelope = None
        blockers.append('CONSERVATIVE_ENVELOPE_INVALID')
    if not camera_reference_frame or not camera_frame:
        blockers.append('CAMERA_PARENT_FRAME_INVALID')
    try:
        checked_transform(camera_reference_T_optical)
    except Exception:
        blockers.append('CAMERA_FACTORY_OPTICAL_TF_INVALID')
    if (expected_mount_fingerprint is not None
            and expected_mount_fingerprint != fingerprint(config)):
        blockers.append('MOUNT_SESSION_FINGERPRINT_MISMATCH')
    return BootstrapGeometryEligibility(
        not blockers, tuple(blockers),
        None if translation is None else tuple(map(float, translation)), bound, envelope)
