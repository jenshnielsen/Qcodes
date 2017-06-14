import logging

from qcodes import VisaInstrument
from qcodes import ChannelList, InstrumentChannel
from qcodes.utils import validators as vals
from cmath import phase
import numpy as np
from qcodes import MultiParameter, ArrayParameter

log = logging.getLogger(__name__)


class FrequencySweepMagPhase(MultiParameter):
    """
    Hardware controlled parameter class for Rohde Schwarz RSZNB20 trace.

    Instrument returns an list of transmission data in the form of a list of
    complex numbers taken from a frequency sweep.

    This is a multiparameter containing both amplitude and phase

    Args:
        name: parameter name
        instrument: instrument the parameter belongs to
        start: starting frequency of sweep
        stop: ending frequency of sweep
        npts: number of points in frequency sweep

    Methods:
          set_sweep(start, stop, npts): sets the shapes and
              setpoint arrays of the parameter to correspond with the sweep
          get(): executes a sweep and returns magnitude and phase arrays

    TODO:
      - ability to choose for linear or db in magnitude return
    """
    def __init__(self, name, instrument, start, stop, npts, channel):
        super().__init__(name, names=("", ""), shapes=((), ()))
        self._instrument = instrument
        self.set_sweep(start, stop, npts)
        self._channel = channel
        self.names = ('{}_magnitude'.format(instrument._vna_parameter),
                      '{}_phase'.format(instrument._vna_parameter))
        self.labels = ('{} magnitude'.format(instrument._vna_parameter),
                       '{} phase'.format(instrument._vna_parameter))
        self.units = ('', 'rad')
        self.setpoint_units = (('Hz',), ('Hz',))
        self.setpoint_names = (('frequency',), ('frequency',))

    def set_sweep(self, start, stop, npts):
        #  needed to update config of the software parameter on sweep change
        # freq setpoints tuple as needs to be hashable for look up
        f = tuple(np.linspace(int(start), int(stop), num=npts))
        self.setpoints = ((f,), (f,))
        self.shapes = ((npts,), (npts,))

    def get(self):
        if not self._instrument._parent.rf_power():
            log.warning("RF output is off")
        self._instrument.write('SENS{}:AVER:STAT ON'.format(self._channel))
        self._instrument.write('SENS{}:AVER:CLE'.format(self._channel))
        self._instrument._parent.cont_meas_off()

        # instrument averages over its last 'avg' number of sweeps
        # need to ensure averaged result is returned
        for avgcount in range(self._instrument.avg()):
            self._instrument.write('INIT:IMM; *WAI')
        data_str = self._instrument.ask('CALC{}:DATA? SDAT'.format(self._channel)).split(',')
        data_list = [float(v) for v in data_str]

        # data_list of complex numbers [re1,im1,re2,im2...]
        data_arr = np.array(data_list).reshape(int(len(data_list) / 2), 2)
        mag_array, phase_array = [], []
        for comp in data_arr:
            complex_num = complex(comp[0], comp[1])
            mag_array.append(abs(complex_num))
            phase_array.append(phase(complex_num))
        self._instrument._parent.cont_meas_on()
        return mag_array, phase_array


class FrequencySweep(ArrayParameter):
    """
    Hardware controlled parameter class for Rohde Schwarz RSZNB20 trace.

    Instrument returns an array of transmission or reflection data depending on the
    active measurement.

    Args:
        name: parameter name
        instrument: instrument the parameter belongs to
        start: starting frequency of sweep
        stop: ending frequency of sweep
        npts: number of points in frequency sweep

    Methods:
          set_sweep(start, stop, npts): sets the shapes and
              setpoint arrays of the parameter to correspond with the sweep
          get(): executes a sweep and returns magnitude and phase arrays

    """
    def __init__(self, name, instrument, start, stop, npts, channel):
        super().__init__(name, shape=(npts,),
                         instrument=instrument,
                         unit='dB',
                         label='{} magnitude'.format(instrument._vna_parameter),
                         setpoint_units=('Hz',),
                         setpoint_names=('frequency',))
        self.set_sweep(start, stop, npts)
        self._channel = channel

    def set_sweep(self, start, stop, npts):
        #  needed to update config of the software parameter on sweep change
        # freq setpoints tuple as needs to be hashable for look up
        f = tuple(np.linspace(int(start), int(stop), num=npts))
        self.setpoints = (f,)
        self.shape = (npts,)

    def get(self):
        if not self._instrument._parent.rf_power():
            log.warning("RF output is off")
        old_format = self._instrument.format()
        self._instrument.format('dB')
        self._instrument.write('SENS{}:AVER:STAT ON'.format(self._channel))
        self._instrument.write('SENS{}:AVER:CLE'.format(self._channel))
        self._instrument._parent.cont_meas_off()

        # instrument averages over its last 'avg' number of sweeps
        # need to ensure averaged result is returned
        for avgcount in range(self._instrument.avg()):
            self._instrument.write('INIT:IMM; *WAI')
        data_str = self._instrument.ask('CALC{}:DATA? FDAT'.format(self._channel))
        data = np.array(data_str.rstrip().split(',')).astype('float64')

        self._instrument._parent.cont_meas_on()
        self._instrument.format(old_format)
        return data


class ZNB20Channel(InstrumentChannel):

    def __init__(self, parent, name, channel):
        n = channel
        self._instrument_channel = channel
        self._tracename = "Ch{}Trc1".format(channel)
        self._vna_parameter = name
        super().__init__(parent, name)

        # map hardware channel to measurement
        # hardware channels are mapped one to one to qcodes channels
        # we are not using sub traces within channels.
        self.write("CALC{}:PAR:SDEF '{}', '{}'".format(self._instrument_channel,
                                                       self._tracename,
                                                       self._vna_parameter))

        self.add_parameter(name='power',
                           label='Power',
                           unit='dBm',
                           get_cmd='SOUR{}:POW?'.format(n),
                           set_cmd='SOUR{}:POW {{:.4f}}'.format(n),
                           get_parser=int,
                           vals=vals.Numbers(-150, 25))
        self.add_parameter(name='bandwidth',
                           label='Bandwidth',
                           unit='Hz',
                           get_cmd='SENS{}:BAND?'.format(n),
                           set_cmd='SENS{}:BAND {{:.4f}}'.format(n),
                           get_parser=int,
                           vals=vals.Numbers(1, 1e6))
        self.add_parameter(name='avg',
                           label='Averages',
                           unit='',
                           get_cmd='SENS{}:AVER:COUN?'.format(n),
                           set_cmd='SENS{}'.format(n) + ':AVER:COUN {:.4f}',
                           get_parser=int,
                           vals=vals.Numbers(1, 5000))
        self.add_parameter(name='start',
                           get_cmd='SENS{}:FREQ:START?'.format(n),
                           set_cmd=self._set_start,
                           get_parser=float,
                           vals=vals.Numbers(self._parent._min_freq, self._parent._max_freq - 10))
        self.add_parameter(name='stop',
                           get_cmd='SENS{}:FREQ:STOP?'.format(n),
                           set_cmd=self._set_stop,
                           get_parser=float,
                           vals=vals.Numbers(self._parent._min_freq + 1, self._parent._max_freq))
        self.add_parameter(name='center',
                           get_cmd='SENS{}:FREQ:CENT?'.format(n),
                           set_cmd=self._set_center,
                           get_parser=float,
                           vals=vals.Numbers(self._parent._min_freq + 0.5, self._parent._max_freq - 10))
        self.add_parameter(name='span',
                           get_cmd='SENS{}:FREQ:SPAN?'.format(n),
                           set_cmd=self._set_span,
                           get_parser=float,
                           vals=vals.Numbers(1, self._parent._max_freq - self._parent._min_freq))
        self.add_parameter(name='npts',
                           get_cmd='SENS:SWE:POIN?',
                           set_cmd=self._set_npts,
                           get_parser=int)
        self.add_parameter(name='format',
                           get_cmd='CALC{}:FORM?'.format(n),
                           set_cmd='CALC{}:FORM {{}}'.format(n),
                           val_mapping={'dB': 'MLOG\n',
                                        'Linear Magnitude': 'MLIN\n',
                                        'Phase': 'PHAS\n',
                                        'Unwr Phase': 'UPH\n',
                                        'Polar': 'POL\n',
                                        'Smith': 'SMIT\n',
                                        'Inverse Smith': 'ISM\n',
                                        'SWR': 'SWR\n',
                                        'Real': 'REAL\n',
                                        'Imaginary': 'IMAG\n',
                                        'Delay': "GDEL\n",
                                        'Complex': "COMP\n"
                                        })

        self.add_parameter(name='trace',
                           start=self.start(),
                           stop=self.stop(),
                           npts=self.npts(),
                           channel=n,
                           parameter_class=FrequencySweepMagPhase)
        self.add_parameter(name='tracedb',
                           start=self.start(),
                           stop=self.stop(),
                           npts=self.npts(),
                           channel=n,
                           parameter_class=FrequencySweep)

        self.add_function('autoscale',
                          call_cmd='DISPlay:TRACe1:Y:SCALe:AUTO ONCE, "{}"'.format(self._tracename))

    def _set_start(self, val):
        channel = self._instrument_channel
        self.write('SENS{}:FREQ:START {:.4f}'.format(channel, val))
        stop = self.stop()
        npts = self.npts()

        if val >= stop:
            raise ValueError("Stop frequency must be larger than start frequency.")
        # we get start as the vna may not be able to set it to the exact value provided
        start = self.start()
        if val != start:
            log.warning("Could not set start to {} setting it to {}".format(val, start))
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(start, stop, npts)
        self.tracedb.set_sweep(start, stop, npts)

    def _set_stop(self, val):
        channel = self._instrument_channel
        start = self.start()
        npts = self.npts()
        if val <= start:
            raise ValueError("Stop frequency must be larger than start frequency.")
        self.write('SENS{}:FREQ:STOP {:.4f}'.format(channel, val))
        # we get stop as the vna may not be able to set it to the exact value provided
        stop = self.stop()
        if val != stop:
            log.warning("Could not set stop to {} setting it to {}".format(val, stop))
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(start, stop, npts)
        self.tracedb.set_sweep(start, stop, npts)

    def _set_npts(self, val):
        channel = self._instrument_channel
        self.write('SENS{}:SWE:POIN {:.4f}'.format(channel, val))
        start = self.start()
        stop = self.stop()
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(start, stop, val)
        self.tracedb.set_sweep(start, stop, val)

    def _set_span(self, val):
        channel = self._instrument_channel
        self.write('SENS{}:FREQ:SPAN {:.4f}'.format(channel, val))
        start = self.start()
        stop = self.stop()
        npts = self.npts()
        self.trace.set_sweep(start, stop, npts)
        self.tracedb.set_sweep(start, stop, npts)

    def _set_center(self, val):
        channel = self._instrument_channel
        self.write('SENS{}:FREQ:CENT {:.4f}'.format(channel, val))
        start = self.start()
        stop = self.stop()
        npts = self.npts()
        self.trace.set_sweep(start, stop, npts)
        self.tracedb.set_sweep(start, stop, npts)


class ZNB20(VisaInstrument):
    """
    qcodes driver for the Rohde & Schwarz ZNB20 virtual network analyser

    Requires FrequencySweep parameter for taking a trace

    TODO:
    - check initialisation settings and test functions
    """
    def __init__(self, name, address, **kwargs):

        super().__init__(name=name, address=address, **kwargs)
        n = 1
        self._sindex_to_channel = {}
        self._channel_to_sindex = {}
        self._max_freq = 20e9
        self._min_freq = 100e3
        channels = ChannelList(self, "VNAChannels", ZNB20Channel,
                               snapshotable=True, oneindexed=True)
        for i in range(1, 3):
            self._sindex_to_channel[i] = {}
            for j in range(1, 3):
                ch_name = 'S' + str(i) + str(j)
                channel = ZNB20Channel(self, ch_name, n)
                channels.append(channel)
                self._sindex_to_channel[i][j] = n
                self._channel_to_sindex[n] = (i, j)
                n += 1
        self.add_submodule("channels", channels)
        self.channels.lock()
        self.add_parameter(name='rf_power',
                           get_cmd='OUTP1?',
                           set_cmd='OUTP1 {}',
                           val_mapping={True: '1\n', False: '0\n'})

        self.add_function('reset', call_cmd='*RST')
        self.add_function('tooltip_on', call_cmd='SYST:ERR:DISP ON')
        self.add_function('tooltip_off', call_cmd='SYST:ERR:DISP OFF')
        self.add_function('cont_meas_on', call_cmd='INIT:CONT:ALL ON')
        self.add_function('cont_meas_off', call_cmd='INIT:CONT:ALL OFF')
        self.add_function('update_display_once', call_cmd='SYST:DISP:UPD ONCE')
        self.add_function('update_display_on', call_cmd='SYST:DISP:UPD ON')
        self.add_function('update_display_off', call_cmd='SYST:DISP:UPD OFF')
        self.add_function('display_sij_split', call_cmd='DISP:LAY GRID;:DISP:LAY:GRID 2,2')
        self.add_function('display_sij_overlay', call_cmd='DISP:LAY GRID;:DISP:LAY:GRID 1,1')
        self.add_function('rf_off', call_cmd='OUTP1 OFF')
        self.add_function('rf_on', call_cmd='OUTP1 ON')

        self.initialise()
        self.autoscale_all()
        self.connect_message()

    def autoscale_all(self):
        for channel in self.channels:
            channel.autoscale()

    def _set_default_values(self):
        for channel in self.channels:
            channel.start(1e6)
            channel.stop(2e6)
            channel.npts(10)
            channel.power(-50)

    def initialise(self):
        self.write('*RST')
        for n in range(1, 5):
            self.write('SENS{}:SWE:TYPE LIN'.format(n))
            self.write('SENS{}:SWE:TIME:AUTO ON'.format(n))
            self.write('TRIG{}:SEQ:SOUR IMM'.format(n))
            self.write('SENS{}:AVER:STAT ON'.format(n))
        self.update_display_on()
        self._set_default_values()
        self.rf_off()
        self.display_sij_split()
