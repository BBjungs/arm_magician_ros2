import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'dobot_kinematics'))

# Keep deterministic image tests from oversubscribing the host CPU.
import cv2
cv2.setNumThreads(1)
