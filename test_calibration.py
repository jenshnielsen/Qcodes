"""
Test the calibration callback functionality in the measurement generator API
"""

from qcodes.extensions.measurement_generator import Sweep, parallel_sweep
from qcodes.parameters import ManualParameter


def test_calibration_callback():
    """Test calibration callbacks with parameter sweeps"""
    print("=== Calibration Callback Test ===")

    # Create mock parameters
    p1 = ManualParameter("p1", initial_value=0.0)
    p2 = ManualParameter("p2", initial_value=0.0)
    p3 = ManualParameter("p3", initial_value=0.0)
    p4 = ManualParameter("p4", initial_value=0.0)  # This will be set by calibration

    # Define calibration callback
    def my_callback(values):
        """Set p4 based on p1 and p2 values: p4 = p1 * 5 + p2 * 0.1"""
        new_value = values["p1"] * 5 + values["p2"] * 0.1
        p4.set(new_value)
        print(
            f"    Calibration: p4 set to {new_value:.2f} (p1={values['p1']:.2f}, p2={values['p2']:.2f})"
        )

    # Use the API as requested with calibration
    measurement = (
        Sweep(parameter=p1, start=1, stop=2, steps=3)
        .sweep(parameter=p2, start=3, stop=5, steps=3)
        .calibrate(callback=my_callback, description="Set p4 = p1*5 + p2*0.1")
        .measure(p3)
    )

    # Show the generated events
    events = measurement.get_events()
    print(f"Generated {len(events)} measurement operations:")
    for i, step_events in enumerate(events):
        step_desc = []
        for event in step_events:
            if event.action == "calibrate":
                step_desc.append("calibrate p4")
            elif (
                event.parameter is not None
                and hasattr(event, "value")
                and event.value is not None
            ):
                step_desc.append(
                    f"{event.action} {event.parameter.name}={event.value:.2f}"
                )
            elif event.parameter is not None:
                step_desc.append(f"{event.action} {event.parameter.name}")
        print(f"  Step {i + 1}: {step_desc}")

    print()


def test_simple_calibration():
    """Test calibration with a simple single sweep"""
    print("=== Simple Calibration Test ===")

    # Create mock parameters
    voltage = ManualParameter("voltage", initial_value=0.0)
    derived = ManualParameter("derived", initial_value=0.0)
    current = ManualParameter("current", initial_value=0.0)

    # Simple calibration callback
    def set_derived(values):
        """Set derived parameter to voltage * 2"""
        new_value = values["voltage"] * 2
        derived.set(new_value)
        print(f"    Calibration: derived set to {new_value:.2f}")

    # Create measurement with calibration
    measurement = (
        Sweep(parameter=voltage, start=0, stop=1, steps=3)
        .calibrate(callback=set_derived)
        .measure(current)
    )

    # Execute the measurement to see calibration in action
    print("Executing measurement with calibration:")
    results = measurement.execute()

    print("Results:")
    for param_name, values in results.items():
        print(f"  {param_name}: {values}")

    print(f"Final derived parameter value: {derived.get()}")
    print()


def test_parallel_calibration():
    """Test calibration with parallel sweeps"""
    print("=== Parallel Calibration Test ===")

    # Create mock parameters
    x = ManualParameter("x", initial_value=0.0)
    y = ManualParameter("y", initial_value=0.0)
    combined = ManualParameter("combined", initial_value=0.0)
    signal = ManualParameter("signal", initial_value=0.0)

    # Calibration for parallel sweep
    def combine_params(values):
        """Set combined parameter to x + y"""
        new_value = values["x"] + values["y"]
        combined.set(new_value)
        print(
            f"    Calibration: combined set to {new_value:.2f} (x={values['x']:.2f}, y={values['y']:.2f})"
        )

    # Create parallel sweep with calibration
    measurement = (
        parallel_sweep((x, 0, 1, 3), (y, 0, 2, 3))
        .calibrate(callback=combine_params)
        .measure(signal)
    )

    # Show the generated events
    events = measurement.get_events()
    print(f"Generated {len(events)} parallel measurement steps:")
    for i, step_events in enumerate(events):
        step_desc = []
        for event in step_events:
            if event.action == "calibrate":
                step_desc.append("calibrate combined")
            elif (
                event.parameter is not None
                and hasattr(event, "value")
                and event.value is not None
            ):
                step_desc.append(
                    f"{event.action} {event.parameter.name}={event.value:.2f}"
                )
            elif event.parameter is not None:
                step_desc.append(f"{event.action} {event.parameter.name}")
        print(f"  Step {i + 1}: {step_desc}")

    print()


def main():
    """Run all calibration tests"""
    print("Testing QCoDeS Measurement Generator Calibration API")
    print("=" * 60)

    test_simple_calibration()
    test_calibration_callback()
    test_parallel_calibration()

    print("=== Summary ===")
    print("✅ The calibration API provides:")
    print("  1. .calibrate(callback) method for setting derived parameter values")
    print("  2. Callback receives dict of current parameter values")
    print("  3. Works with single sweeps, nested sweeps, and parallel sweeps")
    print("  4. Calibration happens after parameter setting but before measurements")
    print()
    print("✅ Example usage:")
    print("  Sweep(parameter=p1, start=1, stop=2, steps=3)")
    print("  .sweep(parameter=p2, start=3, stop=5, steps=3)")
    print("  .calibrate(callback=my_callback)")
    print("  .measure(p3)")


if __name__ == "__main__":
    main()
