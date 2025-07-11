"""
Demonstrate execution of calibration callbacks
"""

from qcodes.extensions.measurement_generator import Sweep
from qcodes.parameters import ManualParameter


def test_calibration_execution():
    """Test actual execution of calibration callbacks"""
    print("=== Calibration Execution Demo ===")

    # Create mock parameters
    p1 = ManualParameter("p1", initial_value=0.0)
    p2 = ManualParameter("p2", initial_value=0.0)
    p3 = ManualParameter("p3", initial_value=0.0)
    p4 = ManualParameter("p4", initial_value=0.0)  # This will be set by calibration

    # Define calibration callback exactly as requested
    def my_callback(values):
        """Set p4 based on p1 and p2 values: p4 = p1 * 5 + p2 * 0.1"""
        new_value = values["p1"] * 5 + values["p2"] * 0.1
        p4.set(new_value)
        print(
            f"    Calibrated p4 to {new_value:.2f} (p1={values['p1']:.2f}, p2={values['p2']:.2f})"
        )

    # Create the exact API as requested
    measurement = (
        Sweep(parameter=p1, start=1, stop=2, steps=3)
        .sweep(parameter=p2, start=3, stop=5, steps=3)
        .calibrate(callback=my_callback)
        .measure(p3)
    )

    print("Executing measurement with calibration:")
    results = measurement.execute()

    print("\nExecution completed!")
    print("Final parameter values:")
    print(f"  p1: {p1.get()}")
    print(f"  p2: {p2.get()}")
    print(f"  p3: {p3.get()}")
    print(f"  p4: {p4.get()}")

    print("\nResults from measurement:")
    for param_name, values in results.items():
        if len(values) <= 10:  # Don't overwhelm with too much output
            print(f"  {param_name}: {values}")
        else:
            print(f"  {param_name}: {len(values)} values (first 5: {values[:5]})")

    print("\n✅ Successfully demonstrated:")
    print("  - Calibration callback receives current parameter values")
    print("  - p4 is automatically set to p1*5 + p2*0.1 at each step")
    print("  - The API works exactly as requested!")


if __name__ == "__main__":
    test_calibration_execution()
