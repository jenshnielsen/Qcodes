import os
import signal
import time
import subprocess

# import win32api
# import win32con
# import win32process


def test_double_kill():
    proc = subprocess.Popen("python nointerupt.py", shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    time.sleep(2)
    pid = proc.pid
    while pid is None:
        pid = proc.pid
    os.kill(pid, signal.CTRL_C_EVENT)
    os.kill(pid, signal.CTRL_C_EVENT)
    output = proc.communicate()
    a = output[0].splitlines()
    for line in a:
        print(line)

    stdout = output[0].splitlines()[-1]
    result = eval(stdout.decode())
    print(result)
    assert isinstance(result[-1], int)


def test_single_kill():
    proc = subprocess.Popen("python nointerupt.py",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    time.sleep(2)
    pid = proc.pid
    while pid is None:
        pid = proc.pid
    print(pid)
    proc.send_signal(signal.CTRL_BREAK_EVENT)
    output = proc.communicate()
    print(output)
    # stdout = output[0].splitlines()[-1]
    # result = eval(stdout.decode())
    # assert result[-1] == 'done_looping'


def test_no_kill():
    proc = subprocess.Popen("python nointerupt.py", shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    output = proc.communicate()
    signal.signal(signal.SIGINT, signal.default_int_handler)

    stdout = output[0].splitlines()[-1]
    result = eval(stdout.decode())
    assert result[-1] == 'completed'
    assert result[-2] == 'done_looping'


if __name__ == '__main__':
    # test_no_kill()
    test_single_kill()
    # test_double_kill()

