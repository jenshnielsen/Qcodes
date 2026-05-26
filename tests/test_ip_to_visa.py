"""Tests for the IPToVisa.close method."""

from unittest.mock import MagicMock, patch

import pytest

from qcodes.instrument.ip_to_visa import IPToVisa


@pytest.fixture
def mock_instrument():
    """Create a mock IPToVisa instance with standard sim-backend attributes."""
    inst = MagicMock()
    inst.visa_handle = MagicMock()
    inst.visabackend = "sim"
    inst.resource_manager = MagicMock()
    inst.resource_manager.visalib = MagicMock()
    inst.resource_manager.visalib.sessions = {1: MagicMock()}
    inst.resource_manager.session = 1
    inst.connection = MagicMock()
    inst._short_name = "test_inst"
    return inst


@patch("qcodes.instrument.ip_to_visa.strip_attrs")
class TestCloseVisaHandle:
    """Tests for the visa_handle closing logic."""

    def test_close_calls_visa_handle_close(self, mock_strip_attrs, mock_instrument):
        """close() should call visa_handle.close() when visa_handle exists."""
        IPToVisa.close(mock_instrument)

        mock_instrument.visa_handle.close.assert_called_once()

    def test_close_does_not_call_visa_handle_close_when_none(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should not call visa_handle.close() when visa_handle is None."""
        mock_instrument.visa_handle = None

        IPToVisa.close(mock_instrument)

        # No error raised, and no call attempted on None


@patch("qcodes.instrument.ip_to_visa.strip_attrs")
class TestCloseSimBackend:
    """Tests for the pyvisa-sim reset logic."""

    def test_close_resets_sim_device_when_last_session(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should call visalib._init() when it's the last session."""
        # One session matching the resource_manager's session
        mock_instrument.resource_manager.visalib.sessions = {1: MagicMock()}
        mock_instrument.resource_manager.session = 1

        IPToVisa.close(mock_instrument)

        mock_instrument.resource_manager.visalib._init.assert_called_once()

    def test_close_does_not_reset_sim_when_multiple_sessions(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should NOT call visalib._init() when multiple sessions exist."""
        mock_instrument.resource_manager.visalib.sessions = {
            1: MagicMock(),
            2: MagicMock(),
        }
        mock_instrument.resource_manager.session = 1

        IPToVisa.close(mock_instrument)

        mock_instrument.resource_manager.visalib._init.assert_not_called()

    def test_close_resets_sim_when_zero_sessions(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should call visalib._init() when n_sessions == 0."""
        mock_instrument.resource_manager.visalib.sessions = {}
        mock_instrument.resource_manager.session = 1

        IPToVisa.close(mock_instrument)

        mock_instrument.resource_manager.visalib._init.assert_called_once()

    def test_close_does_not_reset_when_visabackend_is_not_sim(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should NOT call visalib._init() when visabackend != 'sim'."""
        mock_instrument.visabackend = "ivi"

        IPToVisa.close(mock_instrument)

        mock_instrument.resource_manager.visalib._init.assert_not_called()

    def test_close_does_not_reset_when_resource_manager_is_none(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should NOT attempt sim reset when resource_manager is None."""
        mock_instrument.resource_manager = None

        IPToVisa.close(mock_instrument)

        # No AttributeError raised


@patch("qcodes.instrument.ip_to_visa.strip_attrs")
class TestCloseConnection:
    """Tests for the IP connection closing logic."""

    def test_close_calls_connection_close(self, mock_strip_attrs, mock_instrument):
        """close() should call connection.close() when connection has close."""
        IPToVisa.close(mock_instrument)

        mock_instrument.connection.close.assert_called_once()

    def test_close_does_not_fail_when_connection_missing(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should not fail when connection attribute doesn't exist."""
        del mock_instrument.connection

        IPToVisa.close(mock_instrument)

        # No AttributeError raised

    def test_close_does_not_fail_when_connection_has_no_close(
        self, mock_strip_attrs, mock_instrument
    ):
        """close() should not fail when connection doesn't have a close method."""
        # Use a simple object without close
        mock_instrument.connection = object()

        IPToVisa.close(mock_instrument)

        # No AttributeError raised


@patch("qcodes.instrument.ip_to_visa.strip_attrs")
class TestCloseCleanup:
    """Tests for the strip_attrs and remove_instance cleanup logic."""

    def test_close_calls_strip_attrs(self, mock_strip_attrs, mock_instrument):
        """close() should call strip_attrs with the correct whitelist."""
        IPToVisa.close(mock_instrument)

        mock_strip_attrs.assert_called_once_with(
            mock_instrument, whitelist=["_short_name"]
        )

    def test_close_calls_remove_instance(self, mock_strip_attrs, mock_instrument):
        """close() should call remove_instance(self) to deregister."""
        IPToVisa.close(mock_instrument)

        mock_instrument.remove_instance.assert_called_once_with(mock_instrument)
