import os
from signal import SIGINT, CTRL_C_EVENT
import threading
import time

from qcodes.utils.delaykeyboardinterrupt import DelayedKeyboardInterrupt


def not_to_be_interrupted(output):
    with DelayedKeyboardInterrupt():
        for i in range(20):
            time.sleep(0.1)
            output.append(i)
        output.append("done_looping")
    output.append('completed')


pid = os.getpid()


def trigger_double_kill():
    # You could do something more robust, e.g. wait until port is listening
    time.sleep(1)
    os.kill(pid, CTRL_C_EVENT)
    os.kill(pid, CTRL_C_EVENT)


def trigger_single_kill():
    # You could do something more robust, e.g. wait until port is listening
    time.sleep(1)
    os.kill(pid, CTRL_C_EVENT)


def test_double_kill():
    try:
        thread = threading.Thread(target=trigger_double_kill)
        thread.daemon = True
        thread.start()
        output = []
        not_to_be_interrupted(output)
    except KeyboardInterrupt:
        pass

    #assert "done_looping" not in output
    #assert "completed" in output


def foo_single_kill():
    try:
        thread = threading.Thread(target=trigger_single_kill)
        thread.daemon = True
        thread.start()
        output = []
        not_to_be_interrupted(output)
    except KeyboardInterrupt:
        pass

if __name__ == '__main__':
    foo_single_kill()