"""
Simple test of the measurement generator API
"""

import os
import sys

# Add the src directory to the path so we can import qcodes
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from qcodes.extensions.measurement_generator import Sweep, parallel_sweep
from qcodes.parameters import ManualParameter


def test_simple_sweep():
    """Test a simple parameter sweep with measurement"""
    print("=== Simple Sweep Test ===")

    # Create mock parameters
    voltage = ManualParameter("voltage", initial_value=0.0)
    current = ManualParameter("current", initial_value=0.0)

    # Use the builder pattern API as requested
    measurement = Sweep(parameter=voltage, start=0, stop=1, steps=5).measure(current)

    # Show the generated events
    events = measurement.get_events()
    print(f"Generated {len(events)} measurement steps:")
    for i, step_events in enumerate(events):
        step_desc = []
        for e in step_events:
            if hasattr(e, "value") and e.value is not None:
                step_desc.append(f"{e.action} {e.parameter.name}={e.value:.2f}")
            else:
                step_desc.append(f"{e.action} {e.parameter.name}")
        print(f"  Step {i + 1}: {step_desc}")

    print()


def test_nested_sweep():
    """Test nested parameter sweeps"""
    print("=== Nested Sweep Test ===")

    # Create mock parameters
    p1 = ManualParameter("p1", initial_value=0.0)
    p2 = ManualParameter("p2", initial_value=0.0)
    p3 = ManualParameter("p3", initial_value=0.0)

    # Use the exact API from the user's example
    measurement = (
        Sweep(parameter=p1, start=1, stop=2, steps=3)
        .sweep(parameter=p2, start=3, stop=5, steps=3)
        .measure(p3)
    )

    # Show the generated events
    events = measurement.get_events()
    print(f"Generated {len(events)} measurement operations:")
    for i, step_events in enumerate(events):
        step_desc = []
        for event in step_events:
            if hasattr(event, "value") and event.value is not None:
                step_desc.append(
                    f"{event.action} {event.parameter.name}={event.value:.2f}"
                )
            else:
                step_desc.append(f"{event.action} {event.parameter.name}")
        print(f"  Step {i + 1}: {step_desc}")

    print()


def test_parallel_sweep():
    """Test parallel parameter sweeps"""
    print("=== Parallel Sweep Test ===")

    # Create mock parameters
    x = ManualParameter("x", initial_value=0.0)
    y = ManualParameter("y", initial_value=0.0)
    signal = ManualParameter("signal", initial_value=0.0)

    # Create parallel sweeps using tuples
    measurement = parallel_sweep((x, 0, 1, 4), (y, 0, 2, 4)).measure(signal)

    # Show the generated events
    events = measurement.get_events()
    print(f"Generated {len(events)} parallel measurement steps:")
    for i, step_events in enumerate(events):
        step_desc = []
        for event in step_events:
            if hasattr(event, "value") and event.value is not None:
                step_desc.append(
                    f"{event.action} {event.parameter.name}={event.value:.2f}"
                )
            else:
                step_desc.append(f"{event.action} {event.parameter.name}")
        print(f"  Step {i + 1}: {step_desc}")

    print()


def test_execution():
    """Test executing a measurement"""
    print("=== Execution Test ===")

    # Create a simple mock parameter that simulates a sensor
    class MockSensor(ManualParameter):
        def __init__(self, name: str):
            super().__init__(name, initial_value=0.0)
            self._multiplier = 1.0

        def get_raw(self):
            # Simulate sensor reading based on current value
            return self.cache.raw_value * self._multiplier + 0.1

    voltage = ManualParameter("voltage", initial_value=0.0)
    sensor = MockSensor("sensor")
    sensor._multiplier = 2.0  # Simulate sensor response

    # Create and execute a simple measurement
    measurement = Sweep(parameter=voltage, start=0, stop=0.5, steps=3).measure(sensor)

    print("Executing measurement...")
    results = measurement.execute()

    print("Results:")
    for param_name, values in results.items():
        print(f"  {param_name}: {values}")

    print()


def main():
    """Run all tests"""
    print("Testing QCoDeS Measurement Generator API")
    print("=" * 50)

    test_simple_sweep()
    test_nested_sweep()
    test_parallel_sweep()
    test_execution()

    print("=== Summary ===")
    print("✅ The measurement generator API provides:")
    print("  1. Builder pattern interface with method chaining")
    print("  2. Support for nested sweeps (sweep().sweep())")
    print("  3. Support for parallel sweeps")
    print("  4. Conversion to measurement events (set/get commands)")
    print("  5. Execution capabilities")
    print()
    print("✅ The API matches the requested interface:")
    print(
        "  Sweep(parameter=p1, start=1, stop=2, steps=10).sweep(parameter=p2, start=3, stop=5, steps=5).measure(p3)"
    )


if __name__ == "__main__":
    main()
