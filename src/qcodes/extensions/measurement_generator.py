"""
QCoDeS Measurement Generator with Builder Pattern API

This module provides a builder pattern interface for constructing complex
measurements in QCoDeS. It allows for intuitive specification of parameter
sweeps and measurements using a fluent API.

Example:
    Sweep(parameter=p1, start=1, stop=2, steps=10).each().sweep(
        parameter=p2, start=3, stop=5, steps=5).measure(p3)

"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

if TYPE_CHECKING:
    from collections.abc import Callable

    from qcodes.parameters import ParameterBase


@dataclass
class MeasurementEvent:
    """Represents a single measurement event (set or get operation)"""

    parameter: ParameterBase | None
    action: str  # 'set', 'get', or 'calibrate'
    value: Any = None  # Value to set (None for get operations)
    callback: Callable[[dict[str, Any]], None] | None = None  # For calibrate actions


@dataclass
class SweepSpecification:
    """Specification for a parameter sweep"""

    parameter: ParameterBase
    start: float
    stop: float
    steps: int

    def get_values(self) -> np.ndarray:
        """Generate the sweep values"""
        return np.linspace(self.start, self.stop, self.steps)


@dataclass
class CalibrationCallback:
    """Specification for a calibration callback that sets derived parameter values"""

    callback: Callable[[dict[str, Any]], None]
    description: str = ""


class MeasurementBuilder(ABC):
    """Abstract base class for measurement builders"""

    @abstractmethod
    def get_events(self) -> list[list[MeasurementEvent]]:
        """Get the list of measurement events to execute"""
        pass

    @abstractmethod
    def execute(self) -> dict[str, Any]:
        """Execute the measurement and return results"""
        pass


class Sweep(MeasurementBuilder):
    """
    Primary sweep builder class that implements the fluent API

    This class allows building complex measurements using method chaining:
    - sweep() for nested sweeps
    - each() for parallelizing sweeps
    - measure() for adding measurement parameters
    """

    def __init__(self, parameter: ParameterBase, start: float, stop: float, steps: int):
        """
        Initialize a sweep

        Args:
            parameter: QCoDeS parameter to sweep
            start: Starting value
            stop: Ending value
            steps: Number of steps

        """
        self._outer_sweep = SweepSpecification(parameter, start, stop, steps)
        self._inner_sweeps: list[SweepSpecification] = []
        self._parallel_sweeps: list[SweepSpecification] = []
        self._measurements: list[ParameterBase] = []
        self._calibration_callbacks: list[CalibrationCallback] = []
        self._in_parallel_mode = False

    def sweep(
        self, parameter: ParameterBase, start: float, stop: float, steps: int
    ) -> Sweep:
        """
        Add an inner sweep (nested loop)

        Args:
            parameter: QCoDeS parameter to sweep
            start: Starting value
            stop: Ending value
            steps: Number of steps

        Returns:
            Self for method chaining

        """
        if self._in_parallel_mode:
            raise ValueError(
                "Cannot add inner sweep when in parallel mode. Call each() to exit parallel mode."
            )

        self._inner_sweeps.append(SweepSpecification(parameter, start, stop, steps))
        return self

    def each(self) -> Sweep:
        """
        Enter parallel mode for the next sweep operations

        In parallel mode, subsequent sweeps will be executed in parallel
        (same iteration count) rather than nested.

        Returns:
            Self for method chaining

        """
        self._in_parallel_mode = True
        return self

    def calibrate(
        self, callback: Callable[[dict[str, Any]], None], description: str = ""
    ) -> Sweep:
        """
        Add a calibration callback that sets derived parameter values

        The callback function receives a dictionary with current parameter values
        and can set other parameters based on those values.

        Args:
            callback: Function that takes dict of parameter_name -> value and sets derived parameters
            description: Optional description of what the calibration does

        Returns:
            Self for method chaining

        Example:
            def my_callback(values):
                p4.set(values['p1'] * 5 + values['p2'] * 0.1)

            Sweep(p1, 0, 1, 10).sweep(p2, 0, 2, 5).calibrate(my_callback).measure(p3)

        """
        self._calibration_callbacks.append(CalibrationCallback(callback, description))
        return self

    def measure(self, *parameters: ParameterBase) -> MeasurementExecutor:
        """
        Add measurement parameters and finalize the measurement definition

        Args:
            *parameters: QCoDeS parameters to measure

        Returns:
            MeasurementExecutor for executing the measurement

        """
        self._measurements.extend(parameters)
        return MeasurementExecutor(self)

    def execute(self) -> dict[str, Any]:
        """
        Execute the measurement

        Returns:
            Dictionary containing measurement results

        """
        events = self.get_events()
        results = {}

        # Initialize result storage based on the events
        for event_list in events:
            for event in event_list:
                if event.parameter is not None and event.parameter.name not in results:
                    results[event.parameter.name] = []

        # Execute each step
        current_values = {}  # Track current parameter values for calibration
        for step_events in events:
            for event in step_events:
                if event.action == "set" and event.parameter is not None:
                    event.parameter.set(event.value)
                    current_values[event.parameter.name] = event.value
                    results[event.parameter.name].append(event.value)
                elif event.action == "get" and event.parameter is not None:
                    value = event.parameter.get()
                    results[event.parameter.name].append(value)
                elif event.action == "calibrate" and event.callback is not None:
                    # Execute calibration callback with current parameter values
                    event.callback(current_values.copy())

        return results

    def get_events(self) -> list[list[MeasurementEvent]]:
        """
        Generate the sequence of measurement events

        Returns:
            List of event lists, where each inner list represents events
            to be executed together

        """
        events = []

        # Handle the case with parallel sweeps
        if self._parallel_sweeps:
            # Verify all parallel sweeps have the same number of steps
            steps_counts = [
                sweep.steps for sweep in [self._outer_sweep, *self._parallel_sweeps]
            ]
            if not all(steps == steps_counts[0] for steps in steps_counts):
                raise ValueError(
                    "All parallel sweeps must have the same number of steps"
                )

            # Generate parallel sweep values
            sweep_values = []
            for sweep in [self._outer_sweep, *self._parallel_sweeps]:
                sweep_values.append(sweep.get_values())

            # Create events for each step
            for step_idx in range(self._outer_sweep.steps):
                step_events = []

                # Set all parallel parameters
                for sweep_idx, sweep in enumerate(
                    [self._outer_sweep, *self._parallel_sweeps]
                ):
                    step_events.append(
                        MeasurementEvent(
                            parameter=sweep.parameter,
                            action="set",
                            value=sweep_values[sweep_idx][step_idx],
                        )
                    )

                # Add calibration events
                for calibration in self._calibration_callbacks:
                    step_events.append(
                        MeasurementEvent(
                            parameter=None,
                            action="calibrate",
                            callback=calibration.callback,
                        )
                    )

                # Add measurement events
                for param in self._measurements:
                    step_events.append(MeasurementEvent(parameter=param, action="get"))

                events.append(step_events)

        # Handle nested sweeps
        elif self._inner_sweeps:
            outer_values = self._outer_sweep.get_values()

            for outer_val in outer_values:
                # Set outer parameter
                events.append(
                    [
                        MeasurementEvent(
                            parameter=self._outer_sweep.parameter,
                            action="set",
                            value=outer_val,
                        )
                    ]
                )

                # Handle inner sweeps (can be multiple levels of nesting)
                inner_events = self._generate_nested_events(self._inner_sweeps, 0)
                events.extend(inner_events)

        # Handle single sweep case
        else:
            outer_values = self._outer_sweep.get_values()

            for outer_val in outer_values:
                step_events = []

                # Set outer parameter
                step_events.append(
                    MeasurementEvent(
                        parameter=self._outer_sweep.parameter,
                        action="set",
                        value=outer_val,
                    )
                )

                # Add calibration events
                for calibration in self._calibration_callbacks:
                    step_events.append(
                        MeasurementEvent(
                            parameter=None,
                            action="calibrate",
                            callback=calibration.callback,
                        )
                    )

                # Add measurement events
                for param in self._measurements:
                    step_events.append(MeasurementEvent(parameter=param, action="get"))

                events.append(step_events)

        return events

    def _generate_nested_events(
        self, sweeps: list[SweepSpecification], depth: int
    ) -> list[list[MeasurementEvent]]:
        """
        Recursively generate events for nested sweeps

        Args:
            sweeps: List of sweep specifications
            depth: Current nesting depth

        Returns:
            List of event lists for the nested structure

        """
        if depth >= len(sweeps):
            # Base case: generate calibration and measurement events
            events = []
            # Add calibration events before measurements
            for calibration in self._calibration_callbacks:
                events.append(
                    MeasurementEvent(
                        parameter=None,
                        action="calibrate",
                        callback=calibration.callback,
                    )
                )
            # Add measurement events
            for param in self._measurements:
                events.append(MeasurementEvent(parameter=param, action="get"))
            return [events] if events else [[]]

        current_sweep = sweeps[depth]
        current_values = current_sweep.get_values()
        all_events = []

        for value in current_values:
            # Set current parameter
            set_event = [
                MeasurementEvent(
                    parameter=current_sweep.parameter, action="set", value=value
                )
            ]
            all_events.append(set_event)

            # Recursively handle deeper levels
            deeper_events = self._generate_nested_events(sweeps, depth + 1)
            all_events.extend(deeper_events)

        return all_events


class ParallelSweep(MeasurementBuilder):
    """
    Builder for parallel sweeps where multiple parameters are swept together
    """

    def __init__(self, sweeps: list[SweepSpecification]):
        """
        Initialize parallel sweep

        Args:
            sweeps: List of sweep specifications to run in parallel

        """
        self._sweeps = sweeps
        self._measurements: list[ParameterBase] = []
        self._calibration_callbacks: list[CalibrationCallback] = []

        # Validate that all sweeps have the same number of steps
        if sweeps:
            steps = sweeps[0].steps
            if not all(sweep.steps == steps for sweep in sweeps):
                raise ValueError(
                    "All parallel sweeps must have the same number of steps"
                )

    def calibrate(
        self, callback: Callable[[dict[str, Any]], None], description: str = ""
    ) -> ParallelSweep:
        """
        Add a calibration callback that sets derived parameter values

        Args:
            callback: Function that takes dict of parameter_name -> value and sets derived parameters
            description: Optional description of what the calibration does

        Returns:
            Self for method chaining

        """
        self._calibration_callbacks.append(CalibrationCallback(callback, description))
        return self

    def measure(self, *parameters: ParameterBase) -> MeasurementExecutor:
        """
        Add measurement parameters

        Args:
            *parameters: Parameters to measure

        Returns:
            MeasurementExecutor for executing the measurement

        """
        self._measurements.extend(parameters)
        return MeasurementExecutor(self)

    def get_events(self) -> list[list[MeasurementEvent]]:
        """Generate parallel sweep events"""
        if not self._sweeps:
            return []

        events = []
        steps = self._sweeps[0].steps

        # Generate values for all sweeps
        all_values = [sweep.get_values() for sweep in self._sweeps]

        for step_idx in range(steps):
            step_events = []

            # Set all parameters in parallel
            for sweep_idx, sweep in enumerate(self._sweeps):
                step_events.append(
                    MeasurementEvent(
                        parameter=sweep.parameter,
                        action="set",
                        value=all_values[sweep_idx][step_idx],
                    )
                )

            # Add calibration events
            for calibration in self._calibration_callbacks:
                step_events.append(
                    MeasurementEvent(
                        parameter=None,
                        action="calibrate",
                        callback=calibration.callback,
                    )
                )

            # Add measurements
            for param in self._measurements:
                step_events.append(MeasurementEvent(parameter=param, action="get"))

            events.append(step_events)

        return events

    def execute(self) -> dict[str, Any]:
        """Execute the parallel sweep"""
        events = self.get_events()
        results = {}

        # Initialize result storage
        for sweep in self._sweeps:
            results[sweep.parameter.name] = []
        for param in self._measurements:
            results[param.name] = []

        # Execute events
        current_values = {}  # Track current parameter values for calibration
        for step_events in events:
            for event in step_events:
                if event.action == "set" and event.parameter is not None:
                    event.parameter.set(event.value)
                    current_values[event.parameter.name] = event.value
                    results[event.parameter.name].append(event.value)
                elif event.action == "get" and event.parameter is not None:
                    value = event.parameter.get()
                    results[event.parameter.name].append(value)
                elif event.action == "calibrate" and event.callback is not None:
                    # Execute calibration callback with current parameter values
                    event.callback(current_values.copy())

        return results


class MeasurementExecutor:
    """
    Executes measurements defined by a MeasurementBuilder
    """

    def __init__(self, builder: MeasurementBuilder):
        """
        Initialize executor

        Args:
            builder: The measurement builder containing the measurement definition

        """
        self._builder = builder

    def get_events(self) -> list[list[MeasurementEvent]]:
        """
        Get the measurement events from the associated builder

        Returns:
            List of event lists from the builder

        """
        return self._builder.get_events()

    def execute(self) -> dict[str, Any]:
        """
        Execute the measurement

        Returns:
            Dictionary containing measurement results

        """
        events = self.get_events()
        results = {}

        # Initialize result storage based on the events
        for event_list in events:
            for event in event_list:
                if event.parameter is not None and event.parameter.name not in results:
                    results[event.parameter.name] = []

        # Execute each step
        current_values = {}  # Track current parameter values for calibration
        for step_events in events:
            for event in step_events:
                if event.action == "set" and event.parameter is not None:
                    event.parameter.set(event.value)
                    current_values[event.parameter.name] = event.value
                    results[event.parameter.name].append(event.value)
                elif event.action == "get" and event.parameter is not None:
                    value = event.parameter.get()
                    results[event.parameter.name].append(value)
                elif event.action == "calibrate" and event.callback is not None:
                    # Execute calibration callback with current parameter values
                    event.callback(current_values.copy())

        return results

    def get_command_list(self) -> list[list[MeasurementEvent]]:
        """
        Get the list of commands that would be executed

        Returns:
            List of event lists representing the measurement sequence

        """
        return self.get_events()


# Convenience functions for creating measurements


def sweep(parameter: ParameterBase, start: float, stop: float, steps: int) -> Sweep:
    """
    Create a new sweep measurement

    Args:
        parameter: QCoDeS parameter to sweep
        start: Starting value
        stop: Ending value
        steps: Number of steps

    Returns:
        Sweep builder for method chaining

    """
    return Sweep(parameter, start, stop, steps)


def create_sweep(
    parameter: ParameterBase, start: float, stop: float, steps: int
) -> SweepSpecification:
    """
    Convenience function to create a sweep specification

    Args:
        parameter: QCoDeS parameter to sweep
        start: Starting value
        stop: Ending value
        steps: Number of steps

    Returns:
        SweepSpecification instance

    """
    return SweepSpecification(parameter, start, stop, steps)


def parallel_sweep(
    *sweep_specs: tuple[ParameterBase, float, float, int],
) -> ParallelSweep:
    """
    Create a parallel sweep measurement

    Args:
        *sweep_specs: Tuples of (parameter, start, stop, steps) for each sweep

    Returns:
        ParallelSweep builder

    """
    sweeps = []
    for param, start, stop, steps in sweep_specs:
        sweeps.append(SweepSpecification(param, start, stop, steps))
    return ParallelSweep(sweeps)


# Extension to handle more complex patterns
class ConditionalMeasurement(MeasurementBuilder):
    """
    Builder for conditional measurements based on parameter values
    """

    def __init__(self, condition: Callable[[dict], bool]):
        """
        Initialize conditional measurement

        Args:
            condition: Function that takes current parameter values and returns bool

        """
        self._condition = condition
        self._measurements: list[ParameterBase] = []
        self._base_builder: MeasurementBuilder | None = None

    def when(self, builder: MeasurementBuilder) -> ConditionalMeasurement:
        """
        Set the base measurement to conditionally execute

        Args:
            builder: The measurement builder to execute when condition is met

        Returns:
            Self for method chaining

        """
        self._base_builder = builder
        return self

    def get_events(self) -> list[list[MeasurementEvent]]:
        """Generate conditional measurement events"""
        if not self._base_builder:
            return []

        # This is a simplified implementation
        # In practice, you'd want to evaluate conditions during execution
        return self._base_builder.get_events()

    def execute(self) -> dict[str, Any]:
        """Execute conditional measurement"""
        if not self._base_builder:
            return {}

        return self._base_builder.execute()
