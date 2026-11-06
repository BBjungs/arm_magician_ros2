import cv2
import os
from pathlib import Path


def write_preview(path, image, max_width=480, jpeg_quality=80):
    """Publish a smaller JPEG atomically, without changing detection inputs."""
    if max_width <= 0 or not 1 <= jpeg_quality <= 100:
        raise ValueError('Invalid preview width or JPEG quality')
    if image.shape[1] > max_width:
        height = max(1, round(image.shape[0] * max_width / image.shape[1]))
        image = cv2.resize(image, (max_width, height), interpolation=cv2.INTER_AREA)
    ok, encoded = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
    if not ok:
        raise ValueError('Could not encode preview JPEG')
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    try:
        temporary.write_bytes(encoded.tobytes())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def annotate(image, detections):
    output = image.copy()
    for item in detections:
        x1, y1, x2, y2 = item['bbox']
        color = (0, 210, 0) if item['pick_eligible'] else (0, 165, 255)
        cv2.rectangle(output, (x1, y1), (x2, y2), color, 2)
        u, v = item['center_pixel']
        cv2.drawMarker(output, (u, v), color, cv2.MARKER_CROSS, 12, 2)
        lines = [f"#{item['id']} {item['class_name']}", f"{item['shape']} / {item['color']}"]
        if item.get('depth_mm') is not None:
            height = item.get('object_height_mm')
            height_text = 'N/A' if height is None else f'{height:.0f}mm'
            lines.append(f"Z={item['depth_mm']:.0f}mm H={height_text}")
        else:
            lines.append(item.get('rejection_reason', 'invalid depth'))
        for index, text in enumerate(lines):
            cv2.putText(output, text, (x1, max(18, y1 - 8 - (len(lines)-1-index)*18)), cv2.FONT_HERSHEY_SIMPLEX, 0.48, color, 1, cv2.LINE_AA)
    return output
