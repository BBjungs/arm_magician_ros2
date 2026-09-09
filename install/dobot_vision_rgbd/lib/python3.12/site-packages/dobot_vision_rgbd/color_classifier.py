import cv2
import numpy as np


class ColorClassifier:
    def __init__(self, rules):
        self.rules = rules

    def classify(self, image, contour):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        mask = np.zeros(image.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
        erode = int(self.rules.get('inner_mask_erode_px', 3))
        if erode > 0:
            kernel = np.ones((erode * 2 + 1, erode * 2 + 1), np.uint8)
            mask = cv2.erode(mask, kernel)
        pixels = hsv[mask > 0]
        if not pixels.size:
            return {'color': 'unknown', 'color_score': 0.0, 'median_hsv': None, 'mean_hsv': None}
        scores = {}
        for name, rule in self.rules['colors'].items():
            sv = ((pixels[:, 1] >= rule['s_min']) & (pixels[:, 1] <= rule['s_max']) &
                  (pixels[:, 2] >= rule['v_min']) & (pixels[:, 2] <= rule['v_max']))
            hue = np.zeros(len(pixels), dtype=bool)
            for low, high in rule['h_ranges']:
                hue |= (pixels[:, 0] >= low) & (pixels[:, 0] <= high)
            scores[name] = float(np.mean(sv & hue))
        minimum = float(self.rules.get('minimum_matching_ratio', 0.35))
        priority = self.rules.get('classification_priority', list(scores))
        color = next(
            (name for name in priority if scores.get(name, 0.0) >= minimum),
            'unknown',
        )
        score = scores.get(color, max(scores.values(), default=0.0))
        return {
            'color': color, 'color_score': round(score, 4),
            'median_hsv': np.median(pixels, axis=0).round(2).tolist(),
            'mean_hsv': np.mean(pixels, axis=0).round(2).tolist(),
            'color_distribution': {key: round(value, 4) for key, value in scores.items()},
            'inner_mask': mask,
        }
