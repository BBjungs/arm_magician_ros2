from dobot_vision_yolo.target_selector_node import PlaceStore
from dobot_vision_yolo.target_selector_node import _confidence, _pick_eligible
from dobot_vision_yolo.target_selector_node import select_target_from_detections


def test_rgbd_rule_score_is_used_as_confidence():
    detection = {"classification_score": 0.83, "confidence": 0.12}
    assert _confidence(detection) == 0.83


def test_explicitly_ineligible_rgbd_candidate_is_rejected():
    assert not _pick_eligible({"pick_eligible": False, "rejection_reason": "invalid_depth"})


def test_legacy_yolo_detection_remains_eligible():
    assert _pick_eligible({"class_name": "yellow_cap", "confidence": 0.9})


def test_selected_rgbd_target_preserves_depth_quality_for_visual_servo():
    class Places:
        def get_pose(self, _place_id):
            return [220.0, 160.0, -35.0, 0.0]

    class Calibration:
        def test_point(self, _pixel):
            return {
                'robot_xy': [210.0, 5.0],
                'pick_z': -35.0,
                'safe_z': 60.0,
            }

    result = select_target_from_detections(
        {
            'detections': [
                {
                    'id': 3,
                    'class_name': 'black_cap',
                    'classification_score': 0.92,
                    'center_pixel': [320, 240],
                    'bbox': [300, 220, 340, 260],
                    'pick_eligible': True,
                    'depth_mm': 520.0,
                    'depth_valid': True,
                    'depth_valid_ratio': 0.91,
                    'depth_stddev': 2.5,
                }
            ]
        },
        {
            'object_class': 'black_cap',
            'place_id': 'tray_A',
            'selection_mode': 'highest_confidence',
        },
        Places(),
        Calibration(),
    )

    assert result['selected'] is True
    assert result['depth_valid'] is True
    assert result['depth_mm'] == 520.0
    assert result['depth_valid_ratio'] == 0.91
    assert result['detection']['depth_stddev'] == 2.5


def test_place_store_exposes_canonical_zone_and_legacy_alias(tmp_path):
    config = tmp_path / 'zones.yaml'
    config.write_text(
        '''places:
  Zone A:
    zone_id: Zone A
    pose: [220.0, 160.0, -35.0, 0.0]
    safe_z: 60.0
    aliases: [tray_A]
''',
        encoding='utf-8',
    )

    store = PlaceStore(str(config))
    zone = store.get_placement_zone('tray_A')

    assert store.get_pose('Zone A') == [220.0, 160.0, -35.0, 0.0]
    assert zone['zone_id'] == 'Zone A'
    assert zone['nominal_pose'] == [220.0, 160.0, -35.0, 0.0]
    assert zone['safe_z'] == 60.0
