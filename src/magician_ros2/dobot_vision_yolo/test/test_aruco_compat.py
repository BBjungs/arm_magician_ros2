import numpy as np

import dobot_vision_yolo.camera_calibration_tool as calibration_module


def test_legacy_aruco_api_is_called_without_detector_parameters(monkeypatch):
    calls = []

    class LegacyAruco:
        DICT_4X4_50 = 0
        CORNER_REFINE_SUBPIX = 1

        @staticmethod
        def DetectorParameters():
            raise AssertionError(
                'legacy detectMarkers must not construct DetectorParameters'
            )

        @staticmethod
        def getPredefinedDictionary(dictionary_id):
            assert dictionary_id == LegacyAruco.DICT_4X4_50
            return 'dictionary'

        @staticmethod
        def detectMarkers(gray, dictionary):
            calls.append((gray.shape, dictionary))
            return [], None, []

    class LegacyCv2:
        aruco = LegacyAruco
        COLOR_BGR2GRAY = 6

        @staticmethod
        def cvtColor(frame, conversion):
            assert conversion == LegacyCv2.COLOR_BGR2GRAY
            return frame[:, :, 0]

    monkeypatch.setattr(calibration_module, 'cv2', LegacyCv2)
    frame = np.zeros((8, 8, 3), dtype=np.uint8)

    observations = calibration_module._detect_aruco_observation(
        frame,
        {'dictionary': 'DICT_4X4_50'},
    )

    assert observations == {}
    assert calls == [((8, 8), 'dictionary')]
