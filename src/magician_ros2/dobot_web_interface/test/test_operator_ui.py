import threading

import pytest

from dobot_web_interface.web_interface import DobotWebNode
from dobot_web_interface.web_interface import create_app
from dobot_web_interface.web_interface import operator_detection_counts


def _node_for_operator_status():
    """Build only the small, ROS-free surface used by operator_status."""
    node = object.__new__(DobotWebNode)
    node.vision_mode = 'fixed_camera'
    node._operator_job_lock = threading.RLock()
    node._operator_cancel_event = threading.Event()
    node._vision_cancel_event = threading.Event()
    node._control_lock = threading.RLock()
    node._control_state = 'IDLE'
    node._control_owner = ''
    node._control_ticket = 0
    node._control_stop_acknowledged = False
    node._operator_job = {
        'active': False,
        'state': 'IDLE',
        'message': 'รอคำสั่ง',
        'job': '',
        'place_id': '',
        'completed': 0,
        'total': 0,
        'failed': 0,
    }
    node._operator_places = lambda: [
        {'id': 'Zone A', 'label': 'โซน A'},
        {'id': 'Zone B', 'label': 'โซน B'},
    ]
    node.status = lambda: {
        'motion': {'active_goal': False, 'vision_sequence_active': False},
        'ros': {'ptp_action_ready': True, 'suction_ready': True},
    }
    node.vision_status = lambda: {
        'depth_stream_ok': True,
        'depth_data_valid': True,
    }
    node.vision_detections = lambda: {
        'detections': [
            {'class_name': 'black_cap'},
            {'class_name': 'black_cap'},
            {'class_name': 'white_cap'},
            {'class_name': 'yellow_cap'},
            {'class_name': 'unrelated', 'center_pixel': [9, 8]},
        ]
    }
    node._select_target_preview_source = lambda request: {
        'selected': True,
        'class_name': request['object_class'],
        'place_id': request['place_id'],
        'pick_pose': [200, 0, 0, 0],
        'center_pixel': [10, 20],
    }
    node._safety_report = lambda payload: {
        'allowed': True,
        'checks': [
            {'name': name, 'ok': True}
            for name in ('camera', 'yolo', 'calibration', 'place', 'workspace')
        ],
    }
    node._safety = lambda: type(
        'Safety', (), {'config': type('Config', (), {'allow_real_motion': True})()}
    )()
    return node


def test_operator_counts_only_known_operator_classes():
    assert operator_detection_counts([
        {'class_name': 'black_cap'},
        {'class_name': 'black_cap'},
        {'class_name': 'white_cap'},
        {'class_name': 'yellow_cap'},
        {'class_name': 'blue_cap'},
        {},
    ]) == {'black': 2, 'white': 1, 'yellow': 1}


def test_operator_status_is_sanitized_and_thai_ready():
    status = DobotWebNode.operator_status(
        _node_for_operator_status(), {'job': 'black', 'place_id': 'Zone A'},
    )

    assert status['ready'] is True
    assert status['overall_status'] == 'พร้อมใช้งาน'
    assert status['counts'] == {'black': 2, 'white': 1, 'yellow': 1}
    assert status['selected_job'] == 'สีดำ'
    assert status['selected_place'] == 'โซน A'
    assert all('pose' not in key and 'raw' not in key for key in status)
    assert {check['label'] for check in status['checks']} >= {
        'หุ่นยนต์', 'กล้อง', 'ความลึก', 'การคาลิเบรต', 'หัวดูด',
    }


def test_operator_fault_codes_have_actionable_thai_messages():
    message = DobotWebNode._operator_fault_message({
        'blockers': ['CAMERA_NOT_READY'],
    })
    assert 'USB 3' in message
    assert 'กล้อง' in message


def test_operator_start_refuses_failed_preflight_before_motion():
    node = _node_for_operator_status()
    node._operator_preflight = lambda job, place: {'ready': False}
    node.vision_pick_selected = lambda *args, **kwargs: pytest.fail('motion started')

    with pytest.raises(ValueError, match='ระบบไม่พร้อมใช้งาน'):
        DobotWebNode.operator_start(node, {'job': 'black', 'place_id': 'Zone A'})


def test_operator_stop_propagates_to_vision_robot_abort():
    node = _node_for_operator_status()
    called = []
    node.vision_cancel = lambda: called.append(True) or {'requested': True}
    node._operator_job['active'] = True

    result = DobotWebNode.operator_stop(node)

    assert called == [True]
    assert node._operator_cancel_event.is_set()
    assert node._operator_job['state'] == 'STOPPING'
    assert result['requested'] is True


def test_operator_is_default_and_engineer_page_is_removed():
    app = create_app(type('Node', (), {'api_token': ''})())
    routes = {
        route.path: route.endpoint
        for route in app.routes
        if hasattr(route, 'endpoint')
    }

    assert 'หน้าควบคุมผู้ปฏิบัติงาน' in routes['/']()
    assert '/engineer' not in routes
    assert '/api/operator/status' in routes
    assert '/api/operator/start' in routes
    assert '/api/operator/stop' in routes
