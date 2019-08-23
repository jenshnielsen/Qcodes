"""Set up the main qcodes namespace."""

# flake8: noqa (we don't need the "<...> imported but unused" error)

# config

from qcodes.config import Config
from qcodes.utils.helpers import add_to_spyder_UMR_excludelist
from .version import __version__

# we dont want spyder to reload qcodes as this will overwrite the default station
# instrument list and running monitor
add_to_spyder_UMR_excludelist('qcodes')
config: Config = Config()

from qcodes.version import __version__

from qcodes.station import Station

haswebsockets = True
try:
    import websockets
except ImportError:
    haswebsockets = False
if haswebsockets:
    from qcodes.monitor.monitor import Monitor

from qcodes.instrument.base import Instrument, find_or_create_instrument
from qcodes.instrument.ip import IPInstrument
from qcodes.instrument.visa import VisaInstrument
from qcodes.instrument.channel import InstrumentChannel, ChannelList

from qcodes.instrument.function import Function
from qcodes.instrument.parameter import (
    Parameter,
    ArrayParameter,
    MultiParameter,
    ParameterWithSetpoints,
    DelegateParameter,
    StandardParameter,
    ManualParameter,
    ScaledParameter,
    combine,
    CombinedParameter)

from qcodes.utils import validators
from qcodes.utils.zmq_helpers import Publisher
from qcodes.instrument_drivers.test import test_instruments, test_instrument

from qcodes.dataset.measurements import Measurement
from qcodes.dataset.data_set import new_data_set, load_by_counter, load_by_id, load_by_run_spec, load_by_guid
from qcodes.dataset.experiment_container import new_experiment, load_experiment, load_experiment_by_name, \
    load_last_experiment, experiments, load_or_create_experiment
from qcodes.dataset.sqlite.settings import SQLiteSettings
from qcodes.dataset.descriptions.param_spec import ParamSpec
from qcodes.dataset.sqlite.database import initialise_database, \
    initialise_or_create_database_at

import logging

# ensure to close all instruments when interpreter is closed
import atexit
atexit.register(Instrument.close_all)
atexit.register(logging.shutdown)


def test(**kwargs):
    """
    Run QCoDeS tests. This requires the test requirements given
    in test_requirements.txt to be installed.
    All arguments are forwarded to pytest.main
    """
    try:
        import pytest
    except ImportError:
        print("Need pytest to run tests")
        return
    args = ['--pyargs', 'qcodes.tests']
    retcode = pytest.main(args, **kwargs)
    return retcode


test.__test__ = False  # type: ignore # Don't try to run this method as a test
