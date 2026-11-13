"""Own partial ROS initialization and retain failures even without journald."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import sys
import traceback

import rclpy
from rclpy.signals import SignalHandlerOptions


def record_failure(label):
    message = (f'\n{datetime.now(timezone.utc).isoformat()} pid={os.getpid()} '
               f'{label}\n{traceback.format_exc()}')
    print(message, file=sys.stderr, flush=True)
    try:
        directory = Path(os.environ.get('ROS_LOG_DIR', '~/.ros/log')).expanduser()
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'startup-failures.log').open('a') as stream:
            stream.write(message)
    except OSError as exc:
        print(f'Cannot persist traceback: {exc}', file=sys.stderr, flush=True)


@contextmanager
def node_lifecycle(node_type, args=None, cleanup=None):
    """Destroy partially constructed nodes and preserve the original exception."""
    node = None
    handlers = {}
    try:
        # Keep the ROS context alive until executor/worker cleanup has finished.
        # rclpy's default signal handler destroys it before these owners stop.
        for number in (signal.SIGINT, signal.SIGTERM):
            handlers[number] = signal.signal(number, signal.default_int_handler)
        rclpy.init(args=args, signal_handler_options=SignalHandlerOptions.NO)
        node = node_type.__new__(node_type)
        node.__init__()
        yield node
    except KeyboardInterrupt:
        pass
    except BaseException:
        record_failure(node_type.__name__ + ' startup/runtime failure')
        raise
    finally:
        failed = sys.exc_info()[0] is not None
        try:
            if node is not None:
                try:
                    if cleanup is not None:
                        cleanup(node)
                finally:
                    if hasattr(node, 'handle'):
                        node.destroy_node()
        except Exception:
            record_failure(node_type.__name__ + ' cleanup failure')
            if not failed:
                raise
        finally:
            try:
                if rclpy.ok():
                    rclpy.shutdown()
            finally:
                for number, handler in handlers.items():
                    signal.signal(number, handler)
