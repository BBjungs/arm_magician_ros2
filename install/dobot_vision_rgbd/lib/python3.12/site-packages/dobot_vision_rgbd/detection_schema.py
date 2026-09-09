REQUIRED_FIELDS = {'id', 'detector', 'class_name', 'shape', 'color', 'classification_score', 'bbox', 'center_pixel', 'pick_eligible'}


def validate_detection(detection):
    missing = REQUIRED_FIELDS - detection.keys()
    if missing:
        raise ValueError(f'missing detection fields: {sorted(missing)}')
    if detection['detector'] != 'rgbd_shape':
        raise ValueError('detector must be rgbd_shape')
    if len(detection['bbox']) != 4 or len(detection['center_pixel']) != 2:
        raise ValueError('invalid bbox or center_pixel')
    score = float(detection['classification_score'])
    if not 0.0 <= score <= 1.0:
        raise ValueError('classification_score must be within 0..1')
    if not detection['pick_eligible'] and not detection.get('rejection_reason'):
        raise ValueError('ineligible detection requires rejection_reason')
    return True
