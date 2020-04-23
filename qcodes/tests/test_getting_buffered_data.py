from .instrument_mocks import DummyBufferInstrument, call1d
from qcodes.utils.dataset.doNd import do1d
import numpy as np


def test_doing_two_d_buffered():
    inst = DummyBufferInstrument('foobar')
    start1 = 20
    stop1 = 30
    points1 = 11
    hold1 = 0
    start2 = 10
    stop2 = 20
    points2 = 11
    hold2 = 0

    def append_parameter1_to_buffer():
        value = inst.parameter3.get()
        print(value)
        inst._buffer.append(value)


    gate_sweep = call1d(inst.parameter2, np.linspace(start2, stop2, points2), hold2,
                        append_parameter1_to_buffer,
                        inst_setpoints=(inst.buffered_array,),
                        enter_actions=(inst.clean_buffer,))
    ds, plot, plot2 = do1d(inst.parameter1, start1, stop1, points1, hold1, gate_sweep, inst.buffered_array)

    ds
