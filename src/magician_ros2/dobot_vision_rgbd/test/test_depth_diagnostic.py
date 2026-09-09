import importlib.util
from pathlib import Path

import numpy as np
import pytest


SCRIPT = Path(__file__).parents[4] / 'scripts' / 'diagnose_orbbec_depth.py'
SPEC = importlib.util.spec_from_file_location('diagnose_orbbec_depth', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Message:
    encoding = '16UC1'
    width = 3
    height = 2
    step = 6
    is_bigendian = 0
    data = np.array([0, 50, 250, 750, 1500, 2500], dtype=np.uint16).tobytes()


def test_decode_and_statistics_preserve_raw_uint16_values():
    raw, millimetres, scale = MODULE.decode_depth(Message())
    assert raw.dtype == np.uint16
    assert raw.tolist() == [[0, 50, 250], [750, 1500, 2500]]
    assert scale == 1.0
    stats = MODULE.frame_statistics(millimetres, 100.0, 2000.0)
    assert stats['nonzero_count'] == 5
    assert stats['valid_count'] == 3
    assert stats['valid_ratio'] == pytest.approx(0.5)
    assert stats['histogram'] == {
        '0': 1, '1-100': 1, '100-500': 1, '500-1000': 1,
        '1000-2000': 1, '>2000': 1, 'nonfinite': 0}


def test_decode_rejects_malformed_buffer():
    message = Message()
    message.data = message.data[:-1]
    with pytest.raises(ValueError, match='Invalid data length'):
        MODULE.decode_depth(message)
