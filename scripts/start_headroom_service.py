#!/usr/bin/env python3
"""Keep the local Headroom proxy available, adopting an existing wrap session."""
import os
import socket
import time
from pathlib import Path


def port_in_use():
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", 8787))
        except OSError:
            return True
    return False


if __name__ == "__main__":
    # Leave a running interactive session intact; take over when it exits.
    if port_in_use():
        print("Waiting for the existing Headroom proxy to exit before taking over", flush=True)
    while port_in_use():
        time.sleep(2)
    python = str(Path.home() / ".local/share/uv/tools/headroom-ai/bin/python")
    os.execv(python, [python, "-m", "headroom.cli", "proxy", "--host", "127.0.0.1",
                     "--port", "8787", "--workers", "1"])
