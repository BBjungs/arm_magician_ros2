from dobot_vision_yolo.target_selector_node import _confidence, _pick_eligible


def test_rgbd_rule_score_is_used_as_confidence():
    detection = {"classification_score": 0.83, "confidence": 0.12}
    assert _confidence(detection) == 0.83


def test_explicitly_ineligible_rgbd_candidate_is_rejected():
    assert not _pick_eligible({"pick_eligible": False, "rejection_reason": "invalid_depth"})


def test_legacy_yolo_detection_remains_eligible():
    assert _pick_eligible({"class_name": "yellow_cap", "confidence": 0.9})
