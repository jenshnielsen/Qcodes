from unittest.mock import MagicMock

import hypothesis.strategies as st
import numpy as np
import pytest
from hypothesis import HealthCheck, given, settings

from qcodes.instrument_drivers.Keithley import Keithley7510
from qcodes.instrument_drivers.Keithley.Keithley_7510 import (
    DataArray7510,
    Keithley7510Buffer,
    Keithley7510DigitizeSense,
)


@pytest.fixture(scope="function")
def dmm_7510_driver():
    inst = Keithley7510(
        "Keithley_7510_sim",
        address="GPIB::1::INSTR",
        pyvisa_sim_file="keithley_7510.yaml",
    )

    try:
        yield inst
    finally:
        inst.close()


def test_get_idn(dmm_7510_driver) -> None:
    assert dmm_7510_driver.IDN() == {
        "vendor": "KEITHLEY INSTRUMENTS",
        "model": "DMM7510",
        "serial": "01234567",
        "firmware": "1.2.3a",
    }


def test_change_sense_function(dmm_7510_driver) -> None:
    """
    Measurement should be the same as the sense function, e.g., only voltage
    measurement is allowed when the sense function is "voltage".
    """
    assert dmm_7510_driver.sense.function() == "voltage"
    with pytest.raises(AttributeError, match="no attribute 'current'"):
        dmm_7510_driver.sense.current()
    dmm_7510_driver.sense.function("current")
    assert dmm_7510_driver.sense.function() == "current"


@settings(deadline=None, suppress_health_check=(HealthCheck.function_scoped_fixture,))
@given(st.sampled_from((0.1, 1, 10, 100, 1000)), st.floats(0.01, 10))
def test_set_range_and_nplc(dmm_7510_driver, upper_limit, nplc) -> None:
    """
    Test the ability of setting range and nplc value for sense function.
    "Voltage" is used as an example.
    """
    dmm_7510_driver.sense.function("voltage")
    dmm_7510_driver.sense.range(upper_limit)
    assert dmm_7510_driver.sense.range() == upper_limit
    dmm_7510_driver.sense.nplc(nplc)
    assert dmm_7510_driver.sense.nplc() == nplc


# --- Tests for Keithley7510Buffer._get_data ---


@pytest.fixture
def mock_buffer():
    """Create a mock Keithley7510Buffer for testing _get_data."""
    parent = MagicMock()
    parent.digi_sense_function.return_value = "None"
    parent.sense_function.return_value = "voltage"

    buf = MagicMock()
    buf.parent = parent
    buf.short_name = "defbuffer1"
    buf.data_start.return_value = 1
    buf.data_end.return_value = 5
    buf.elements.return_value = []
    buf.n_pts.return_value = 5
    buf.setpoints = MagicMock()
    buf.setpoints.return_value = np.linspace(0, 1, 5)
    buf.setpoints.unit = "s"
    buf.setpoints.label = "time"
    buf.t_start = MagicMock()
    buf.t_stop = MagicMock()
    buf.set_setpoints = MagicMock()
    buf.buffer_elements = Keithley7510Buffer.buffer_elements
    buf.ask = MagicMock(return_value="1.0,2.0,3.0,4.0,5.0")
    return buf


def test_get_data_no_elements(mock_buffer) -> None:
    """Test _get_data with no elements selected (defaults to 'measurement')."""
    result = Keithley7510Buffer._get_data(mock_buffer)

    assert isinstance(result, DataArray7510)
    assert result.names == ("measurement",)
    assert result.units == ("V",)
    assert result.shapes == ((5,),)
    assert hasattr(result, "measurement")
    assert result.measurement == (1.0, 2.0, 3.0, 4.0, 5.0)
    mock_buffer.ask.assert_called_once_with(":TRACe:DATA? 1, 5, 'defbuffer1'")


def test_get_data_with_elements(mock_buffer) -> None:
    """Test _get_data with specific elements selected."""
    mock_buffer.elements.return_value = ["measurement", "relative_time"]
    mock_buffer.ask.return_value = "1.0,0.0,2.0,0.2,3.0,0.4,4.0,0.6,5.0,0.8"

    result = Keithley7510Buffer._get_data(mock_buffer)

    assert result.names == ("measurement", "relative_time")
    assert result.units == ("V", "s")
    assert result.shapes == ((5,), (5,))
    assert result.measurement == (1.0, 2.0, 3.0, 4.0, 5.0)
    assert result.relative_time == (0.0, 0.2, 0.4, 0.6, 0.8)
    mock_buffer.ask.assert_called_once_with(
        ":TRACe:DATA? 1, 5, 'defbuffer1', READing,RELative"
    )


def test_get_data_with_string_elements(mock_buffer) -> None:
    """Test _get_data with string-type elements mixed with numeric."""
    mock_buffer.elements.return_value = ["date", "measurement"]
    mock_buffer.ask.return_value = (
        "2023-01-01,1.5,2023-01-02,2.5,2023-01-03,3.5,2023-01-04,4.5,2023-01-05,5.5"
    )

    result = Keithley7510Buffer._get_data(mock_buffer)

    assert result.names == ("date", "measurement")
    assert result.units == ("str", "V")
    # String elements should be stored as-is (numpy string arrays -> tuples)
    assert result.date == (
        "2023-01-01",
        "2023-01-02",
        "2023-01-03",
        "2023-01-04",
        "2023-01-05",
    )
    assert result.measurement == (1.5, 2.5, 3.5, 4.5, 5.5)


def test_get_data_setpoints_not_implemented(mock_buffer) -> None:
    """Test _get_data falls back to t_start/t_stop when setpoints raises."""
    call_count = 0

    def setpoints_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise NotImplementedError
        return np.linspace(0, 1, 5)

    mock_buffer.setpoints.side_effect = setpoints_side_effect
    # After set_setpoints is called, setpoints should work on subsequent calls
    mock_buffer.setpoints.unit = "s"
    mock_buffer.setpoints.label = "time"

    result = Keithley7510Buffer._get_data(mock_buffer)

    mock_buffer.set_setpoints.assert_called_once_with(
        mock_buffer.t_start, mock_buffer.t_stop
    )
    assert isinstance(result, DataArray7510)


def test_get_data_digitize_sense_function(mock_buffer) -> None:
    """Test _get_data when digitize sense function is active."""
    mock_buffer.parent.digi_sense_function.return_value = "voltage"
    mock_buffer.ask.return_value = "0.5,1.0,1.5,2.0,2.5"

    result = Keithley7510Buffer._get_data(mock_buffer)

    # Should use DigitizeSense function_modes for unit
    expected_unit = Keithley7510DigitizeSense.function_modes["voltage"]["unit"]
    assert result.units == (expected_unit,)
    assert result.names == ("measurement",)
    assert result.measurement == (0.5, 1.0, 1.5, 2.0, 2.5)


def test_get_data_digitize_sense_current(mock_buffer) -> None:
    """Test _get_data with digitize sense function set to current."""
    mock_buffer.parent.digi_sense_function.return_value = "current"
    mock_buffer.ask.return_value = "0.001,0.002,0.003,0.004,0.005"

    result = Keithley7510Buffer._get_data(mock_buffer)

    expected_unit = Keithley7510DigitizeSense.function_modes["current"]["unit"]
    assert result.units == (expected_unit,)
    assert result.measurement == (0.001, 0.002, 0.003, 0.004, 0.005)


def test_get_data_correct_shapes_and_setpoint_metadata(mock_buffer) -> None:
    """Test that the returned DataArray7510 has correct shapes, setpoint info."""
    mock_buffer.elements.return_value = ["measurement", "seconds"]
    mock_buffer.ask.return_value = "1.0,0.0,2.0,0.5,3.0,1.0,4.0,1.5,5.0,2.0"

    result = Keithley7510Buffer._get_data(mock_buffer)

    assert result.shapes == ((5,), (5,))
    assert result.setpoint_units == (("s",), ("s",))
    assert result.setpoint_names == (("time",), ("time",))
    # setpoints should be duplicated for each element
    assert len(result.setpoints) == 2
    np.testing.assert_array_equal(result.setpoints[0][0], np.linspace(0, 1, 5))
    np.testing.assert_array_equal(result.setpoints[1][0], np.linspace(0, 1, 5))


def test_get_data_ask_command_without_elements(mock_buffer) -> None:
    """Verify the SCPI ask command format when no elements are selected."""
    mock_buffer.data_start.return_value = 3
    mock_buffer.data_end.return_value = 7
    mock_buffer.n_pts.return_value = 5
    mock_buffer.ask.return_value = "1.0,2.0,3.0,4.0,5.0"

    Keithley7510Buffer._get_data(mock_buffer)

    mock_buffer.ask.assert_called_once_with(":TRACe:DATA? 3, 7, 'defbuffer1'")


def test_get_data_ask_command_with_elements(mock_buffer) -> None:
    """Verify the SCPI ask command format when elements are selected."""
    mock_buffer.elements.return_value = ["seconds", "measurement_status"]
    mock_buffer.data_start.return_value = 2
    mock_buffer.data_end.return_value = 4
    mock_buffer.n_pts.return_value = 3
    mock_buffer.ask.return_value = "0.1,0,0.2,0,0.3,0"

    Keithley7510Buffer._get_data(mock_buffer)

    mock_buffer.ask.assert_called_once_with(
        ":TRACe:DATA? 2, 4, 'defbuffer1', SEConds,STATus"
    )
