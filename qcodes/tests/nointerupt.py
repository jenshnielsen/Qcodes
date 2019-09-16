from qcodes.utils.delaykeyboardinterrupt import DelayedKeyboardInterrupt
import signal
import os
import time


def not_to_be_interrupted():
    output = []

    try:
        with DelayedKeyboardInterrupt():

            print(f"sub process signal handler {signal.getsignal(signal.SIGINT)}")
            print(f"sub pid = {os.getpid()}")
            for i in range(20):
                print(f"sub process signal handler {signal.getsignal(signal.SIGINT)}")
                time.sleep(0.1)
                output.append(i)
                print(i)
                print(f"sub process signal handler {signal.getsignal(signal.SIGINT)}")
            output.append("done_looping")
            print("done_looping")
        output.append('completed')
        print("completed")
    except KeyboardInterrupt:
        pass
        # print(f"at interrupt sub process signal handler {signal.getsignal(signal.SIGINT)}")
    print(output)


if __name__ == '__main__':
    not_to_be_interrupted()