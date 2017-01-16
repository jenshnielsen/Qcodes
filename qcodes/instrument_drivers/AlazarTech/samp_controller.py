import logging
from .ATS import AcquisitionController
import numpy as np
from qcodes import Parameter
from qcodes.instrument_drivers.AlazarTech.acq_helpers import filter_win, filter_ls, sample_to_volt_u12
from qcodes.instrument.parameter import ManualParameter
# from qcodes.utils.validators import Validator, Numbers, Ints, Enum, Anything
# from qcodes.utils import validators


# class AqcParam(Parameter):
#     def __init__(self, name, instrument, unit, get_cmd, set_cmd):
#         super().__init__(name)
#         self._instrument = instrument
#         self.units = unit
#         setattr(self, 'get', get_cmd)
#         getattr(self, 'set', set_cmd)
#         # self.get = get_cmd
#         # self.set = set_cmd

# class AqcParam(Parameter):
#     def __init__(self, name, instrument, validation_fn):
#         super().__init__(name)
#         self._instrument = instrument
#         setattr(self, 'acq_validate', validation_fn)
#         # if initial_value is not None:
#         #     #self.acq_validate(initial_value)
#         #     self._save_val(initial_value)

#         def set(self, value):
#             self.acq_validate(value)
#             self._save_val(value)

#         def get(self, value):
#             return self._latest()['value']

class SamplesParam(Parameter):
    """
    Hardware controlled parameter class for Alazar acquisition. To be used with
    HD_Samples_Controller (tested with ATS9360 board) for return of an array of
    sample data from the Alazar, averaged over records and buffers.

    TODO(nataliejpg) refactor setpoints/shapes horriblenesss
    TODO(nataliejpg) setpoint units
    """

    def __init__(self, name, instrument):
        super().__init__(name)
        self._instrument = instrument
        self.acquisition_kwargs = {}
        self.names = ('magnitude', 'phase')
        self.units = ('', '')
        self.setpoint_names = (('acq_time (s)',), ('acq_time (s)',))
        self.setpoints = ((1,), (1,))
        self.shapes = ((1,), (1,))

    def update_sweep(self, start, stop, npts):
        n = tuple(np.linspace(start, stop, num=npts))
        self.setpoints = ((n,), (n,))
        self.shapes = ((npts,), (npts,))

    def get(self):
        mag, phase = self._instrument._get_alazar().acquire(
            acquisition_controller=self._instrument,
            **self.acquisition_kwargs)
        print(mag)
        return mag, phase


class HD_Samples_Controller(AcquisitionController):
    """
    This is the Acquisition Controller class which works with the ATS9360,
    averaging over buffers and records and demodulating with a software
    reference signal, returning the  samples.

    Args:
        name: name for this acquisition_conroller as an instrument
        alazar_name: the name of the alazar instrument such that this controller
            can communicate with the Alazar
        demod_freq: the frequency of the software wave to be created
        filt: the filter to be used to filter out double freq component (win or ls)
        numtaps: number of freq components used in the filter
        chan_b: whether there is also a second channel of data to be processed
            and returned
        **kwargs: kwargs are forwarded to the Instrument base class

    Returns:

    TODO(nataliejpg) test filter options
    TODO(nataliejpg) finish implementation of channel b option
    TODO(nataliejpg) validators for int_time and int_delay
    """
    filter_dict = {'win': 0, 'ls': 1}

    def __init__(self, name, alazar_name, filter='win', numtaps=101, chan_b=False, **kwargs):
        self.filter_settings = {'filter': self.filter_dict[filter],
                                'numtaps': numtaps}
        self.chan_b = chan_b
        # self.samples_per_record = 0
        # self.records_per_buffer = 0
        # self.buffers_per_acquisition = 0
        # self.number_of_channels = 2
        # self.samples_delay = 0
        # self.samples_time = 0
        self.cos_list = None
        self.sin_list = None
        self.buffer = None
        self.board_info = None

        super().__init__(name, alazar_name, **kwargs)

        self.add_parameter(name='acquisition',
                           parameter_class=SamplesParam)
        self.add_parameter(name='demodulation_frequency',
                           initial_value=[20e6],
                           parameter_class=ManualParameter)
        self.add_parameter(name='int_time',
                           unit='s',
                           initial_value=None,
                           parameter_class=ManualParameter)
        self.add_parameter(name='int_delay',
                           initial_value=None,
                           parameter_class=ManualParameter)

    # def set_int_time(self, value):
        # alazar = self._get_alazar()
        # sample_rate = alazar.get_sample_rate()
        # samples_per_record = alazar.samples_per_record.get()
        # time_available = samples_per_record / sample_rate
    # def get_int_time(self, value):
        # raise NotImplementedError

    # def int_time_validate(self, value):
    #     oscilations_measured = value * self.demodulation_frequency()
    #     alazar = self._get_alazar()
    #     sample_rate = alazar.get_sample_rate()
    #     samples_per_record = alazar.samples_per_record.get()
    #     total_time = samples_per_record / sample_rate
    #     time_available = total_time - self.int_delay()
    #     oversampling = sample_rate / (2 * self.demodulation_frequency())

    #     if value > total_time:
    #         # logging.warn('int_time set to {} which is longer'
    #         # ' than total time available {}, samples_per_record'
    #         # 'increased to )
    #         raise ValueError('Cannot set int_time to {};'
    #         'greater than total time available {}'
    #         'increase samples_per_record or decrease '
    #         'sampling rate'.format(value, total_time))
    #     elif value > time_available:
    #         raise ValueError('Cannot set int_time to {};'
    #         'greater than total time available - int delay {}'
    #         'increase samples_per_record , decrease '
    #         'sampling rate or decrease delay'.format(value, time_available))
    #     elif oscilations_measured < 10:
    #         logging.warning('{} oscilations measured, recommend at '
    #                         'least 10: decrease sampling rate, take '
    #                         'more samples or increase demodulation '
    #                         'freq'.format(oscilations_measured))
    #     elif oversampling < 1:
    #         logging.warning('oversampling rate is {}, recommend > 1: '
    #                         'increase sampling rate or decrease '
    #                         'demodulation frequency'.format(oversampling))

    # def int_delay_validate(self, value):
    #     alazar = self._get_alazar()
    #     sample_rate = alazar.get_sample_rate()
    #     samples_per_record = alazar.samples_per_record.get()
    #     total_time = samples_per_record / sample_rate
    #     time_available = total_time - self.int_time()
    #     samples_delay_min = self.filter_settings['numtaps'] - 1
    #     int_delay_min = samples_delay_min / sample_rate

    #     if value < time_available:
    #         raise AttributeError('Cannot set int_time to {};'
    #         'greater than total time available - int time {}'
    #         'increase samples_per_record , decrease '
    #         'sampling rate or decrease int_time'.format(value, time_available))
    #     elif value < int_delay_min:
    #         logging.warning(
    #             'delay is less than recommended for filter choice: '
    #             '(expect delay >= {}'.format(int_delay_min))

    def update_filter_settings(self, filter, numtaps):
        """
        Updates the settings of the filter for filtering out
        double frwuency component for demodulation.

        Args:
            filter (str): filter type ('win' or 'ls')
            numtaps (int): numtaps for filter
        """
        self.filter_settings.update({'filter': self.filter_dict[filter],
                                     'numtaps': numtaps})

    def update_acquisition_kwargs(self, **kwargs):
        """
        Updates the kwargs to be used when
        alazar_driver.acquire is called via a get call of the
        acquisition SamplesParam.

        It is also used to set the limits on the selection of
        samples returned (bounded by delay and integration time)
        and update this information in the Samples Parameter.
        """
        alazar = self._get_alazar()
        self.sample_rate = alazar.get_sample_rate()
        self.samples_per_record = kwargs['samples_per_record']
        time_available = self.samples_per_record / self.sample_rate

        if self.int_delay() is None:
            samp_delay = self.numtaps - 1
            self.int_delay(samp_delay / self.sample_rate)
        else:
            self.check_delay(time_available)

        time_available -= self.int_delay()

        if self.int_time() is None:
            self.int_time(time_available)
        else:
            self.check_time(time_available)

        start = self.int_delay()
        stop = self.int_delay() + self.int_time()
        npts = int(self.int_time() * self.sample_rate)

        self.acquisition.acquisition_kwargs.update(**kwargs)
        self.acquisition.update_sweep(start, stop, npts)

    def pre_start_capture(self):
        """
        Called before capture start to update Acquisition Controller with
        alazar acquisition params and set up software wave for demodulation.
        :return:
        """
        alazar = self._get_alazar()
        if self.samples_per_record != alazar.samples_per_record.get():
            raise Exception('acq controller samples per record does not match'
                            ' instrument value, most likely need '
                            'to call update_acquisition_settings')
        if self.sample_rate != alazar.get_sample_rate():
            raise Exception('acq controller sample rate does not match '
                            'instrument value, most likely need '
                            'to call update_acquisition_settings')
        self.records_per_buffer = alazar.records_per_buffer.get()
        self.buffers_per_acquisition = alazar.buffers_per_acquisition.get()
        self.board_info = alazar.get_idn()
        self.buffer = np.zeros(self.samples_per_record *
                               self.records_per_buffer *
                               self.number_of_channels)

        integer_list = np.arange(self.samples_per_record, dtype=np.uint16)
        angle_list = (2 * np.pi * self.demodulation_frequency() /
                      self.sample_rate * integer_list)

        self.cos_list = np.cos(angle_list)
        self.sin_list = np.sin(angle_list)

    def pre_acquire(self):
        pass

    def handle_buffer(self, data):
        """
        Adds data from alazar to buffer (effectively averaging)
        :return:
        """
        self.buffer += data

    def post_acquire(self):
        """
        Processes the data according to ATS9360 settings, splitting into
        records and averaging over them, then applying demodulation fit
        nb: currently only channel A
        :return: samples_magnitude_array, samples_phase_array
        """
        records_per_acquisition = (self.buffers_per_acquisition *
                                   self.records_per_buffer)
        # for ATS9360 samples are arranged in the buffer as follows:
        # S00A, S00B, S01A, S01B...S10A, S10B, S11A, S11B...
        # where SXYZ is record X, sample Y, channel Z.

        # break buffer up into records and averages over them
        recA = np.zeros(self.samples_per_record)
        for i in range(self.records_per_buffer):
            i0 = (i * self.samples_per_record * self.number_of_channels)
            i1 = (i0 + self.samples_per_record * self.number_of_channels)
            recA += self.buffer[i0:i1:self.number_of_channels]
        recordA = np.uint16(recA / records_per_acquisition)

        # do demodulation
        magA, phaseA = self.fit(recordA)

        # same for chan b
        if self.chan_b:
            raise NotImplementedError('chan b code not complete')
            # recordB = np.zeros(self.samples_per_record, dtype=np.uint16)
            # for i in range(self.records_per_buffer):
            #     i0 = (i * self.samples_per_record *
            #           self.number_of_channels + 1)
            #     i1 = (i0 + self.samples_per_record * self.number_of_channels)
            #     recordB += np.uint16(self.buffer[i0:i1:self.number_of_channels] /
            #                          records_per_acquisition)
            # magB, phaseB = self.fit(recordB)

        return magA, phaseA

    def check_delay(self, time_available):
        samples_delay_min = (self.numtaps - 1)
        int_delay_min = samples_delay_min / self.sample_rate
        if self.int_delay() > time_available:
            raise ValueError('int_delay {} is longer than total_time '
                             '{}'.format(self.int_delay(), time_available))
        elif self.int_delay() < int_delay_min:
            logging.warning(
                'delay is less than recommended for filter choice: '
                '(expect delay >= {}'.format(int_delay_min))

    def check_time(self, time_available):
        oscilations_measured = self.int_time() * self.demodulation_frequency()
        oversampling = self.sample_rate / (2 * self.demodulation_frequency())
        if self.int_time() > time_available:
            raise ValueError('int_time {} is longer than total_time - delay'
                             ' = {}'.format(self.int_time(), time_available))
        elif oscilations_measured < 10:
            logging.warning('{} oscilations measured, recommend at '
                            'least 10: decrease sampling rate, take '
                            'more samples or increase demodulation '
                            'freq'.format(oscilations_measured))
        elif oversampling < 1:
            logging.warning('oversampling rate is {}, recommend > 1: '
                            'increase sampling rate or decrease '
                            'demodulation frequency'.format(oversampling))

    def fit(self, rec):
        """
        Applies volts conversion, demodulation fit, low bandpass filter
        and integration limits to samples array
        :return: samples_magnitude_array, samples_phase_array
        """
        # convert rec to volts
        bps = self.board_info['bits_per_sample']
        if bps == 12:
            volt_rec = sample_to_volt_u12(rec, bps)
        else:
            logging.warning('sample to volt conversion does not exist for'
                            ' bps != 12, centered raw samples returned')
            volt_rec = rec - np.mean(rec)

        # multiply with software wave
        re_wave = np.multiply(volt_rec, self.cos_list)
        im_wave = np.multiply(volt_rec, self.sin_list)
        cutoff = self.demodulation_frequency() / 10

        # filter out higher freq component
        if self.filter == 0:
            re_filtered = filter_win(re_wave, cutoff,
                                     self.sample_rate, self.numtaps)
            im_filtered = filter_win(im_wave, cutoff,
                                     self.sample_rate, self.numtaps)
        elif self.filter == 1:
            re_filtered = filter_ls(re_wave, cutoff,
                                    self.sample_rate, self.numtaps)
            im_filtered = filter_ls(im_wave, cutoff,
                                    self.sample_rate, self.numtaps)

        # # apply integration limits
        beginning = int(self.int_delay() * self.sample_rate)
        end = beginning + int(self.int_time() * self.sample_rate)

        re_limited = re_filtered[beginning:end]
        im_limited = im_filtered[beginning:end]

        # convert to magnitude and phase
        complex_num = re_limited + im_limited * 1j
        mag = abs(complex_num)
        phase = np.angle(complex_num, deg=True)

        return mag, phase

    def get_max_total_sample_time(self):
        time_available = self.samples_per_record / self.sample_rate
        return time_available
