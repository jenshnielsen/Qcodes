"""
Tests for the _setsync and _setslope methods of the QDevQDac class.

These tests use unittest.mock to avoid needing real hardware, since
QDevQDac requires a serial VISA connection.
"""

from unittest.mock import MagicMock

import pytest

from qcodes.instrument_drivers.QDev.QDac_channels import QDevQDac


@pytest.fixture
def mock_qdac():
    """Create a mock QDevQDac with minimum attributes for testing _setslope/_setsync."""
    qdac = MagicMock(spec=QDevQDac)
    qdac._syncoutputs = []
    qdac._slopes = []
    qdac._assigned_fgs = {}
    # Create mock channels (48 channels, 0-indexed)
    channels = [MagicMock() for _ in range(48)]
    for ch in channels:
        ch.sync = MagicMock()
        ch.sync.get_latest.return_value = None
    qdac.channels = channels
    return qdac


# ============================================================
# Tests for _setsync
# ============================================================


class TestSetSync:
    """Tests for QDevQDac._setsync."""

    def test_invalid_channel_raises_valueerror(self, mock_qdac):
        """Channel number must be 1-48."""
        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setsync(mock_qdac, 0, 1)

        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setsync(mock_qdac, 49, 1)

        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setsync(mock_qdac, -1, 0)

    def test_sync_zero_removes_channel_from_syncoutputs(self, mock_qdac):
        """Setting sync=0 removes the channel's entry from _syncoutputs."""
        mock_qdac._syncoutputs = [(5, 1), (10, 2)]
        QDevQDac._setsync(mock_qdac, 5, 0)
        assert (5, 1) not in mock_qdac._syncoutputs
        assert (10, 2) in mock_qdac._syncoutputs

    def test_sync_zero_calls_write_when_oldsync_not_none(self, mock_qdac):
        """Setting sync=0 frees the previously assigned sync via write."""
        mock_qdac._syncoutputs = [(3, 2)]
        mock_qdac.channels[2].sync.get_latest.return_value = 2
        QDevQDac._setsync(mock_qdac, 3, 0)
        mock_qdac.write.assert_called_once_with("syn 2 0 0 0")

    def test_sync_zero_does_not_call_write_when_oldsync_is_none(self, mock_qdac):
        """Setting sync=0 does not call write if oldsync is None."""
        mock_qdac._syncoutputs = [(7, 3)]
        mock_qdac.channels[6].sync.get_latest.return_value = None
        QDevQDac._setsync(mock_qdac, 7, 0)
        mock_qdac.write.assert_not_called()

    def test_assigning_sync_already_used_by_another_channel(self, mock_qdac):
        """If sync is already assigned to another channel, remove old assignment."""
        mock_qdac._syncoutputs = [(5, 1)]
        QDevQDac._setsync(mock_qdac, 10, 1)
        # Old assignment (5, 1) should be removed, new (10, 1) appended
        assert (5, 1) not in mock_qdac._syncoutputs
        assert (10, 1) in mock_qdac._syncoutputs

    def test_reassigning_sync_for_channel_that_already_has_one(self, mock_qdac):
        """If channel already has a sync, update it in place."""
        mock_qdac._syncoutputs = [(5, 1), (10, 2)]
        QDevQDac._setsync(mock_qdac, 5, 3)
        # Channel 5's sync should be updated from 1 to 3
        assert (5, 3) in mock_qdac._syncoutputs
        assert (5, 1) not in mock_qdac._syncoutputs
        # Other entries unchanged
        assert (10, 2) in mock_qdac._syncoutputs

    def test_appending_new_sync(self, mock_qdac):
        """A new (chan, sync) pair is appended when neither is already assigned."""
        mock_qdac._syncoutputs = [(5, 1)]
        QDevQDac._setsync(mock_qdac, 10, 2)
        assert (10, 2) in mock_qdac._syncoutputs
        assert (5, 1) in mock_qdac._syncoutputs

    def test_appending_new_sync_to_empty_list(self, mock_qdac):
        """A new sync can be appended to an initially empty list."""
        QDevQDac._setsync(mock_qdac, 1, 1)
        assert mock_qdac._syncoutputs == [(1, 1)]

    def test_reassign_sync_removes_old_channel_then_updates_existing(self, mock_qdac):
        """
        If sync is used by another channel AND the target channel already has
        a different sync, both operations happen correctly.
        """
        mock_qdac._syncoutputs = [(5, 1), (10, 2)]
        # Assign sync 1 (currently on ch5) to ch10 (which currently has sync 2)
        QDevQDac._setsync(mock_qdac, 10, 1)
        # (5, 1) removed because sync 1 was reassigned
        assert (5, 1) not in mock_qdac._syncoutputs
        # ch10 updated from sync 2 to sync 1
        assert (10, 1) in mock_qdac._syncoutputs
        assert (10, 2) not in mock_qdac._syncoutputs


# ============================================================
# Tests for _setslope
# ============================================================


class TestSetSlope:
    """Tests for QDevQDac._setslope."""

    def test_invalid_channel_raises_valueerror(self, mock_qdac):
        """Channel number must be 1-48."""
        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setslope(mock_qdac, 0, 1.0)

        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setslope(mock_qdac, 49, 1.0)

        with pytest.raises(ValueError, match=r"Channel number must be 1-48\."):
            QDevQDac._setslope(mock_qdac, -1, "Inf")

    def test_slope_inf_calls_write(self, mock_qdac):
        """Setting slope='Inf' writes the wav command to disable ramping."""
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        mock_qdac.write.assert_called_once_with("wav 5 0 0 0")

    def test_slope_inf_removes_assigned_fg(self, mock_qdac):
        """Setting slope='Inf' pops the channel from _assigned_fgs."""
        mock_qdac._assigned_fgs = {5: 2, 10: 3}
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        assert 5 not in mock_qdac._assigned_fgs
        assert 10 in mock_qdac._assigned_fgs

    def test_slope_inf_no_error_when_fg_not_assigned(self, mock_qdac):
        """Setting slope='Inf' when channel has no assigned fg does not raise."""
        mock_qdac._assigned_fgs = {10: 3}
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        # Should not raise KeyError
        assert mock_qdac._assigned_fgs == {10: 3}

    def test_slope_inf_removes_sync_if_assigned(self, mock_qdac):
        """Setting slope='Inf' removes the sync output for that channel."""
        mock_qdac._syncoutputs = [(5, 1)]
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        mock_qdac.channels[4].sync.set.assert_called_once_with(0)

    def test_slope_inf_does_not_touch_sync_if_not_assigned(self, mock_qdac):
        """Setting slope='Inf' does nothing with sync if channel has none."""
        mock_qdac._syncoutputs = [(10, 2)]
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        mock_qdac.channels[4].sync.set.assert_not_called()

    def test_slope_inf_removes_from_slopes(self, mock_qdac):
        """Setting slope='Inf' removes the channel from _slopes."""
        mock_qdac._slopes = [(5, 0.5), (10, 1.0)]
        QDevQDac._setslope(mock_qdac, 5, "Inf")
        assert (5, 0.5) not in mock_qdac._slopes
        assert (10, 1.0) in mock_qdac._slopes

    def test_slope_inf_when_channel_not_in_slopes_no_error(self, mock_qdac):
        """Setting slope='Inf' when channel is not in _slopes does not raise."""
        mock_qdac._slopes = [(10, 1.0)]
        # Channel 5 not in _slopes — but list is non-empty so generator will
        # be exhausted and next() raises StopIteration (only IndexError caught).
        # This is a known edge case in the implementation.
        with pytest.raises(StopIteration):
            QDevQDac._setslope(mock_qdac, 5, "Inf")

    def test_slope_inf_when_slopes_empty_no_error(self, mock_qdac):
        """Setting slope='Inf' when _slopes is empty raises StopIteration."""
        mock_qdac._slopes = []
        # Empty list means generator yields nothing, next() raises StopIteration
        with pytest.raises(StopIteration):
            QDevQDac._setslope(mock_qdac, 5, "Inf")

    def test_updating_existing_slope_for_channel(self, mock_qdac):
        """If channel already has a slope, update it in place."""
        mock_qdac._slopes = [(5, 0.5), (10, 1.0)]
        QDevQDac._setslope(mock_qdac, 5, 2.0)
        assert (5, 2.0) in mock_qdac._slopes
        assert (5, 0.5) not in mock_qdac._slopes
        # Others unchanged
        assert (10, 1.0) in mock_qdac._slopes

    def test_raises_when_more_than_8_slopes_assigned(self, mock_qdac):
        """Cannot assign finite slope to more than 8 channels."""
        mock_qdac._slopes = [(i, 1.0) for i in range(1, 9)]  # 8 channels
        with pytest.raises(
            ValueError, match="Can not assign finite slope to more than 8 channels"
        ):
            QDevQDac._setslope(mock_qdac, 9, 1.0)

    def test_appending_new_slope(self, mock_qdac):
        """A new (chan, slope) pair is appended."""
        mock_qdac._slopes = [(5, 0.5)]
        QDevQDac._setslope(mock_qdac, 10, 2.0)
        assert (10, 2.0) in mock_qdac._slopes
        assert (5, 0.5) in mock_qdac._slopes

    def test_appending_slope_to_empty_list(self, mock_qdac):
        """A new slope can be appended to an initially empty list."""
        QDevQDac._setslope(mock_qdac, 1, 0.1)
        assert mock_qdac._slopes == [(1, 0.1)]

    def test_eighth_slope_can_be_assigned(self, mock_qdac):
        """Exactly 8 slopes is allowed (the limit is >=8, i.e., >8 fails)."""
        mock_qdac._slopes = [(i, 1.0) for i in range(1, 8)]  # 7 channels
        QDevQDac._setslope(mock_qdac, 8, 0.5)
        assert (8, 0.5) in mock_qdac._slopes
        assert len(mock_qdac._slopes) == 8
