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

    # ctrl_C_event and ctrl_break_events are the only ones that can be send on windows. They can only be send
    # to a process group and not an individual process. We therefore create a new process group below.
    # Furthermore they can only be sent to a process bound to the same console not to detached processes or
    # across console boundaries.
    # However, new process groups disable handling of ctrl_c events. ctrl-break events are not handled by
    # the default signal handler for sigint (keyboardinterupt) but trigger a SIGBREAK.
    # Provided a signal handler is added for sigbreak this test works as expected. But does not test what we want
    # https://docs.microsoft.com/en-us/windows/win32/procthread/process-creation-flags
    # https://stackoverflow.com/questions/44124338/trying-to-implement-signal-ctrl-c-event-in-python3-6
    # it may be possible to restore the python signal handlers here
    # for setconsolectrlhandler https://docs.microsoft.com/en-us/windows/console/setconsolectrlhandler
    proc = subprocess.Popen("python nointerupt.py",
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    time.sleep(2)
    pid = proc.pid
    while pid is None:
        pid = proc.pid
    print(pid)
    #os.kill(pid, signal.CTRL_BREAK_EVENT)
    time.sleep(1)
    proc.send_signal(signal.CTRL_C_EVENT)
    #proc.send_signal(signal.CTRL_BREAK_EVENT)
    output = proc.communicate()
    print(output)
    # stdout = output[0].splitlines()[-1]
    # result = eval(stdout.decode())
    # assert result[-1] == 'done_looping'


def test_no_kill():
    proc = subprocess.Popen("python nointerupt.py", shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    output = proc.communicate()

    stdout = output[0].splitlines()[-1]
    result = eval(stdout.decode())
    assert result[-1] == 'completed'
    assert result[-2] == 'done_looping'


if __name__ == '__main__':
    #test_no_kill()
    test_single_kill()
    # test_double_kill()

