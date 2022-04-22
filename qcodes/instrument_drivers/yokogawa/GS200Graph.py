from contextlib import contextmanager
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, Iterable, Iterator, Optional

from typing_extensions import Literal

from qcodes.graph.graph import (
    BasicEdgeActivator,
    ConnectionAttributeType,
    Edge,
    EdgeActivator,
    EdgeStatus,
    MutableStationGraph,
    Node,
    NodeActivator,
    NodeId,
    NodeStatus,
)
from qcodes.instrument.channel import InstrumentModule
from qcodes.instrument.visa import VisaInstrument
from qcodes.utils.helpers import create_on_off_val_mapping
from qcodes.utils.validators import Bool, Enum, Ints, Numbers

if TYPE_CHECKING:
    from qcodes.instrument.parameter import Parameter, _BaseParameter

ModeType = Literal["CURR", "VOLT"]


class SourceEdgeActivator(EdgeActivator):
    def __init__(self, status_parameter, active_state: Any):
        self._status_parameter = status_parameter
        self._active_state = active_state

    @property
    def status(self) -> EdgeStatus:
        state = self._status_parameter.cache()
        if state == self._active_state:
            return EdgeStatus.ACTIVE_ELECTRICAL_CONNECTION
        else:
            return EdgeStatus.INACTIVE_ELECTRICAL_CONNECTION

    # todo currently this is done when activating the matching node
    # should it change
    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass


class SourceModuleActivator(NodeActivator):
    def __init__(
        self,
        *,
        node: Node,
        parent: Optional[Node] = None,
        active_state: Any,
        inactive_state: Any,
        status_parameter: "Parameter",
    ):
        super().__init__(node=node)
        self._parent = parent
        self._active_state = active_state
        self._inactive_state = inactive_state
        self._status_parameter = status_parameter

    @property
    def parameters(self) -> Iterable["Parameter"]:
        return []

    def activate(self) -> None:
        self._status_parameter(self._active_state)
        super().activate()

    def deactivate(self) -> None:
        self._status_parameter(self._inactive_state)
        super().deactivate()

    @property
    def status(self) -> NodeStatus:
        if self._status_parameter.cache() == self._active_state:
            return NodeStatus.ACTIVE
        else:
            return NodeStatus.INACTIVE

    def upstream_nodes(self) -> Iterable[Node]:
        return []

    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        return {}


def _float_round(val: float) -> int:
    """
    Rounds a floating number

    Args:
        val: number to be rounded

    Returns:
        Rounded integer
    """
    return round(float(val))


class GS200Exception(Exception):
    pass


class GS200Monitor(InstrumentModule):
    """
    Monitor part of the GS200. This is only enabled if it is
    installed in the GS200 (it is an optional extra).

    Args:
        parent: Instance of GS200 to use as parent
        name: instrument name
        mode: CURR or VOLT. Oposite of the mode set.
    """

    def __init__(self, parent: "Source", name: str, mode: ModeType) -> None:
        super().__init__(parent, name)

        self.add_parameter(
            "enabled",
            label="Measurement Enabled",
            get_cmd=":SENS?",
            set_cmd=":SENS {}",
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
        )

        if mode == "VOLT":
            self.add_parameter(
                "voltage",
                label="Voltage",
                unit="V",
                get_cmd=self._get_measurement,
                snapshot_get=False,
            )
        elif mode == "CURR":
            self.add_parameter(
                "current",
                label="Current",
                unit="I",
                get_cmd=self._get_measurement,
                snapshot_get=False,
            )

        self.add_parameter(
            "NPLC",
            label="NPLC",
            unit="1/LineFreq",
            vals=Ints(1, 25),
            set_cmd=":SENS:NPLC {}",
            set_parser=int,
            get_cmd=":SENS:NPLC?",
            get_parser=_float_round,
        )
        self.add_parameter(
            "delay",
            label="Measurement Delay",
            unit="ms",
            vals=Ints(0, 999999),
            set_cmd=":SENS:DEL {}",
            set_parser=int,
            get_cmd=":SENS:DEL?",
            get_parser=_float_round,
        )
        self.add_parameter(
            "trigger",
            label="Trigger Source",
            set_cmd=":SENS:TRIG {}",
            get_cmd=":SENS:TRIG?",
            val_mapping={
                "READY": "READ",
                "READ": "READ",
                "TIMER": "TIM",
                "TIM": "TIM",
                "COMMUNICATE": "COMM",
                "IMMEDIATE": "IMM",
                "IMM": "IMM",
            },
        )
        self.add_parameter(
            "interval",
            label="Measurement Interval",
            unit="s",
            vals=Numbers(0.1, 3600),
            set_cmd=":SENS:INT {}",
            set_parser=float,
            get_cmd=":SENS:INT?",
            get_parser=float,
        )

    def _get_measurement(self) -> float:
        if self.parent.auto_range.get() or (
            self.root_instrument.source_mode.cache.get() == "VOLT"
            and self.parent.range.cache() < 1
        ):
            # Measurements will not work with autorange, or when
            # range is <1V.
            raise GS200Exception(
                "Measurements will not work when range is <1V "
                "or when in auto range mode."
            )
        if not self.root_instrument.output.cache():
            raise GS200Exception("Output is off.")
        if not self.enabled.cache():
            raise GS200Exception("Measurements are disabled.")
        # If enabled and output is on, then we can perform a measurement.
        return float(self.ask(":MEAS?"))


class GS200Program(InstrumentModule):
    """ """

    def __init__(self, parent: "GS200", name: str) -> None:
        super().__init__(parent, name)
        self._repeat = 1
        self._file_name = None

        self.add_parameter(
            "interval",
            label="the program interval time",
            unit="s",
            vals=Numbers(0.1, 3600.0),
            get_cmd=":PROG:INT?",
            set_cmd=":PROG:INT {}",
        )

        self.add_parameter(
            "slope",
            label="the program slope time",
            unit="s",
            vals=Numbers(0.1, 3600.0),
            get_cmd=":PROG:SLOP?",
            set_cmd=":PROG:SLOP {}",
        )

        self.add_parameter(
            "trigger",
            label="the program trigger",
            get_cmd=":PROG:TRIG?",
            set_cmd=":PROG:TRIG {}",
            vals=Enum("normal", "mend"),
        )

        self.add_parameter(
            "save",
            set_cmd=":PROG:SAVE '{}'",
            docstring="save the program to the system memory " "(.csv file)",
        )

        self.add_parameter(
            "load",
            get_cmd=":PROG:LOAD?",
            set_cmd=":PROG:LOAD '{}'",
            docstring="load the program (.csv file) from the " "system memory",
        )

        self.add_parameter(
            "repeat",
            label="program execution repetition",
            get_cmd=":PROG:REP?",
            set_cmd=":PROG:REP {}",
            val_mapping={"OFF": 0, "ON": 1},
        )
        self.add_parameter(
            "count",
            label="step of the current program",
            get_cmd=":PROG:COUN?",
            set_cmd=":PROG:COUN {}",
            vals=Ints(1, 10000),
        )

        self.add_function(
            "start", call_cmd=":PROG:EDIT:STAR", docstring="start program editing"
        )
        self.add_function(
            "end", call_cmd=":PROG:EDIT:END", docstring="end program editing"
        )
        self.add_function(
            "run",
            call_cmd=":PROG:RUN",
            docstring="run the program",
        )


class Source(InstrumentModule):
    def __init__(self, parent: "GS200", name: str):
        super().__init__(parent, name)
        # The instrument does autoranging by passing a flag when setting voltage/current
        # rather than this being a specific range value. We emulate this using a manual
        # parameter
        self.add_parameter(
            "auto_range",
            label="Auto Range",
            set_cmd=None,
            get_cmd=None,
            initial_cache_value=False,
            vals=Bool(),
        )

    def _set_range(self, mode: ModeType, output_range: float) -> None:
        """
        Update range

        Args:
            mode: "CURR" or "VOLT"
            output_range: Range to set. For voltage, we have the ranges [10e-3,
                100e-3, 1e0, 10e0, 30e0]. For current, we have the ranges [1e-3,
                10e-3, 100e-3, 200e-3]. If auto_range = False, then setting the
                output can only happen if the set value is smaller than the
                present range.
        """
        self._assert_mode(mode)
        output_range = float(output_range)
        self.write(f":SOUR:RANG {output_range}")

    def _get_range(self, mode: ModeType) -> float:
        """
        Query the present range.

        Args:
            mode: "CURR" or "VOLT"

        Returns:
            range: For voltage, we have the ranges [10e-3, 100e-3, 1e0, 10e0,
                30e0]. For current, we have the ranges [1e-3, 10e-3, 100e-3,
                200e-3]. If auto_range = False, then setting the output can only
                happen if the set value is smaller than the present range.
        """
        self._assert_mode(mode)
        return float(self.ask(":SOUR:RANG?"))

    def _get_output(self, mode: ModeType) -> float:
        self._assert_mode(mode)
        return float(self.ask(":SOUR:LEV?"))

    def _set_output(self, mode: ModeType, output_level: float) -> None:
        """
        Set the output of the instrument.

        Args:
            output_level: output level in Volt or Ampere, depending
                on the current mode.
        """
        self._assert_mode(mode)
        auto_enabled = self.auto_range()

        self_range = self.range()

        if not auto_enabled:
            if self_range is None:
                raise RuntimeError(
                    "Trying to set output but not in auto mode and range is unknown."
                )
        else:
            mode = self.root_instrument.source_mode.get_latest()
            if mode == "CURR":
                self_range = 200e-3
            else:
                self_range = 30.0

        # Check we are not trying to set an out of range value
        if self_range is None or abs(output_level) > abs(self_range):
            # Check that the range hasn't changed
            if not auto_enabled:
                if self_range is None:
                    raise RuntimeError(
                        "Trying to set output but not in"
                        " auto mode and range is unknown."
                    )
                # If we are still out of range, raise a value error
                if abs(output_level) > abs(self_range):
                    raise ValueError(
                        f"Desired output level not in range"
                        f" [-{self_range:.3}, {self_range:.3}]"
                    )

        if auto_enabled:
            auto_str = ":AUTO"
        else:
            auto_str = ""
        cmd_str = f":SOUR:LEV{auto_str} {output_level:.5e}"
        self.write(cmd_str)

    def _assert_mode(self, mode: ModeType) -> None:
        """
        Assert that we are in the correct mode to perform an operation.

        Args:
            mode: "CURR" or "VOLT"
        """
        if self.root_instrument.source_mode.get_latest() != mode:
            raise ValueError(
                f"Cannot get/set {mode} settings "
                f"while in {self.root_instrument.source_mode.get_latest()} mode"
            )

    def _ramp_source(
        self, mode: ModeType, ramp_to: float, step: float, delay: float
    ) -> None:
        """
        Ramp the output from the current level to the specified output

        Args:
            mode: Mode to ramp in (CURR or VOLT)
            ramp_to: The ramp target in volts/amps
            step: The ramp steps in volts/ampere
            delay: The time between finishing one step and
                starting another in seconds.
        """

        @contextmanager
        def delay_and_step_set(
            parameter: "_BaseParameter", temp_step: float, temp_delay: float
        ) -> Iterator[None]:
            saved_step = parameter.step
            saved_inter_delay = parameter.inter_delay

            try:
                parameter.step = temp_step
                parameter.inter_delay = temp_delay
                yield
            finally:
                parameter.step = saved_step
                parameter.inter_delay = saved_inter_delay

        if mode == "CURR":
            output_param = self.parameters["current"]
        elif mode == "VOLT":
            output_param = self.parameters["voltage"]
        else:
            raise ValueError(f"Mode must be either 'CURR' or 'VOLT' got {mode}")

        with delay_and_step_set(output_param, step, delay):
            output_param(ramp_to)


class VoltageSource(Source):
    def __init__(self, parent: "GS200", name: str) -> None:
        super().__init__(parent, name)

        # Check if monitor is present, and if so enable measurement
        monitor_present = "/MON" in self.root_instrument.ask("*OPT?")
        if monitor_present:
            measure = GS200Monitor(self, "measure", "CURR")
            self.add_submodule("measure", measure)

        self.add_parameter(
            "range",
            label="Voltage Source Range",
            unit="V",
            get_cmd=partial(self._get_range, "VOLT"),
            set_cmd=partial(self._set_range, "VOLT"),
            vals=Enum(10e-3, 100e-3, 1e0, 10e0, 30e0),
        )

        self.add_parameter(
            "voltage",
            label="Voltage",
            unit="V",
            set_cmd=partial(self._set_output, "VOLT"),
            get_cmd=partial(self._get_output, "VOLT"),
        )

        self._activator: NodeActivator = SourceModuleActivator(
            node=self,
            parent=self.parent,
            active_state="VOLT",
            inactive_state="CURR",
            status_parameter=self.root_instrument.source_mode,
        )

    def ramp_voltage(self, ramp_to: float, step: float, delay: float) -> None:
        """
        Ramp the voltage from the current level to the specified output.

        Args:
            ramp_to: The ramp target in Volt
            step: The ramp steps in Volt
            delay: The time between finishing one step and
                starting another in seconds.
        """
        self._assert_mode("VOLT")
        self._ramp_source("VOLT", ramp_to, step, delay)


class CurrentSource(Source):
    def __init__(self, parent: "GS200", name: str) -> None:
        super().__init__(parent, name)

        # Check if monitor is present, and if so enable measurement
        monitor_present = "/MON" in self.root_instrument.ask("*OPT?")
        if monitor_present:
            measure = GS200Monitor(self, "measure", "VOLT")
            self.add_submodule("measure", measure)

        self.add_parameter(
            "range",
            label="Current Source Range",
            unit="I",
            get_cmd=partial(self._get_range, "CURR"),
            set_cmd=partial(self._set_range, "CURR"),
            vals=Enum(1e-3, 10e-3, 100e-3, 200e-3),
        )

        self.add_parameter(
            "current",
            label="Current",
            unit="I",
            set_cmd=partial(self._set_output, "CURR"),
            get_cmd=partial(self._get_output, "CURR"),
        )

        self._activator: NodeActivator = SourceModuleActivator(
            node=self,
            parent=self.parent,
            active_state="CURR",
            inactive_state="VOLT",
            status_parameter=self.root_instrument.source_mode,
        )

    def ramp_current(self, ramp_to: float, step: float, delay: float) -> None:
        """
        Ramp the current from the current level to the specified output.

        Args:
            ramp_to: The ramp target in Ampere
            step: The ramp steps in Ampere
            delay: The time between finishing one step and starting
                another in seconds.
        """
        self._assert_mode("CURR")
        self._ramp_source("CURR", ramp_to, step, delay)


class GS200(VisaInstrument):
    """
    This is the QCoDeS driver for the Yokogawa GS200 voltage and current source.

    Args:
      name: What this instrument is called locally.
      address: The GPIB or USB address of this instrument
      kwargs: kwargs to be passed to VisaInstrument class
      terminator: read terminator for reads/writes to the instrument.
    """

    def __init__(
        self, name: str, address: str, terminator: str = "\n", **kwargs: Any
    ) -> None:
        super().__init__(name, address, terminator=terminator, **kwargs)

        self.add_parameter(
            "output",
            label="Output State",
            get_cmd="OUTPUT?",
            set_cmd="OUTPUT {}",
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
        )

        self.add_parameter(
            "source_mode",
            label="Source Mode",
            get_cmd=":SOUR:FUNC?",
            set_cmd=self._set_source_mode,
            vals=Enum("VOLT", "CURR"),
        )

        # We need to get the source_mode value here as we cannot rely on the
        # default value that may have been changed before we connect to the
        # instrument (in a previous session or via the frontpanel).
        self.source_mode()

        self.add_parameter(
            "voltage_limit",
            label="Voltage Protection Limit",
            unit="V",
            vals=Ints(1, 30),
            get_cmd=":SOUR:PROT:VOLT?",
            set_cmd=":SOUR:PROT:VOLT {}",
            get_parser=_float_round,
            set_parser=int,
        )

        self.add_parameter(
            "current_limit",
            label="Current Protection Limit",
            unit="I",
            vals=Numbers(1e-3, 200e-3),
            get_cmd=":SOUR:PROT:CURR?",
            set_cmd=":SOUR:PROT:CURR {:.3f}",
            get_parser=float,
            set_parser=float,
        )

        self.add_parameter(
            "four_wire",
            label="Four Wire Sensing",
            get_cmd=":SENS:REM?",
            set_cmd=":SENS:REM {}",
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
        )

        # Note: The guard feature can be used to remove common mode noise.
        # Read the manual to see if you would like to use it
        self.add_parameter(
            "guard",
            label="Guard Terminal",
            get_cmd=":SENS:GUAR?",
            set_cmd=":SENS:GUAR {}",
            val_mapping=create_on_off_val_mapping(on_val=1, off_val=0),
        )

        # Return measured line frequency
        self.add_parameter(
            "line_freq",
            label="Line Frequency",
            unit="Hz",
            get_cmd="SYST:LFR?",
            get_parser=int,
        )

        # Reset function
        self.add_function("reset", call_cmd="*RST")

        self.add_submodule("program", GS200Program(self, "program"))
        self.add_submodule("current_source", CurrentSource(self, "current_source"))
        self.add_submodule("voltage_source", VoltageSource(self, "voltage_source"))

        self.add_parameter(
            "BNC_out",
            label="BNC trigger out",
            get_cmd=":ROUT:BNCO?",
            set_cmd=":ROUT:BNCO {}",
            vals=Enum("trigger", "output", "ready"),
            docstring="Sets or queries the output BNC signal",
        )

        self.add_parameter(
            "BNC_in",
            label="BNC trigger in",
            get_cmd=":ROUT:BNCI?",
            set_cmd=":ROUT:BNCI {}",
            vals=Enum("trigger", "output"),
            docstring="Sets or queries the input BNC signal",
        )

        self.add_parameter(
            "system_errors",
            get_cmd=":SYSTem:ERRor?",
            docstring="returns the oldest unread error message from the event "
            "log and removes it from the log.",
        )

        self.connect_message()

    def _set_source_mode(self, mode: ModeType) -> None:
        """
        Set output mode and TODO handle activating/deactivating relevant modules
        # TODO invalidate cache when switching mode

        Args:
            mode: "CURR" or "VOLT"

        """
        if self.output() == "on":
            raise GS200Exception("Cannot switch mode while source is on")

        self.write(f"SOUR:FUNC {mode}")

    def _make_instrument_graph(self) -> "StationGraph":
        subgraph_primary_node_names = []
        self_graph = MutableStationGraph()
        self_graph[self.full_name] = self
        subgraphs = [self_graph]
        for submodule in self.instrument_modules.values():
            subgraph = submodule._make_graph()
            subgraph_primary_node_names.append(submodule.full_name)
            subgraphs.append(subgraph)

        graph = MutableStationGraph.compose(*subgraphs)

        for name in subgraph_primary_node_names:
            print(name)
            if "current_source" in name:
                activator = SourceEdgeActivator(
                    status_parameter=self.source_mode, active_state="CURR"
                )
            elif "voltage_source" in name:
                activator = SourceEdgeActivator(
                    status_parameter=self.source_mode, active_state="VOLT"
                )
            else:
                activator = BasicEdgeActivator(edge_status=EdgeStatus.PART_OF)

            graph[self.full_name, name] = Edge(activator=activator)

        return graph.as_station_graph()
