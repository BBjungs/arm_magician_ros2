import os
import threading

from dobot_driver.interface import Interface


class LazyInterface:
    """Open the serial device only when the first hardware call is made."""

    def __init__(self, port):
        self._port = port
        self._interface = None
        self._lock = threading.Lock()

    def _get_interface(self):
        if self._interface is None:
            with self._lock:
                if self._interface is None:
                    self._interface = Interface(self._port)
        return self._interface

    def __getattr__(self, name):
        return getattr(self._get_interface(), name)


bot = LazyInterface(os.environ.get('DOBOT_SERIAL_PORT', '/dev/ttyUSB0'))
