"""Crash-safe persistence for passive markerless capture sessions."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import uuid

import numpy as np
import yaml

from .geometry import CalibrationError, checked_transform, fingerprint
from .registration import Capture


SCHEMA_VERSION = 1


def _fsync_directory(path):
    descriptor = os.open(str(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _atomic_yaml(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            yaml.safe_dump(value, stream, sort_keys=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _atomic_npz(path, **arrays):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.npz',
                                     dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PassiveSessionStore:
    def __init__(self, root, mount_fingerprint, camera_id):
        self.root = Path(root).expanduser()
        self.mount_fingerprint = str(mount_fingerprint)
        self.camera_id = str(camera_id)
        self.active_file = self.root / 'active.yaml'
        self.session_dir = None
        self.manifest = None

    def new(self, intrinsics_fingerprint=''):
        session_id = (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
                      + '-' + uuid.uuid4().hex[:8])
        self.session_dir = self.root / session_id
        self.manifest = {
            'schema_version': SCHEMA_VERSION,
            'session_id': session_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'accepted_pose_count': 0,
            'calibration_mode': 'markerless_passive',
            'mount_config_fingerprint': self.mount_fingerprint,
            'camera_id': self.camera_id,
            'intrinsics_fingerprint': str(intrinsics_fingerprint),
            'geometry_verified': False,
            'status': 'unfinished',
        }
        self.session_dir.mkdir(parents=True, exist_ok=False)
        self._write_manifest()
        _atomic_yaml(self.active_file, {'session_id': session_id})
        return self.manifest

    def _write_manifest(self):
        _atomic_yaml(self.session_dir / 'manifest.yaml', self.manifest)

    def ensure_plan(self, targets):
        if self.manifest is None:
            raise CalibrationError('No active passive session')
        if 'target_poses' not in self.manifest:
            self.manifest['target_poses'] = list(targets)
            self._write_manifest()
        elif self.manifest['target_poses'] != list(targets):
            raise CalibrationError('Stored passive calibration plan changed')
        return self.manifest['target_poses']

    def discover(self):
        if not self.active_file.is_file():
            return None
        try:
            active = yaml.safe_load(self.active_file.read_text(encoding='utf-8'))
            session_id = active['session_id']
            directory = self.root / session_id
            manifest = yaml.safe_load((directory / 'manifest.yaml').read_text(encoding='utf-8'))
        except (OSError, KeyError, TypeError, yaml.YAMLError) as error:
            raise CalibrationError('Passive session metadata is corrupt: ' + str(error)) from error
        self._validate_manifest(manifest)
        self.session_dir, self.manifest = directory, manifest
        return manifest

    def _validate_manifest(self, manifest, intrinsics_fingerprint=''):
        if (not isinstance(manifest, dict)
                or manifest.get('schema_version') != SCHEMA_VERSION
                or manifest.get('calibration_mode') != 'markerless_passive'
                or manifest.get('geometry_verified') is not False
                or manifest.get('status') != 'unfinished'):
            raise CalibrationError('Passive session manifest schema/status is incompatible')
        if manifest.get('mount_config_fingerprint') != self.mount_fingerprint:
            raise CalibrationError('Passive session mount/config fingerprint changed')
        if manifest.get('camera_id', '') != self.camera_id:
            raise CalibrationError('Passive session camera identity changed')
        stored = manifest.get('intrinsics_fingerprint', '')
        if intrinsics_fingerprint and stored and stored != intrinsics_fingerprint:
            raise CalibrationError('Passive session camera intrinsics changed')

    def save_pose(self, capture, joints, metadata, rgb_stamp, depth_stamp,
                  intrinsics_fingerprint, camera_info=None, joint_names=None):
        if self.manifest is None:
            self.new(intrinsics_fingerprint)
        self._validate_manifest(self.manifest, intrinsics_fingerprint)
        if not self.manifest.get('intrinsics_fingerprint'):
            self.manifest['intrinsics_fingerprint'] = intrinsics_fingerprint
        index = int(self.manifest['accepted_pose_count']) + 1
        if int(metadata.get('pose_index', index)) != index:
            raise CalibrationError('Passive pose index is not sequential')
        carrier = (np.empty((0, 0)) if capture.base_T_carrier is None
                   else checked_transform(capture.base_T_carrier))
        _atomic_npz(
            self.session_dir / f'pose_{index:03d}.npz',
            pose_index=np.array(index, dtype=np.int64),
            capture_timestamp=np.array(capture.stamp, dtype=np.float64),
            base_T_tool=checked_transform(capture.base_T_tool),
            joints=np.asarray(joints, dtype=np.float64),
            joint_names=np.asarray(joint_names or [f'magician_joint_{i}' for i in range(1, 5)]),
            j4_yaw_deg=np.array(metadata['J4_yaw_deg'], dtype=np.float64),
            rgb_timestamp=np.array(rgb_stamp, dtype=np.float64),
            depth_timestamp=np.array(depth_stamp, dtype=np.float64),
            rgb_depth_sync_skew_ms=np.array(metadata['sync_skew_ms'], dtype=np.float64),
            rgb=capture.rgb,
            depth=capture.depth,
            intrinsics=capture.intrinsics,
            intrinsics_fingerprint=np.array(str(intrinsics_fingerprint)),
            camera_info_json=np.array(json.dumps(camera_info or {}, allow_nan=False)),
            point_cloud=capture.cloud,
            plane_coefficients=capture.plane,
            base_T_carrier=carrier,
            quality_json=np.array(json.dumps(capture.quality, allow_nan=False)),
            metadata_json=np.array(json.dumps(metadata, allow_nan=False)),
            accepted=np.array(True),
            status=np.array('ACCEPTED'),
        )
        self.manifest['accepted_pose_count'] = index
        self._write_manifest()
        return index

    def restore(self, intrinsics_fingerprint=''):
        manifest = self.discover()
        if manifest is None:
            return [], []
        self._validate_manifest(manifest, intrinsics_fingerprint)
        captures, metadata = [], []
        count = int(manifest.get('accepted_pose_count', -1))
        if count < 0:
            raise CalibrationError('Passive session pose count is invalid')
        for index in range(1, count + 1):
            path = self.session_dir / f'pose_{index:03d}.npz'
            try:
                with np.load(path, allow_pickle=False) as value:
                    if int(value['pose_index']) != index or not bool(value['accepted']):
                        raise CalibrationError('Passive pose identity/status is corrupt')
                    if str(value['status']) != 'ACCEPTED':
                        raise CalibrationError('Passive pose status is corrupt')
                    pose_intrinsics = str(value['intrinsics_fingerprint'])
                    if pose_intrinsics != manifest.get('intrinsics_fingerprint', ''):
                        raise CalibrationError('Passive pose intrinsics fingerprint disagrees with manifest')
                    quality = json.loads(str(value['quality_json']))
                    item_metadata = json.loads(str(value['metadata_json']))
                    json.loads(str(value['camera_info_json']))
                    carrier = value['base_T_carrier'].copy()
                    capture = Capture(
                        float(value['capture_timestamp']), value['base_T_tool'].copy(),
                        value['rgb'].copy(), value['depth'].copy(),
                        value['intrinsics'].copy(), value['point_cloud'].copy(),
                        value['plane_coefficients'].copy(), quality,
                        None if carrier.size == 0 else carrier)
            except (OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as error:
                raise CalibrationError(f'Passive pose {index} is corrupt: {error}') from error
            captures.append(capture)
            metadata.append(item_metadata)
        return captures, metadata

    def discard(self):
        if self.session_dir is None:
            self.discover()
        if self.session_dir is None:
            return None
        target = self.session_dir.with_name(self.session_dir.name + '.discarded')
        os.replace(self.session_dir, target)
        if self.active_file.exists():
            self.active_file.unlink()
        self.session_dir, self.manifest = None, None
        return target

    def delete_last(self):
        if self.manifest is None:
            self.discover()
        count = int(self.manifest.get('accepted_pose_count', 0))
        if count <= 0:
            return 0
        path = self.session_dir / f'pose_{count:03d}.npz'
        if path.exists():
            os.replace(path, path.with_suffix('.npz.deleted'))
        self.manifest['accepted_pose_count'] = count - 1
        self._write_manifest()
        return count - 1
