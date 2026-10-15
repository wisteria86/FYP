"""Landmark-based presentation posture indicators (not clinical assessment)."""
import math
from domain.ports import VisualMetrics


class LandmarkVisionAdapter:
    def analyze_posture(self, landmarks):
        if len(landmarks) != 33:
            return VisualMetrics({}, False, 'No complete body-landmark set was detected')
        indices = (0, 11, 12, 23, 24)
        if any(landmarks[i].get('visibility', 0) < .5 for i in indices):
            return VisualMetrics({}, False, 'Keep your head, shoulders, and hips visible for posture analysis')
        nose, left, right, lh, rh = [landmarks[i] for i in indices]
        width = abs(left['x']-right['x'])
        if width < .04:
            return VisualMetrics({}, False, 'Move closer or face the camera')
        shoulder_x, shoulder_y = (left['x']+right['x'])/2, (left['y']+right['y'])/2
        hip_x, hip_y = (lh['x']+rh['x'])/2, (lh['y']+rh['y'])/2
        clamp = lambda value: round(max(0, min(100, value)), 1)
        return VisualMetrics({
            'slouching': clamp(100-math.degrees(math.atan2(abs(shoulder_x-hip_x), max(.01,hip_y-shoulder_y)))*2),
            'head_position': clamp(100-abs(nose['x']-shoulder_x)/width*100),
            'shoulder_alignment': clamp(100-abs(left['y']-right['y'])/width*150),
            'body_orientation': clamp(100-abs(left.get('z',0)-right.get('z',0))/width*70),
        }, True)
