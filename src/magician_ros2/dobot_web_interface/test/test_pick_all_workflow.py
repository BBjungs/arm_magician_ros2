import threading

from dobot_web_interface.web_interface import DobotWebNode


def _node(scenes):
    node = object.__new__(DobotWebNode)
    node._operator_job_lock = threading.RLock()
    node._operator_cancel_event = threading.Event()
    node._vision_cancel_event = threading.Event()
    node._operator_job = {
        'active': True,
        'state': 'PICKING',
        'message': '',
        'job': 'pick_all',
        'place_id': 'Zone A',
        'completed': 0,
        'total': 2,
        'failed': 0,
    }
    node.pick_all_max_items = 10
    node.vision_mode = 'fixed_camera'
    node.get_logger = lambda: type('Logger', (), {
        'info': staticmethod(lambda *_args, **_kwargs: None),
        'warn': staticmethod(lambda *_args, **_kwargs: None),
    })()
    node._scenes = iter(scenes)
    node.detect_requests = []
    node.pick_requests = []

    def fresh(object_class, place_id):
        node.detect_requests.append((object_class, place_id))
        return {'detections': next(node._scenes)}

    node._request_fresh_detection = fresh
    node._operator_preflight = lambda job, place: {
        'ready': True,
        'selected': {'selected': True},
    }
    node._operator_job_spec = lambda job: (job, {'class_name': job + '_cap'})

    def pick(payload, **_kwargs):
        node.pick_requests.append(payload)
        return {'executed': True, 'placed': True, 'observation_returned': True}

    node.vision_pick_selected = pick
    return node


def test_pick_all_uses_a_fresh_scene_before_every_item_and_after_each_place():
    node = _node([
        [{'class_name': 'black_cap'}, {'class_name': 'white_cap'}],
        [{'class_name': 'white_cap'}],
        [],
    ])

    DobotWebNode._run_operator_job(node, 'pick_all', 'Zone A', {'black': 1, 'white': 1})

    assert node.detect_requests == [('all', 'Zone A')] * 3
    assert [item['object_class'] for item in node.pick_requests] == [
        'black_cap', 'white_cap',
    ]
    assert node._operator_job['state'] == 'DONE'
    assert node._operator_job['completed'] == 2


def test_pick_all_does_not_move_when_selected_target_disappears_before_pick():
    node = _node([
        [{'class_name': 'black_cap'}],
        [],
    ])
    node._operator_preflight = lambda _job, _place: {
        'ready': False,
        'selected': {'selected': False},
    }

    DobotWebNode._run_operator_job(node, 'pick_all', 'Zone A', {'black': 1})

    assert node.pick_requests == []
    assert node._operator_job['state'] == 'DONE'
    assert node._operator_job['completed'] == 0
