import cv2


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
