from typing import Dict, Union, Optional
from time import sleep, time
import numpy as np
import ctypes as ct
import logging

from qcodes.instrument.base import Instrument
import qcodes.utils.validators as vals
from qcodes.instrument.parameter import ArrayParameter2, Parameter


from enum import IntEnum
log = logging.getLogger(__name__)


class SignalHound_USB_SA124B(Instrument):
    """
    QCoDeS driver for the SignalHound USB SA124B
    """
    dll_path = 'C:\\Program Files\\Signal Hound\\Spike\\sa_api.dll'

    def __init__(self, name, dll_path=None, **kwargs):
        t0 = time()
        super().__init__(name, **kwargs)

        log.info('Initializing instrument SignalHound USB 124B')
        self.dll = ct.CDLL(dll_path or self.dll_path)
        self.hf = constants

        self.config_synced = False
        self.initialisation_synced = False

        self.add_parameter('frequency',
                           label='Frequency ',
                           unit='Hz',
                           initial_value=5e9,
                           get_cmd=None,
                           parameter_class=TraceParameter,
                           vals=vals.Numbers())
        self.add_parameter('span',
                           label='Span ',
                           unit='Hz',
                           initial_value=.25e6,
                           get_cmd=None,
                           parameter_class=TraceParameter,
                           vals=vals.Numbers())
        self.add_parameter('ref_lvl',
                           label='Reference power ',
                           unit='dBm',
                           initial_value=0,
                           get_cmd=None,
                           parameter_class=TraceParameter,
                           vals=vals.Numbers(max_value=20))
        self.add_parameter('external_reference',
                           get_cmd=None, set_cmd=None,
                           initial_value=False,
                           parameter_class=TraceParameter,
                           vals=vals.Bool())
        self.add_parameter('device_type',
                           get_cmd=self._do_get_device_type)

        self.add_parameter('device_mode',
                           initial_value='sweeping',
                           get_cmd=None,
                           parameter_class=TraceParameter,
                           update_function='initialisation_synced',
                           vals=vals.Anything())

        self.add_parameter('n_avg',
                           get_cmd=None,
                           set_cmd=None,
                           initial_value=1,
                           vals=vals.Ints(1))

        # not implemented, not sure how it is useful.
        # was broken in the old driver anyway
        # self.add_parameter('acquisition_mode',
        #                    get_cmd=None,
        #                    initial_value='average',
        #                    parameter_class=TraceParameter,
        #                    vals=vals.Enum('average', 'min-max'))
        self.add_parameter('scale',
                           get_cmd=None,
                           initial_value='log-scale',
                           parameter_class=TraceParameter,
                           vals=vals.Enum('log-scale', 'lin-scale',
                                          'log-full-scale', 'lin-full-scale'))
        self.add_parameter('running',
                           get_cmd=None, set_cmd=None,
                           initial_value=False,
                           vals=vals.Bool())
        self.add_parameter('decimation',
                           get_cmd=None,
                           initial_value=1,
                           parameter_class=TraceParameter,
                           docstring='Only used in IQ mode',
                           vals=vals.Ints(1, 8))
        self.add_parameter('bandwidth',
                           label='Bandwidth',
                           unit='Hz',
                           initial_value=0,
                           parameter_class=TraceParameter,
                           get_cmd=None,
                           docstring='Only used in IQ mode',
                           vals=vals.Numbers())
        # rbw Resolution bandwidth in Hz. RBW can be arbitrary.
        self.add_parameter('rbw',
                           label='Resolution Bandwidth',
                           unit='Hz',
                           initial_value=1e3,
                           parameter_class=TraceParameter,
                           get_cmd=None,
                           vals=vals.Numbers())
        # vbw Video bandwidth in Hz. VBW must be less than or equal to RBW.
        #  VBW can be arbitrary. For best performance use RBW as the VBW.
        self.add_parameter('vbw',
                           label='Video Bandwidth',
                           unit='Hz',
                           initial_value=1e3,
                           parameter_class=TraceParameter,
                           get_cmd=None,
                           vals=vals.Numbers())

        self.add_parameter('reject_image',
                           label='Reject image',
                           unit='',
                           initial_value=True,
                           parameter_class=TraceParameter,
                           get_cmd=None,
                           vals=vals.Bool())

        self.add_parameter('frequency_axis',
                           label='Frequency',
                           unit='Hz',
                           get_cmd=self._get_freq_axis,
                           set_cmd=False,
                           vals=vals.Arrays(),
                           snapshot_value=False
                           )

        self.add_parameter('freq_sweep',
                           label='Power',
                           unit='depends on mode',
                           get_cmd=self._get_sweep,
                           set_cmd=False,
                           parameter_class=ArrayParameter2,
                           vals=vals.Arrays(),
                           setpoints=(self.frequency_axis,),
                           snapshot_value=False)

        self.openDevice()
        self.device_type()

        t1 = time()
        # poor-man's connect_message. We could overwrite get_idn
        # instead and use connect_message.
        print('Initialized SignalHound in %.2fs' % (t1-t0))

    def openDevice(self):
        log.info('Opening Device')
        self.deviceHandle = ct.c_int(0)
        deviceHandlePnt = ct.pointer(self.deviceHandle)
        ret = self.dll.saOpenDevice(deviceHandlePnt)
        if ret != saStatus.saNoError:
            raise ValueError('Could not open device. Got error: '
                             f'{saStatus(ret).name}')

        self.devOpen = True

    def close(self, preset=False):
        """

        Args:
            preset: If True performs a hardware reset of the device.

        """
        log.info('Closing Device with handle num: '
                 f'{self.deviceHandle.value}')
        if preset is True:
            log.warning('Performing hardware-reset of device!')
            ret = self.dll.saPreset(self.deviceHandle)
            if ret != saStatus.saNoError:
                log.warning('Error performing preset of device: '
                            f'{saStatus(ret).name}')
            log.info(
                f'Preset Device with handle num: {self.deviceHandle.value}')
        else:
            ret = self.dll.saAbort(self.deviceHandle)
            if ret != saStatus.saNoError:
                raise ValueError('Error performing abort: '
                                 f'{saStatus(ret).name}')
            ret = self.dll.saCloseDevice(self.deviceHandle)
            if ret != saStatus.saNoError:
                raise ValueError('Error performing abort: '
                                 f'{saStatus(ret).name}')
            log.info(
                f'Closed Device with handle num: {self.deviceHandle.value}')
        self.devOpen = False
        self.running(False)
        super().close()

    def abort(self):
        log.info('Stopping acquisition')

        err = self.dll.saAbort(self.deviceHandle)
        if err == saStatus.saNoError:
            log.info('Call to abort succeeded.')
            self.running(False)
        elif err == saStatus.saDeviceNotOpenErr:
            raise IOError('Device not open!')
        elif err == saStatus.saDeviceNotConfiguredErr:
            raise IOError('Device was already idle! Did you call abort '
                          'without ever calling initiate()?')
        else:
            raise IOError('Unknown error setting abort! Error = %s' % err)

    def _do_get_device_type(self):
        log.info('Querying device for model information')

        devType = ct.c_uint(0)
        devTypePnt = ct.pointer(devType)

        err = self.dll.saGetDeviceType(self.deviceHandle, devTypePnt)
        if err == saStatus.saNoError:
            pass
        elif err == saStatus.saDeviceNotOpenErr:
            raise IOError('Device not open!')
        elif err == saStatus.saNullPtrErr:
            raise IOError('Null pointer error!')
        else:
            raise IOError('Unknown error setting getDeviceType! '
                          'Error = %s' % err)

        if devType.value == self.hf.saDeviceTypeNone:
            dev = 'No device'
        elif devType.value == self.hf.saDeviceTypeSA44:
            dev = 'sa44'
        elif devType.value == self.hf.saDeviceTypeSA44B:
            dev = 'sa44B'
        elif devType.value == self.hf.saDeviceTypeSA124A:
            dev = 'sa124A'
        elif devType.value == self.hf.saDeviceTypeSA124B:
            dev = 'sa124B'
        else:
            raise ValueError('Unknown device type!')
        return dev

    ########################################################################

    def initialisation(self, flag=0):
        mode = self.get('device_mode')
        modeOpts = {
            'sweeping': self.hf.sa_SWEEPING,
            'real_time': self.hf.sa_REAL_TIME,
            'IQ': self.hf.sa_IQ,  # not implemented
            'idle': self.hf.sa_IDLE  # not implemented
        }
        if mode in modeOpts:
            mode = modeOpts[mode]
        else:
            raise ValueError('Mode must be one of %s. Passed value was %s.' %
                             (modeOpts, mode))
        err = self.dll.saInitiate(self.deviceHandle, mode, flag)

        ###################################
        # Below here only error handling
        ###################################
        if err == saStatus.saNoError:
            self.running(True)
            log.info('Call to initiate succeeded.')
        elif err == saStatus.saDeviceNotOpenErr:
            raise IOError('Device not open!')
        elif err == saStatus.saInvalidParameterErr:
            log.error(
                """
                saInvalidParameterErr!
                In real-time mode, this value may be returned if the span
                limits defined in the API header are broken. Also in
                real-time mode, this error will be returned if the
                resolution bandwidth is outside the limits defined in
                the API header.
                In time-gate analysis mode this error will be returned if
                span limits defined in the API header are broken. Also in
                time gate analysis, this error is returned if the
                bandwidth provided require more samples for processing
                than is allowed in the gate length. To fix this
                increase rbw/vbw.
                """
            )
            raise IOError('The value for mode did not match any known value.')
        elif err == saStatus.saBandwidthErr:
            raise IOError('RBW is larger than your span. (Sweep Mode)!')
        self.check_for_error(err)
        self.initialisation_synced = True
        return

    def QuerySweep(self):
        """
        Queries the sweep for information on the parameters it uses
        """
        if self.config_synced is False or self.initialisation_synced is False:
            raise RuntimeError("Trying to query sweep settings but parameters "
                               "have not been synced to device")
        sweep_len = ct.c_int(0)
        start_freq = ct.c_double(0)
        stepsize = ct.c_double(0)
        err = self.dll.saQuerySweepInfo(self.deviceHandle,
                                        ct.pointer(sweep_len),
                                        ct.pointer(start_freq),
                                        ct.pointer(stepsize))
        if err == saStatus.saNoError:
            pass
        elif err == saStatus.saDeviceNotOpenErr:
            raise IOError('Device not open!')
        elif err == saStatus.saDeviceNotConfiguredErr:
            raise IOError('The device specified is not currently streaming!')
        elif err == saStatus.saNullPtrErr:
            raise IOError('Null pointer error!')
        else:
            raise IOError('Could not query stream got error:'
                          f'{saStatus(err).name}')

        info = [sweep_len.value, start_freq.value, stepsize.value]
        return info

    def _get_freq_axis(self) -> np.ndarray:
        sweep_len, start_freq, stepsize = self.QuerySweep()

        end_freq = start_freq + stepsize*(sweep_len-1)
        freq_points = np.linspace(start_freq, end_freq, sweep_len)
        return freq_points

    def configure(self):
        """
        Configure consists of five parts
            1. Center span configuration (freqs and span)
            2. Acquisition configuration
                lin-scale/log-scale
                avg/max power
            3. Configuring the external 10MHz reference
            4. Configuration of the mode that is being used
            5. Configuration of the tracking generator (not implemented)
                used in VNA mode

        Configure sets the configuration of the instrument using the parameters
        specified in the Qcodes instrument.

        Note that to ensure loading call self.initialisation()
        These two functions are combined in prepare_for_measurement()
        """
        # CenterSpan Configuration
        frequency = self.get('frequency')
        span = self.get('span')
        center = ct.c_double(frequency)
        span = ct.c_double(span)
        log.info('Setting device CenterSpan configuration.')

        err = self.dll.saConfigCenterSpan(self.deviceHandle, center, span)
        self.check_for_error(err)

        # Acquisition configuration
        detectorVals = {
            'min-max': ct.c_uint(self.hf.sa_MIN_MAX),
            'average': ct.c_uint(self.hf.sa_AVERAGE)
        }
        scaleVals = {
            'log-scale': ct.c_uint(self.hf.sa_LOG_SCALE),
            'lin-scale': ct.c_uint(self.hf.sa_LIN_SCALE),
            'log-full-scale': ct.c_uint(self.hf.sa_LOG_FULL_SCALE),
            'lin-full-scale': ct.c_uint(self.hf.sa_LIN_FULL_SCALE)
        }
        if self.scale() in scaleVals:
            scale = scaleVals[self.scale()]
        else:
            raise ValueError('Invalid Scaling mode! Scaling mode must be one '
                             f'of {list(scaleVals.keys())}. '
                             f'Specified scale = {self.scale()}')
        err = self.dll.saConfigAcquisition(self.deviceHandle,
                                           detectorVals['average'], scale)
        self.check_for_error(err)

        # Reference Level configuration
        log.info('Setting device reference level configuration.')
        err = self.dll.saConfigLevel(
            self.deviceHandle, ct.c_double(self.ref_lvl()))
        self.check_for_error(err)

        # External Reference configuration
        if self.external_reference():
            log.info('Setting reference frequency from external source.')
            err = self.dll.saEnableExternalReference(self.deviceHandle)
            self.check_for_error(err)

        if self.device_mode() == 'sweeping':
            # Sweeping Configuration
            reject_var = ct.c_bool(self.reject_image())
            log.info('Setting device Sweeping configuration.')
            err = self.dll.saConfigSweepCoupling(
                self.deviceHandle, ct.c_double(self.get('rbw')),
                ct.c_double(self.get('vbw')), reject_var)
            self.check_for_error(err)
        elif self.device_mode() == 'IQ':
            err = self.dll.saConfigIQ(
                self.deviceHandle, ct.c_int(self.get('decimation')),
                ct.c_double(self.get('bandwidth')))
            self.check_for_error(err)
        # Now we have synced all the parameters to the SA
        self.config_synced = True

    def _get_sweep(self):
        """
        This function performs a sweep over the configured ranges.
        The result of the sweep is returned along with the sweep points

        returns:

        """
        if self.device_mode() != 'sweeping':
            raise RuntimeError("Trying to perform a sweep but "
                               " instrument is not in sweep mode.")
        self.prepare_for_measurement()
        if self.config_synced is False or self.initialisation_synced is False:
            raise RuntimeError("Trying to capture sweep but parameters "
                               "have not been synced to device")
        freq_points = self._get_freq_axis()
        sweep_len = len(freq_points)

        minarr = (ct.c_float * sweep_len)()
        maxarr = (ct.c_float * sweep_len)()
        n_avg = self.n_avg.get()
        datamin = np.zeros(sweep_len, dtype=np.float64)
        for i in range(n_avg):
            sleep(.1)  # Added extra sleep for updating issue
            err = self.dll.saGetSweep_32f(self.deviceHandle, minarr, maxarr)

            if err == saStatus.saNoError:
                pass
            elif err == saStatus.saDeviceNotOpenErr:
                raise IOError('Device not open!')
            elif err == saStatus.saDeviceNotConfiguredErr:
                raise IOError('The device specified is not currently streaming!')
            elif err == saStatus.saNullPtrErr:
                raise IOError('Null pointer error!')
            elif err == saStatus.saInvalidModeErr:
                raise IOError('Invalid mode error!')
            elif err == saStatus.saCompressionWarning:
                raise IOError('Input voltage overload!')
            elif err == saStatus.sCUSBCommErr:
                raise IOError('Error occurred in the USB connection!')
            else:
                raise IOError('Unknown error!')

            # note if used in averaged mode, the only mode currently supported
            # minarr=maxarr
            datamin += np.array([minarr[elem] for elem in range(sweep_len)])
        return datamin / n_avg

    def get_power_at_freq(self, Navg=1):
        """
        Returns the maximum power in a window of 250kHz
        around the specified  frequency.
        The integration window is specified by the VideoBandWidth (set by vbw)
        """
        poweratfreq = 0
        for i in range(Navg):
            data = self.sweep()
            max_power = np.max(data[1][:])
            poweratfreq += max_power
        self.power(poweratfreq / Navg)
        return self.power()

    def prepare_for_measurement(self):
        self.configure()
        self.initialisation()
        return

    def check_for_error(self, err):
        if err != saStatus.saNoError:
            err_msg = saStatus(err).name
            if err > 0:
                print('Warning:', err_msg)
            else:
                raise IOError(err_msg)

    def get_idn(self) -> Dict[str, Optional[Union[str, int]]]:

        output = {}

        output['vendor'] = 'Signal Hound'
        output['model'] = self._do_get_device_type()

        serialnumber = ct.c_int32()
        ret = self.dll.saGetSerialNumber(self.deviceHandle,
                                         ct.pointer(serialnumber))
        if ret != saStatus.saNoError:
            raise RuntimeError(f"Could not get serial number. "
                               f"Error was: {saStatus(ret).name}")
        output['serial'] = serialnumber.value

        fw_version = (ct.c_char*17)()
        # the manual says that this must be at least 16 char
        # but not clear if that includes a termination zero so
        # make it 17 just in case
        ret = self.dll.saGetFirmwareString(self.deviceHandle, fw_version)
        if ret != saStatus.saNoError:
            raise RuntimeError(f"Could not get fw version. "
                               f"Error was: {saStatus(ret).name}")
        output['firmware'] = fw_version.value.decode('ascii')
        return output


class constants:
    SA_MAX_DEVICES = 8

    saDeviceTypeNone = 0
    saDeviceTypeSA44 = 1
    saDeviceTypeSA44B = 2
    saDeviceTypeSA124A = 3
    saDeviceTypeSA124B = 4

    sa44_MIN_FREQ = 1.0
    sa124_MIN_FREQ = 100.0e3
    sa44_MAX_FREQ = 4.4e9
    sa124_MAX_FREQ = 13.0e9
    sa_MIN_SPAN = 1.0
    sa_MAX_REF = 20
    sa_MAX_ATTEN = 3
    sa_MAX_GAIN = 2
    sa_MIN_RBW = 0.1
    sa_MAX_RBW = 6.0e6
    sa_MIN_RT_RBW = 100.0
    sa_MAX_RT_RBW = 10000.0
    sa_MIN_IQ_BANDWIDTH = 100.0
    sa_MAX_IQ_DECIMATION = 128

    sa_IQ_SAMPLE_RATE = 486111.111

    sa_IDLE = -1
    sa_SWEEPING = 0x0
    sa_REAL_TIME = 0x1
    sa_IQ = 0x2
    sa_AUDIO = 0x3
    sa_TG_SWEEP = 0x4

    sa_MIN_MAX = 0x0
    sa_AVERAGE = 0x1

    sa_LOG_SCALE = 0x0
    sa_LIN_SCALE = 0x1
    sa_LOG_FULL_SCALE = 0x2
    sa_LIN_FULL_SCALE = 0x3

    sa_AUTO_ATTEN = -1
    sa_AUTO_GAIN = -1

    sa_LOG_UNITS = 0x0
    sa_VOLT_UNITS = 0x1
    sa_POWER_UNITS = 0x2
    sa_BYPASS = 0x3

    sa_AUDIO_AM = 0x0
    sa_AUDIO_FM = 0x1
    sa_AUDIO_USB = 0x2
    sa_AUDIO_LSB = 0x3
    sa_AUDIO_CW = 0x4

    TG_THRU_0DB = 0x1
    TG_THRU_20DB = 0x2


class saStatus(IntEnum):

    saUnknownErr = -666
    saFrequencyRangeErr = 99
    saInvalidDetectorErr = -95
    saInvalidScaleErr = -94
    saBandwidthErr = -91
    saExternalReferenceNotFound = -89
    # Device specific errors
    saOvenColdErr = -20
    # Data errors
    saInternetErr = -12
    saUSBCommErr = -11
    # General configuration errors
    saTrackingGeneratorNotFound = -10
    saDeviceNotIdleErr = -9
    saDeviceNotFoundErr = -8
    saInvalidModeErr = -7
    saNotConfiguredErr = -6
    saDeviceNotConfiguredErr = -6 # Added because key error raised
    saTooManyDevicesErr = -5
    saInvalidParameterErr = -4
    saDeviceNotOpenErr = -3
    saInvalidDeviceErr = -2
    saNullPtrErr = -1
    # No error
    saNoError = 0
    # Warnings
    saNoCorrections = 1
    saCompressionWarning = 2
    saParameterClamped = 3
    saBandwidthClamped = 4


class TraceParameter(Parameter):
    """
    A parameter that keeps track of if its value has been synced to
    the USB device by calling configure or similar function.
    """
    def __init__(self, *args, update_function='config_synced', **kwargs):
        if update_function is None:
            raise RuntimeError("You must supply an update function to"
                               "the Tracing parameter")
        self._update_function = update_function
        super().__init__(*args, **kwargs)

    def set_raw(self, value):
        setattr(self.instrument, self._update_function, False)
        self._save_val(value, validate=False)
