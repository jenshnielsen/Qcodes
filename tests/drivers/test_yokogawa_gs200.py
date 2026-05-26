from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from qcodes.instrument_drivers.yokogawa import YokogawaGS200

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope="function", name="gs200")
def _make_gs200() -> "Iterator[YokogawaGS200]":
    gs200 = YokogawaGS200(
        "GS200", address="GPIB0::1::INSTR", pyvisa_sim_file="Yokogawa_GS200.yaml"
    )
    yield gs200

    gs200.close()


def test_basic_init(gs200: YokogawaGS200) -> None:
    idn = gs200.get_idn()
    assert idn["vendor"] == "QCoDeS Yokogawa Mock"


def test_current_raises_in_voltage_mode(gs200: YokogawaGS200) -> None:
    gs200.source_mode("VOLT")

    with pytest.raises(
        ValueError, match="Cannot get/set CURR settings while in VOLT mode"
    ):
        gs200.current_range()

    with pytest.raises(
        ValueError, match="Cannot get/set CURR settings while in VOLT mode"
    ):
        gs200.current(1)


def test_voltage_raises_in_current_mode(gs200: YokogawaGS200) -> None:
    gs200.source_mode("CURR")

    with pytest.raises(
        ValueError, match="Cannot get/set VOLT settings while in CURR mode"
    ):
        gs200.voltage_range()

    with pytest.raises(
        ValueError, match="Cannot get/set VOLT settings while in CURR mode"
    ):
        gs200.voltage(1)


def test_get_parameters_as_components(gs200: YokogawaGS200) -> None:
    assert gs200.get_component("voltage_range") is gs200.voltage_range
    assert gs200.get_component("voltage") is gs200.voltage


class TestSetOutput:
    """Tests for YokogawaGS200._set_output."""

    def test_set_output_voltage_mode(self, gs200: YokogawaGS200) -> None:
        """Test _set_output sends correct SCPI command in voltage mode."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10)
        gs200.range.source = gs200.voltage_range

        with (
            patch.object(gs200.voltage_range, "get", return_value=10),
            patch.object(gs200, "write") as mock_write,
        ):
            gs200._set_output(5.0)
            mock_write.assert_called_once_with(":SOUR:LEV 5.00000e+00")

    def test_set_output_out_of_range_raises(self, gs200: YokogawaGS200) -> None:
        """Test _set_output raises ValueError when output exceeds range."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10.0)
        gs200.range.source = gs200.voltage_range

        with patch.object(gs200.voltage_range, "get", return_value=10.0):
            with pytest.raises(ValueError, match="Desired output level not in range"):
                gs200._set_output(15.0)

    def test_set_output_auto_range_enabled(self, gs200: YokogawaGS200) -> None:
        """Test _set_output with auto_range uses :AUTO suffix in command."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10)
        gs200.range.source = gs200.voltage_range
        gs200.auto_range.cache.set(True)

        with (
            patch.object(gs200.voltage_range, "get", return_value=10),
            patch.object(gs200, "write") as mock_write,
        ):
            gs200._set_output(5.0)
            mock_write.assert_called_once_with(":SOUR:LEV:AUTO 5.00000e+00")

    def test_set_output_auto_range_max_voltage_raises(
        self, gs200: YokogawaGS200
    ) -> None:
        """Test _set_output with auto_range raises when above max 30V."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(30)
        gs200.range.source = gs200.voltage_range
        gs200.auto_range.cache.set(True)

        with patch.object(gs200.voltage_range, "get", return_value=30):
            with pytest.raises(ValueError, match="Desired output level not in range"):
                gs200._set_output(35.0)

    def test_set_output_auto_range_max_current_raises(
        self, gs200: YokogawaGS200
    ) -> None:
        """Test _set_output with auto_range raises when above max 200mA."""
        gs200.source_mode("CURR")
        gs200.current_range.cache.set(200e-3)
        gs200.range.source = gs200.current_range
        gs200.auto_range.cache.set(True)

        with patch.object(gs200.current_range, "get", return_value=200e-3):
            with pytest.raises(ValueError, match="Desired output level not in range"):
                gs200._set_output(0.3)

    def test_set_output_auto_range_within_max_current(
        self, gs200: YokogawaGS200
    ) -> None:
        """Test _set_output with auto_range works within max 200mA."""
        gs200.source_mode("CURR")
        gs200.current_range.cache.set(200e-3)
        gs200.range.source = gs200.current_range
        gs200.auto_range.cache.set(True)

        with (
            patch.object(gs200.current_range, "get", return_value=200e-3),
            patch.object(gs200, "write") as mock_write,
        ):
            gs200._set_output(0.1)
            mock_write.assert_called_once_with(":SOUR:LEV:AUTO 1.00000e-01")


class TestRampSource:
    """Tests for YokogawaGS200._ramp_source."""

    def test_ramp_source_jump_mode(self, gs200: YokogawaGS200) -> None:
        """Test _ramp_source in JUMP mode delegates to _set_output."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10)
        gs200.range.source = gs200.voltage_range
        gs200.ramp_mode("JUMP")

        with patch.object(gs200, "_set_output") as mock_set:
            gs200._ramp_source(5.0)
            mock_set.assert_called_once_with(5.0)

    def test_ramp_source_jump_mode_out_of_range(self, gs200: YokogawaGS200) -> None:
        """Test _ramp_source in JUMP mode propagates ValueError from _set_output."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10.0)
        gs200.range.source = gs200.voltage_range
        gs200.ramp_mode("JUMP")

        with patch.object(gs200.voltage_range, "get", return_value=10.0):
            with pytest.raises(ValueError, match="Desired output level not in range"):
                gs200._ramp_source(15.0)

    def test_ramp_source_software_mode(self, gs200: YokogawaGS200) -> None:
        """Test _ramp_source in SOFTWARE mode sets step/inter_delay then restores."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10)
        gs200.range.source = gs200.voltage_range
        gs200.ramp_mode("SOFTWARE")
        gs200.ramp_rate(1.0)
        gs200.ramp_step(0.5)

        # Set initial output level in cache so we ramp from 0
        gs200.voltage.cache.set(0.0)

        original_step = gs200.output_level.step
        original_inter_delay = gs200.output_level.inter_delay

        with (
            patch.object(gs200.voltage_range, "get", return_value=10),
            patch.object(gs200, "write"),
        ):
            gs200._ramp_source(1.0)

        # Verify step and inter_delay are restored after ramp
        assert gs200.output_level.step == original_step
        assert gs200.output_level.inter_delay == original_inter_delay

    def test_ramp_source_hardware_mode_output_off_raises(
        self, gs200: YokogawaGS200
    ) -> None:
        """Test _ramp_source in HARDWARE mode raises when output is off."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10)
        gs200.range.source = gs200.voltage_range
        gs200.ramp_mode("HARDWARE")
        gs200.ramp_rate(1.0)
        gs200.ramp_step(0.1)
        # Output is off by default in the sim

        with pytest.raises(RuntimeError, match="Need to enable output"):
            gs200._ramp_source(5.0)

    def test_ramp_source_hardware_mode_out_of_range_raises(
        self, gs200: YokogawaGS200
    ) -> None:
        """Test _ramp_source in HARDWARE mode raises when target exceeds range."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10.0)
        gs200.range.source = gs200.voltage_range
        gs200.ramp_mode("HARDWARE")
        gs200.ramp_rate(1.0)
        gs200.ramp_step(0.1)
        # Turn output on
        gs200.on()

        with patch.object(gs200.voltage_range, "get", return_value=10.0):
            with pytest.raises(ValueError, match="Desired output level not in range"):
                gs200._ramp_source(15.0)

    def test_ramp_source_unknown_mode_raises(self, gs200: YokogawaGS200) -> None:
        """Test _ramp_source raises ValueError for unknown ramp mode."""
        gs200.source_mode("VOLT")
        gs200.voltage_range.cache.set(10.0)
        gs200.range.source = gs200.voltage_range
        # Force an invalid ramp_mode by bypassing validation
        gs200.ramp_mode.cache._update_with(value="INVALID", raw_value="INVALID")

        with pytest.raises(ValueError, match="Unknown ramp mode"):
            gs200._ramp_source(5.0)
