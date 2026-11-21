"""Run the camera under systemd and reopen it after a wall-clock step."""

import signal
import subprocess
import sys
import time


def clock_offset():
    return time.time() - time.clock_gettime(time.CLOCK_BOOTTIME)


def run(command):
    previous = clock_offset()
    driver = subprocess.Popen(command)
    try:
        while True:
            try:
                return driver.wait(timeout=2)
            except subprocess.TimeoutExpired:
                current = clock_offset()
                if abs(current - previous) > 1:
                    print(f"Host clock stepped by {current - previous:+.1f}s. "
                          "Restarting Orbbec acquisition.", file=sys.stderr, flush=True)
                    return 75  # Retry through the camera unit and its ownership checks.
                previous = current
    except KeyboardInterrupt:
        return 0
    finally:
        if driver.poll() is None:
            driver.send_signal(signal.SIGINT)
            try:
                driver.wait(timeout=10)
            except subprocess.TimeoutExpired:
                driver.kill()
                driver.wait()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
