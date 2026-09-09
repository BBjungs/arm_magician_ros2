import math
import cv2
import numpy as np


class ShapeDetector:
    def __init__(self, rules):
        self.rules = rules

    def detect(self, image):
        cfg = self.rules['candidate']
        kernel_size = int(cfg.get('blur_kernel', 5)) | 1
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (kernel_size, kernel_size), 0)
        edges = cv2.Canny(blurred, int(cfg['canny_low']), int(cfg['canny_high']))
        kernel = np.ones((int(cfg.get('morph_kernel', 5)),) * 2, np.uint8)
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for contour in contours:
            area = float(cv2.contourArea(contour))
            if area < cfg['min_area_px'] or area > cfg['max_area_px']:
                continue
            perimeter = float(cv2.arcLength(contour, True))
            if perimeter <= 0:
                continue
            epsilon = float(cfg.get('approx_epsilon_ratio', 0.035)) * perimeter
            vertices = len(cv2.approxPolyDP(contour, epsilon, True))
            x, y, width, height = cv2.boundingRect(contour)
            aspect = width / max(float(height), 1.0)
            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
            shape, score = self._classify(vertices, aspect, circularity)
            results.append({
                'contour': contour, 'shape': shape, 'shape_score': round(score, 4),
                'area_px': round(area, 2), 'perimeter_px': round(perimeter, 2),
                'vertices': vertices, 'aspect_ratio': round(aspect, 4),
                'circularity': round(circularity, 4),
                'bbox': [x, y, x + width, y + height],
                'center_pixel': [int(round(x + width / 2)), int(round(y + height / 2))],
            })
        return sorted(results, key=lambda item: item['area_px'], reverse=True)

    def _classify(self, vertices, aspect, circularity):
        if vertices == 3:
            return 'triangle', 1.0
        if vertices == 4:
            cfg = self.rules['square']
            if cfg['min_aspect_ratio'] <= aspect <= cfg['max_aspect_ratio']:
                return 'square', max(0.0, 1.0 - abs(1.0 - aspect))
            return 'rectangle', min(1.0, abs(1.0 - aspect) + 0.5)
        circle = self.rules['circle']
        if (vertices > 5 and circularity >= circle['min_circularity'] and
                circle['min_aspect_ratio'] <= aspect <= circle['max_aspect_ratio']):
            return 'circle', min(1.0, circularity)
        if vertices >= 5:
            return 'polygon', min(1.0, vertices / 10.0)
        return 'unknown', 0.0
