from qcodes import VisaInstrument
from qcodes.utils import validators as vals
from cmath import phase
import numpy as np
from qcodes import Parameter
import time

class FrequencySweep(Parameter):
    """
    Hardware controlled parameter class for Rohde Schwarz RSZNB20 trace.

    Instrument returns an list of transmission data in the form of a list of
    complex numbers taken from a frequency sweep.

    TODO:
      - ability to choose for abs or db in magnitude return
    """
    def __init__(self, name, instrument, start, stop, npts):
        super().__init__(name)
        self._instrument = instrument
        self.set_sweep(start, stop, npts)
        self.names = ('magnitude', 'phase')
        self.units = ('dBm', 'rad')
        self.setpoint_names = (('frequency',), ('frequency',))

    def set_sweep(self, start, stop, npts):
        #  needed to update config of the software parameter on sweep chage
        # freq setpoints tuple as needs to be hashable for look up
        f = tuple(np.linspace(int(start), int(stop), num=npts))
        self.setpoints = ((f,), (f,))
        self.shapes = ((npts,), (npts,))

    def get(self):
        self._instrument.write('SENS1:AVER:STAT ON')
        self._instrument.write('AVER:CLE')
        self._instrument.cont_meas_off()

        # instrument averages over its last 'avg' number of sweeps
        # need to ensure averaged result is returned
        for avgcount in range(self._instrument.avg()):
            self._instrument.write('INIT:IMM; *WAI')
        data_str = self._instrument.ask('CALC:DATA? SDAT').split(',')
        data_list = [float(v) for v in data_str]

        # data_list of complex numbers [re1,im1,re2,im2...]
        data_arr = np.array(data_list).reshape(int(len(data_list) / 2), 2)
        mag_array, phase_array = [], []
        for comp in data_arr:
            complex_num = complex(comp[0], comp[1])
            mag_array.append(abs(complex_num))
            phase_array.append(phase(complex_num))
        self._instrument.cont_meas_on()
        return mag_array, phase_array


class ZNB20(VisaInstrument):
    """
    qcodes driver for the Rohde & Schwarz ZNB20 virtual network analyser

    Requires FrequencySweep parameter for taking a trace

    TODO:
    - centre/span settable for frequwncy sweep
    - check initialisation settings and test functions
    """
    def __init__(self, name, address, **kwargs):

        super().__init__(name=name, address=address, **kwargs)

        self.add_parameter(name='power',
                           label='Power',
                           units='dBm',
                           get_cmd='SOUR:POW?',
                           set_cmd='SOUR:POW {:.4f}',
                           get_parser=int,
                           vals=vals.Numbers(-150, 25))

        self.add_parameter(name='bandwidth',
                           label='Bandwidth',
                           units='Hz',
                           get_cmd='SENS:BAND?',
                           set_cmd='SENS:BAND {:.4f}',
                           get_parser=int,
                           vals=vals.Numbers(1, 1e6))

        self.add_parameter(name='avg',
                           label='Averages',
                           units='',
                           get_cmd='AVER:COUN?',
                           set_cmd='AVER:COUN {:.4f}',
                           get_parser=int,
                           vals=vals.Numbers(1, 5000))

        self.add_parameter(name='start',
                           get_cmd='SENS:FREQ:START?',
                           set_cmd=self._set_start,
                           get_parser=int)

        self.add_parameter(name='stop',
                           get_cmd='SENS:FREQ:STOP?',
                           set_cmd=self._set_stop,
                           get_parser=int)

        self.add_parameter(name='npts',
                           get_cmd='SENS:SWE:POIN?',
                           set_cmd=self._set_npts,
                           get_parser=int)

        self.add_parameter(name='trace',
                           start=self.start(),
                           stop=self.stop(),
                           npts=self.npts(),
                           parameter_class=FrequencySweep)
                           
        self.add_parameter(name='spec_state',
                           set_cmd=self._set_spec_state)
                           
        # TODO(nataliejpg) add center frequency as parameter

        self.add_parameter(name='cav_freq',
                           get_cmd=self._get_cav_freq,
                           set_cmd=self._set_cav_freq)
                           
        self.add_parameter(name='cav_pow',
                           get_cmd=self._get_cav_pow,
                           set_cmd=self._set_cav_pow)

        self.add_function('reset', call_cmd='*RST')
        self.add_function('tooltip_on', call_cmd='SYST:ERR:DISP ON')
        self.add_function('tooltip_off', call_cmd='SYST:ERR:DISP OFF')
        self.add_function('cont_meas_on', call_cmd='INIT:CONT:ALL ON')
        self.add_function('cont_meas_off', call_cmd='INIT:CONT:ALL OFF')
        self.add_function('update_display_once', call_cmd='SYST:DISP:UPD ONCE')
        self.add_function('update_display_on', call_cmd='SYST:DISP:UPD ON')
        self.add_function('update_display_off', call_cmd='SYST:DISP:UPD OFF')
        self.add_function('rf_off', call_cmd='OUTP1 OFF')
        self.add_function('rf_on', call_cmd='OUTP1 ON')

        self.initialise()
        self.connect_message()
        
    def _set_spec_state(self, val):
        if val == 1:
            freq = self.ask('SENS:FREQ:CENT?')
            pow = self.power()
            self.write('SOUR:POW3:STAT 1')
            time.sleep(0.2)
            self.write('SOUR:POW1:PERM 1')
            time.sleep(0.2)
            self.write('SOUR:POW3:PERM 1')
            time.sleep(0.2)
            self.cav_freq(freq)
            self.cav_pow(pow)   
        else:
            self.write('SOUR:FREQ1:CONV:ARB:IFR 1, 1, 0, SWE')
            self.write('SOUR:FREQ2:CONV:ARB:IFR 1, 1, 0, SWE')
            self.write('SOUR:POW1:OFFS 0, CPAD')
            self.write('SOUR:POW2:OFFS 0, CPAD')
            self.write('SOUR:POW3:STAT 0')
            self.write('SOUR:POW1:PERM 0')
            self.write('SOUR:POW3:PERM 0')          
       

    # do these two smarter?
       
    def _get_cav_freq(self):
        ret = self.ask('SOUR:FREQ1:CONV:ARB:IFR?').split(',')
        return int(ret[2])
        
    def _set_cav_freq(self, freq):
        self.write('SOUR:FREQ1:CONV:ARB:IFR 0, 1, {:.6f}, CW'.format(freq))
        # add pause?
        self.write('SOUR:FREQ2:CONV:ARB:IFR 0, 1, {:.6f}, CW'.format(freq))
        
    def _get_cav_pow(self):
        ret = self.ask('SOUR:POW1:OFFS?').split(',')
        return int(ret[0])
        
    def _set_cav_pow(self, pow):
        self.write('SOUR:POW1:OFFS {:.3f}, ONLY'.format(pow))
        # add pause?
        self.write('SOUR:POW2:OFFS {:.3f}, ONLY'.format(pow))
    
    def _set_start(self, val):
        self.write('SENS:FREQ:START {:.4f}'.format(val))
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(val, self.stop(), self.npts())

    def _set_stop(self, val):
        self.write('SENS:FREQ:STOP {:.4f}'.format(val))
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(self.start(), val, self.npts())

    def _set_npts(self, val):
        self.write('SENS:SWE:POIN {:.4f}'.format(val))
        # update setpoints for FrequencySweep param
        self.trace.set_sweep(self.start(), self.stop(), val)

    def initialise(self):
        self.write('*RST')
        self.write('SENS1:SWE:TYPE LIN')
        self.write('SENS1:SWE:TIME:AUTO ON')
        self.write('TRIG1:SEQ:SOUR IMM')
        self.write('SENS1:AVER:STAT ON')
        self.update_display_on()
        self.start(1e6)
        self.stop(2e6)
        self.npts(10)
        self.power(-50)
