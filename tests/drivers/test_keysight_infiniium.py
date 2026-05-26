"""
Tests for KeysightInfiniium driver methods _validate_source and _query_capabilities.

These tests use unittest.mock since there is no simulation file for this instrument.
"""

from unittest.mock import MagicMock, call

import pytest
from pyvisa import VisaIOError
from pyvisa.constants import StatusCode

from qcodes.instrument_drivers.Keysight.Infiniium import (
    KeysightInfiniium,
    KeysightInfiniiumUnboundMeasurement,
)

# --- Fixtures ---


@pytest.fixture
def mock_measurement():
    """Create a mock measurement subsystem for _validate_source tests."""
    meas = MagicMock(spec=KeysightInfiniiumUnboundMeasurement)
    meas.root_instrument = MagicMock()
    meas.root_instrument.no_channels = 4
    # Default: channel is on
    meas.ask = MagicMock(return_value="1")
    return meas


@pytest.fixture
def mock_scope():
    """Create a mock scope for _query_capabilities tests."""
    scope = MagicMock(spec=KeysightInfiniium)
    scope._meta_attrs = []
    scope.log = MagicMock()
    scope.ask = MagicMock()
    scope.write = MagicMock()
    return scope


# --- _validate_source tests ---


class TestValidateSource:
    """Tests for KeysightInfiniiumUnboundMeasurement._validate_source."""

    def test_valid_chan_source_on(self, mock_measurement):
        """CHAN source within range and turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "CHAN1"
        )
        assert result == "CHAN1"
        mock_measurement.ask.assert_called_once_with("CHAN1:DISP?")

    def test_valid_chan_source_different_channel(self, mock_measurement):
        """CHAN3 source within range and turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "CHAN3"
        )
        assert result == "CHAN3"
        mock_measurement.ask.assert_called_once_with("CHAN3:DISP?")

    def test_valid_chan_source_off(self, mock_measurement):
        """CHAN source within range but turned off raises ValueError."""
        mock_measurement.ask.return_value = "0"
        with pytest.raises(ValueError, match="Channel 2 not turned on"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "CHAN2"
            )

    def test_chan_source_out_of_range(self, mock_measurement):
        """CHAN source out of range (e.g. CHAN5 with 4 channels) raises ValueError."""
        with pytest.raises(ValueError, match="Invalid measurement source CHAN5"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "CHAN5"
            )

    def test_valid_diff_source_on(self, mock_measurement):
        """DIFF source turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "DIFF1"
        )
        assert result == "DIFF1"
        # DIFF1 -> diff_chan = (1-1)*2+1 = 1
        mock_measurement.ask.assert_called_once_with("CHAN1:DIFF?")

    def test_valid_diff2_source_on(self, mock_measurement):
        """DIFF2 source turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "DIFF2"
        )
        assert result == "DIFF2"
        # DIFF2 -> diff_chan = (2-1)*2+1 = 3
        mock_measurement.ask.assert_called_once_with("CHAN3:DIFF?")

    def test_valid_diff_source_off(self, mock_measurement):
        """DIFF source not turned on raises ValueError."""
        mock_measurement.ask.return_value = "0"
        with pytest.raises(ValueError, match="Differential channel 1 not turned on"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "DIFF1"
            )

    def test_valid_comm_source_on(self, mock_measurement):
        """COMM source turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "COMM1"
        )
        assert result == "COMM1"
        # COMM1 -> diff_chan = (1-1)*2+1 = 1
        mock_measurement.ask.assert_called_once_with("CHAN1:DIFF?")

    def test_valid_comm2_source_on(self, mock_measurement):
        """COMM2 source turned on returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "COMM2"
        )
        assert result == "COMM2"
        # COMM2 -> diff_chan = (2-1)*2+1 = 3
        mock_measurement.ask.assert_called_once_with("CHAN3:DIFF?")

    def test_valid_comm_source_off(self, mock_measurement):
        """COMM source not turned on raises ValueError."""
        mock_measurement.ask.return_value = "0"
        with pytest.raises(ValueError, match="Differential channel 2 not turned on"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "COMM2"
            )

    def test_wmem_source_valid(self, mock_measurement):
        """WMEM source is always valid with no display check."""
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "WMEM1"
        )
        assert result == "WMEM1"
        # No ask calls should be made for WMEM
        mock_measurement.ask.assert_not_called()

    def test_wmem_source_all_valid_numbers(self, mock_measurement):
        """All WMEM[1-4] sources are valid."""
        for i in range(1, 5):
            mock_measurement.ask.reset_mock()
            result = KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, f"WMEM{i}"
            )
            assert result == f"WMEM{i}"
            mock_measurement.ask.assert_not_called()

    def test_func_source_in_range_enabled(self, mock_measurement):
        """FUNC source in range [1-16] and enabled returns the source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "FUNC1"
        )
        assert result == "FUNC1"
        mock_measurement.ask.assert_called_once_with("FUNC1:DISP?")

    def test_func_source_double_digit_enabled(self, mock_measurement):
        """FUNC source with double digits (e.g. FUNC12) and enabled returns source."""
        mock_measurement.ask.return_value = "1"
        result = KeysightInfiniiumUnboundMeasurement._validate_source(
            mock_measurement, "FUNC12"
        )
        assert result == "FUNC12"
        mock_measurement.ask.assert_called_once_with("FUNC12:DISP?")

    def test_func_source_in_range_not_enabled(self, mock_measurement):
        """FUNC source in range but not enabled raises ValueError."""
        mock_measurement.ask.return_value = "0"
        with pytest.raises(ValueError, match="Function 5 is not enabled"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "FUNC5"
            )

    def test_func_source_out_of_range(self, mock_measurement):
        """FUNC source out of range (>16) raises ValueError."""
        with pytest.raises(
            ValueError, match=r"Function number should be in the range 1-16\. Got 19"
        ):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "FUNC19"
            )

    def test_invalid_source_string(self, mock_measurement):
        """Completely invalid source string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid measurement source INVALID"):
            KeysightInfiniiumUnboundMeasurement._validate_source(
                mock_measurement, "INVALID"
            )

    def test_invalid_source_empty_string(self, mock_measurement):
        """Empty source string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid measurement source"):
            KeysightInfiniiumUnboundMeasurement._validate_source(mock_measurement, "")


# --- _query_capabilities tests ---


class TestQueryCapabilities:
    """Tests for KeysightInfiniium._query_capabilities."""

    def test_all_capabilities_parsed_correctly(self, mock_scope):
        """All three capabilities are parsed correctly from valid responses."""
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth
            "1,<numeric>16:100000000",  # memory depth
            "5.0E+09",  # current bandwidth setting for sample rate section
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        assert mock_scope.min_bw == 2.0e7
        assert mock_scope.max_bw == 8.0e9
        assert mock_scope.min_pts == 16
        assert mock_scope.max_pts == 100_000_000
        assert mock_scope.min_srat == 1.0e1
        assert mock_scope.max_srat == 2.0e11
        assert "min_bw" in mock_scope._meta_attrs
        assert "max_bw" in mock_scope._meta_attrs
        assert "min_pts" in mock_scope._meta_attrs
        assert "max_pts" in mock_scope._meta_attrs
        assert "min_srat" in mock_scope._meta_attrs
        assert "max_srat" in mock_scope._meta_attrs

    def test_bandwidth_invalid_format_uses_defaults(self, mock_scope):
        """Invalid bandwidth format logs warning and uses defaults."""
        mock_scope.ask.side_effect = [
            "INVALID_FORMAT",  # bandwidth - invalid
            "1,<numeric>16:100000000",  # memory depth
            "5.0E+09",  # current bandwidth setting
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        assert mock_scope.min_bw == 0.0
        assert mock_scope.max_bw == 99.0e9
        mock_scope.log.warning.assert_any_call(
            "Unable to query bandwidth limits (inv. format (INVALID_FORMAT)). "
            "Setting limits to default."
        )

    def test_bandwidth_visa_error_uses_defaults(self, mock_scope):
        """VisaIOError on bandwidth query logs warning and uses defaults."""
        visa_error = VisaIOError(StatusCode.error_timeout)
        mock_scope.ask.side_effect = [
            visa_error,  # bandwidth - raises
            "1,<numeric>16:100000000",  # memory depth
            "5.0E+09",  # current bandwidth setting
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        # Defaults should still be set from before the exception
        assert mock_scope.min_bw == 0.0
        assert mock_scope.max_bw == 99.0e9
        assert mock_scope.log.warning.called

    def test_memory_depth_invalid_format_uses_defaults(self, mock_scope):
        """Invalid memory depth format logs warning and uses defaults."""
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth - valid
            "BAD_RESPONSE",  # memory depth - invalid
            "5.0E+09",  # current bandwidth setting
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        assert mock_scope.min_pts == 16
        assert mock_scope.max_pts == 1_000_000_000
        mock_scope.log.warning.assert_any_call(
            "Unable to query memory depth (inv. format (BAD_RESPONSE)). "
            "Setting limits to default."
        )

    def test_memory_depth_visa_error_uses_defaults(self, mock_scope):
        """VisaIOError on memory depth query logs warning and uses defaults."""
        visa_error = VisaIOError(StatusCode.error_timeout)
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth - valid
            visa_error,  # memory depth - raises
            "5.0E+09",  # current bandwidth setting
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        assert mock_scope.min_pts == 16
        assert mock_scope.max_pts == 1_000_000_000
        assert mock_scope.log.warning.called

    def test_sample_rate_invalid_format_uses_defaults(self, mock_scope):
        """Invalid sample rate format logs warning and uses defaults."""
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth - valid
            "1,<numeric>16:100000000",  # memory depth - valid
            "5.0E+09",  # current bandwidth setting
            "NOT_VALID",  # sample rate - invalid
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        assert mock_scope.min_srat == 10.0
        assert mock_scope.max_srat == 99.0e9
        mock_scope.log.warning.assert_any_call(
            "Unable to query sample rate (inv. format (NOT_VALID)). "
            "Setting limits to default."
        )

    def test_sample_rate_visa_error_uses_defaults(self, mock_scope):
        """VisaIOError on sample rate query logs warning and uses defaults."""
        visa_error = VisaIOError(StatusCode.error_timeout)
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth - valid
            "1,<numeric>16:100000000",  # memory depth - valid
            visa_error,  # current bandwidth ask raises before defaults are set
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        # The error occurs before min_srat/max_srat are assigned, so they
        # won't be set. Only verify that the warning was logged.
        assert mock_scope.log.warning.called

    def test_bandwidth_set_to_max_triggers_auto(self, mock_scope):
        """When bandwidth is set to max_bw, it is detected as AUTO."""
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth
            "1,<numeric>16:100000000",  # memory depth
            "8.0E+09",  # current bandwidth == max_bw -> AUTO
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        # Should write AUTO to set bandwidth, then restore with "AUTO"
        write_calls = mock_scope.write.call_args_list
        assert call(":ACQ:BAND AUTO") in write_calls
        # Restore should write AUTO since bw_set was detected as AUTO
        assert write_calls[-1] == call(":ACQ:BAND AUTO")

    def test_bandwidth_not_max_restores_original(self, mock_scope):
        """When bandwidth is not max, it is restored to its original numeric value."""
        mock_scope.ask.side_effect = [
            "1,<numeric>2.0E+07:8.0E+09",  # bandwidth
            "1,<numeric>16:100000000",  # memory depth
            "5.0E+09",  # current bandwidth != max_bw
            "1,<numeric>1.0E+01:2.0E+11",  # sample rate
        ]

        KeysightInfiniium._query_capabilities(mock_scope)

        write_calls = mock_scope.write.call_args_list
        # First call sets AUTO for querying sample rate limits
        assert call(":ACQ:BAND AUTO") in write_calls
        # Last call restores the original value
        assert write_calls[-1] == call(":ACQ:BAND 5000000000.0")
