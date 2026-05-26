"""Tests for the AWG binary file parser module."""

from __future__ import annotations

import struct
from typing import TYPE_CHECKING

import numpy as np
import numpy.testing as npt
import pytest

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

from qcodes.instrument_drivers.tektronix.AWGFileParser import (
    _getendingnumber,
    _parser1,
    _parser2,
    _parser3,
    _unpacker,
    _unwrap,
    parse_awg_file,
)

# ---------------------------------------------------------------------------
# Helper to build binary AWG file records
# ---------------------------------------------------------------------------


def _make_record(name: str, value_bytes: bytes) -> bytes:
    """Build a single binary record: 8-byte header + name + value."""
    name_bytes = name.encode("ascii") + b"\x00"  # null-terminated
    namelen = len(name_bytes)
    valuelen = len(value_bytes)
    header = struct.pack("<II", namelen, valuelen)
    return header + name_bytes + value_bytes


# ===========================================================================
# Tests for _unwrap
# ===========================================================================


class TestUnwrap:
    """Tests for the _unwrap helper function."""

    def test_string_format(self) -> None:
        """Format 's' should decode null-terminated ASCII bytes."""
        bites = b"hello\x00"
        result = _unwrap(bites, "s")
        assert result == "hello"

    def test_string_format_empty(self) -> None:
        """Format 's' with only a null terminator gives empty string."""
        bites = b"\x00"
        result = _unwrap(bites, "s")
        assert result == ""

    def test_short_format(self) -> None:
        """Format 'h' should unpack a little-endian signed short."""
        value = 42
        bites = struct.pack("<h", value)
        result = _unwrap(bites, "h")
        assert result == value

    def test_short_format_negative(self) -> None:
        """Format 'h' handles negative values."""
        value = -1
        bites = struct.pack("<h", value)
        result = _unwrap(bites, "h")
        assert result == value

    def test_double_format(self) -> None:
        """Format 'd' should unpack a little-endian double."""
        value = 3.14159
        bites = struct.pack("<d", value)
        result = _unwrap(bites, "d")
        assert result == pytest.approx(value)

    def test_long_format(self) -> None:
        """Format 'l' should unpack a little-endian signed long (4 bytes)."""
        value = 1024
        bites = struct.pack("<l", value)
        result = _unwrap(bites, "l")
        assert result == value

    def test_ignore_format(self) -> None:
        """Format 'ignore' should return 'Not read' regardless of content."""
        result = _unwrap(b"\x01\x02\x03\x04", "ignore")
        assert result == "Not read"

    def test_multi_value_tuple(self) -> None:
        """A multi-value format string should return a tuple."""
        # "2h" means two signed shorts
        bites = struct.pack("<2h", 10, 20)
        result = _unwrap(bites, "2h")
        assert result == (10, 20)

    def test_eight_unsigned_shorts(self) -> None:
        """Format '8H' (used for WAVEFORM_TIMESTAMP) returns a tuple."""
        values = (2017, 1, 15, 10, 30, 0, 0, 0)
        bites = struct.pack("<8H", *values)
        result = _unwrap(bites, "8H")
        assert result == values


# ===========================================================================
# Tests for _getendingnumber
# ===========================================================================


class TestGetEndingNumber:
    """Tests for the _getendingnumber helper function."""

    def test_single_digit(self) -> None:
        result = _getendingnumber("SEQUENCE_JUMP_3")
        assert result == (3, "SEQUENCE_JUMP_")

    def test_multi_digit(self) -> None:
        result = _getendingnumber("SEQUENCE_JUMP_23")
        assert result == (23, "SEQUENCE_JUMP_")

    def test_large_number(self) -> None:
        result = _getendingnumber("WAVEFORM_NAME_21")
        assert result == (21, "WAVEFORM_NAME_")

    def test_single_char_prefix(self) -> None:
        result = _getendingnumber("X1")
        assert result == (1, "X")

    def test_number_only(self) -> None:
        """A string that is entirely digits."""
        result = _getendingnumber("999")
        assert result == (999, "")

    def test_channel_number(self) -> None:
        """Field names with channel suffixes like OUTPUT_WAVEFORM_NAME_1."""
        result = _getendingnumber("OUTPUT_WAVEFORM_NAME_1")
        assert result == (1, "OUTPUT_WAVEFORM_NAME_")

    def test_waveform_data_field(self) -> None:
        """Waveform data fields like WAVEFORM_DATA_421."""
        result = _getendingnumber("WAVEFORM_DATA_421")
        assert result == (421, "WAVEFORM_DATA_")


# ===========================================================================
# Tests for _unpacker
# ===========================================================================


class TestUnpacker:
    """Tests for the _unpacker function that splits 16-bit values."""

    def test_zero_value(self) -> None:
        """All zeros: waveform at -1.0, markers off."""
        # 0b0000000000000000 -> m2=0, m1=0, wf bits = 0 -> (0 - 2^13)/2^13 = -1
        arr = np.array([0], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        assert wf[0] == pytest.approx(-1.0)
        assert m1[0] == 0.0
        assert m2[0] == 0.0

    def test_max_waveform_value(self) -> None:
        """Maximum waveform bits (all 14 bits set): wf close to +1."""
        # 14 bits all 1 = 0x3FFF = 16383
        # wf = (16383 - 8192) / 8192 = 8191/8192 ≈ 0.99988
        val = 0x3FFF  # bits[2:] all ones, m1=0, m2=0
        arr = np.array([val], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        expected_wf = (16383 - 2**13) / 2**13
        assert wf[0] == pytest.approx(expected_wf)
        assert m1[0] == 0.0
        assert m2[0] == 0.0

    def test_midscale_waveform(self) -> None:
        """Midscale (0x2000 = 8192): wf = 0."""
        val = 0x2000  # bits[2:] = 10000000000000 = 8192
        arr = np.array([val], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        assert wf[0] == pytest.approx(0.0)
        assert m1[0] == 0.0
        assert m2[0] == 0.0

    def test_marker1_only(self) -> None:
        """Bit 14 (second MSB) set means m1=1."""
        # 0b0100000000000000 = 0x4000
        val = 0x4000
        arr = np.array([val], dtype=np.uint16)
        _wf, m1, m2 = _unpacker(arr)
        assert m1[0] == 1.0
        assert m2[0] == 0.0

    def test_marker2_only(self) -> None:
        """Bit 15 (MSB) set means m2=1."""
        # 0b1000000000000000 = 0x8000
        val = 0x8000
        arr = np.array([val], dtype=np.uint16)
        _wf, m1, m2 = _unpacker(arr)
        assert m1[0] == 0.0
        assert m2[0] == 1.0

    def test_both_markers(self) -> None:
        """Both MSB bits set: m1=1, m2=1."""
        # 0b1100000000000000 = 0xC000
        val = 0xC000
        arr = np.array([val], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        assert m1[0] == 1.0
        assert m2[0] == 1.0
        # wf bits are 0 -> wf = -1
        assert wf[0] == pytest.approx(-1.0)

    def test_multiple_samples(self) -> None:
        """Test with an array of multiple samples."""
        # Sample 1: midscale, no markers -> wf=0, m1=0, m2=0
        # Sample 2: midscale + m1 -> wf=0, m1=1, m2=0
        # Sample 3: midscale + m2 -> wf=0, m1=0, m2=1
        arr = np.array([0x2000, 0x6000, 0xA000], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)

        npt.assert_allclose(wf, [0.0, 0.0, 0.0])
        npt.assert_array_equal(m1, [0.0, 1.0, 0.0])
        npt.assert_array_equal(m2, [0.0, 0.0, 1.0])

    def test_output_shapes(self) -> None:
        """All output arrays have the same length as input."""
        arr = np.array([100, 200, 300, 400, 500], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        assert len(wf) == 5
        assert len(m1) == 5
        assert len(m2) == 5

    def test_full_scale_with_markers(self) -> None:
        """Full waveform value with both markers set."""
        # 0b1111111111111111 = 0xFFFF
        # m2=1, m1=1, wf bits = 0x3FFF = 16383
        val = 0xFFFF
        arr = np.array([val], dtype=np.uint16)
        wf, m1, m2 = _unpacker(arr)
        expected_wf = (16383 - 2**13) / 2**13
        assert wf[0] == pytest.approx(expected_wf)
        assert m1[0] == 1.0
        assert m2[0] == 1.0


# ===========================================================================
# Tests for _parser1
# ===========================================================================


class TestParser1:
    """Tests for _parser1 that reads binary AWG files."""

    def _build_minimal_awg_file(self, tmp_path: Path) -> Path:
        """Build a minimal binary AWG file with known content."""
        filepath = tmp_path / "test.awg"

        records = b""

        # Instrument setting: MAGIC (short, value=1)
        records += _make_record("MAGIC", struct.pack("<h", 1))

        # Instrument setting: VERSION (short, value=2)
        records += _make_record("VERSION", struct.pack("<h", 2))

        # Instrument setting: SAMPLING_RATE (double)
        records += _make_record("SAMPLING_RATE", struct.pack("<d", 1.2e9))

        # Waveform records: NAME, TYPE, LENGTH, TIMESTAMP, DATA
        # The parser strips "WAVEFORM_" prefix and looks up fields.
        # Naming convention: WAVEFORM_NAME_21 (number >= 21 after subtracting 20 gives 1)
        wfm_name = b"test_wfm\x00"
        records += _make_record("WAVEFORM_NAME_21", wfm_name)

        # TYPE (short)
        records += _make_record("WAVEFORM_TYPE_21", struct.pack("<h", 1))

        # LENGTH (long, 4 bytes) - 4 samples
        records += _make_record("WAVEFORM_LENGTH_21", struct.pack("<l", 4))

        # TIMESTAMP (8 unsigned shorts)
        ts = struct.pack("<8H", 2020, 6, 15, 12, 0, 0, 0, 0)
        records += _make_record("WAVEFORM_TIMESTAMP_21", ts)

        # DATA: 4 unsigned shorts (16-bit waveform values)
        # midscale values: 0x2000 = 8192
        data = struct.pack("<4H", 0x2000, 0x2000, 0x2000, 0x2000)
        records += _make_record("WAVEFORM_DATA_21", data)

        # Sequence record: SEQUENCE_WAIT_1
        records += _make_record("SEQUENCE_WAIT_1", struct.pack("<h", 1))

        # Sequence record: SEQUENCE_LOOP_1
        records += _make_record("SEQUENCE_LOOP_1", struct.pack("<l", 3))

        # Sequence record: SEQUENCE_JUMP_1
        records += _make_record("SEQUENCE_JUMP_1", struct.pack("<h", 0))

        # Sequence record: SEQUENCE_GOTO_1
        records += _make_record("SEQUENCE_GOTO_1", struct.pack("<h", 0))

        # Sequence record: SEQUENCE_WAVEFORM_NAME_CH_1_1
        records += _make_record("SEQUENCE_WAVEFORM_NAME_CH_1_1", b"test_wfm\x00")

        filepath.write_bytes(records)
        return filepath

    def test_parser1_reads_instrument_settings(self, tmp_path: Path) -> None:
        """Instrument settings should appear in instdict."""
        filepath = self._build_minimal_awg_file(tmp_path)
        instdict, _waveformlist, _sequencelist = _parser1(str(filepath))

        assert instdict["MAGIC"] == 1
        assert instdict["VERSION"] == 2
        assert instdict["SAMPLING_RATE"] == pytest.approx(1.2e9)

    def test_parser1_reads_waveforms(self, tmp_path: Path) -> None:
        """Waveform records should populate the waveformlist."""
        filepath = self._build_minimal_awg_file(tmp_path)
        _instdict, waveformlist, _sequencelist = _parser1(str(filepath))

        # waveformlist is [names_list, values_list]
        assert len(waveformlist) == 2
        assert len(waveformlist[0]) > 0
        assert len(waveformlist[1]) > 0

        # Check the name field is present (number 21 - 20 = 1)
        assert "WAVEFORM_NAME_1" in waveformlist[0]
        name_idx = waveformlist[0].index("WAVEFORM_NAME_1")
        assert waveformlist[1][name_idx] == "test_wfm"

    def test_parser1_reads_waveform_data(self, tmp_path: Path) -> None:
        """Waveform DATA should be unpacked as a tuple of unsigned shorts."""
        filepath = self._build_minimal_awg_file(tmp_path)
        _instdict, waveformlist, _sequencelist = _parser1(str(filepath))

        # Find DATA entry
        assert "WAVEFORM_DATA_1" in waveformlist[0]
        data_idx = waveformlist[0].index("WAVEFORM_DATA_1")
        data_value = waveformlist[1][data_idx]
        # Should be a tuple of 4 values = (8192, 8192, 8192, 8192)
        assert data_value == (0x2000, 0x2000, 0x2000, 0x2000)

    def test_parser1_reads_sequence(self, tmp_path: Path) -> None:
        """Sequence records should populate sequencelist."""
        filepath = self._build_minimal_awg_file(tmp_path)
        _instdict, _waveformlist, sequencelist = _parser1(str(filepath))

        assert len(sequencelist) == 2
        assert "SEQUENCE_WAIT_1" in sequencelist[0]
        assert "SEQUENCE_LOOP_1" in sequencelist[0]
        assert "SEQUENCE_JUMP_1" in sequencelist[0]
        assert "SEQUENCE_GOTO_1" in sequencelist[0]

        wait_idx = sequencelist[0].index("SEQUENCE_WAIT_1")
        assert sequencelist[1][wait_idx] == 1

        loop_idx = sequencelist[0].index("SEQUENCE_LOOP_1")
        assert sequencelist[1][loop_idx] == 3

    def test_parser1_empty_file(self, tmp_path: Path) -> None:
        """An empty file should return empty structures."""
        filepath = tmp_path / "empty.awg"
        filepath.write_bytes(b"")
        instdict, waveformlist, sequencelist = _parser1(str(filepath))

        assert instdict == {}
        assert waveformlist == [[], []]
        assert sequencelist == [[], []]

    def test_parser1_instrument_only(self, tmp_path: Path) -> None:
        """File with only instrument settings, no waveforms or sequences."""
        filepath = tmp_path / "inst_only.awg"
        records = b""
        records += _make_record("MAGIC", struct.pack("<h", 5))
        records += _make_record("VERSION", struct.pack("<h", 1))
        filepath.write_bytes(records)

        instdict, waveformlist, sequencelist = _parser1(str(filepath))
        assert instdict["MAGIC"] == 5
        assert instdict["VERSION"] == 1
        assert waveformlist == [[], []]
        assert sequencelist == [[], []]


# ===========================================================================
# Tests for _parser2
# ===========================================================================


class TestParser2:
    """Tests for _parser2 that converts waveformlist to dict."""

    def test_single_waveform(self) -> None:
        """A single waveform should be parsed into a dict with wfm/m1/m2."""
        # Simulate what _parser1 produces
        # midscale values -> wf = 0
        data = (0x2000, 0x2000, 0x2000)
        waveformlist: list[list[Any]] = [
            ["WAVEFORM_NAME_1", "WAVEFORM_DATA_1"],
            ["my_waveform", data],
        ]

        result = _parser2(waveformlist)

        assert "my_waveform" in result
        assert "wfm" in result["my_waveform"]
        assert "m1" in result["my_waveform"]
        assert "m2" in result["my_waveform"]
        npt.assert_allclose(result["my_waveform"]["wfm"], [0.0, 0.0, 0.0])
        npt.assert_array_equal(result["my_waveform"]["m1"], [0.0, 0.0, 0.0])
        npt.assert_array_equal(result["my_waveform"]["m2"], [0.0, 0.0, 0.0])

    def test_multiple_waveforms(self) -> None:
        """Multiple waveforms should all appear in the output dict."""
        data_a = (0x2000, 0x6000)  # sample 1: wf=0,m1=0,m2=0; sample 2: wf=0,m1=1,m2=0
        data_b = (0xA000, 0xC000)  # sample 1: wf=0,m1=0,m2=1; sample 2: wf=-1,m1=1,m2=1
        waveformlist: list[list[Any]] = [
            [
                "WAVEFORM_NAME_1",
                "WAVEFORM_DATA_1",
                "WAVEFORM_NAME_2",
                "WAVEFORM_DATA_2",
            ],
            ["wave_a", data_a, "wave_b", data_b],
        ]

        result = _parser2(waveformlist)

        assert "wave_a" in result
        assert "wave_b" in result
        # wave_a: second sample has m1=1
        assert result["wave_a"]["m1"][1] == 1.0
        # wave_b: first sample has m2=1
        assert result["wave_b"]["m2"][0] == 1.0

    def test_waveform_with_markers(self) -> None:
        """Verify waveform + marker extraction through _parser2."""
        # 0xE000 = 1110 0000 0000 0000 -> m2=1, m1=1, wf=0x2000=8192 -> wf=0
        data = (0xE000,)
        waveformlist: list[list[Any]] = [
            ["WAVEFORM_NAME_1", "WAVEFORM_DATA_1"],
            ["marker_test", data],
        ]

        result = _parser2(waveformlist)

        assert result["marker_test"]["m1"][0] == 1.0
        assert result["marker_test"]["m2"][0] == 1.0
        assert result["marker_test"]["wfm"][0] == pytest.approx(0.0)

    def test_empty_waveformlist(self) -> None:
        """An empty waveformlist should return an empty dict."""
        waveformlist: list[list[Any]] = [[], []]
        result = _parser2(waveformlist)
        assert result == {}

    def test_non_data_fields_are_skipped(self) -> None:
        """Fields like TYPE and LENGTH that don't contain DATA or NAME are skipped."""
        waveformlist: list[list[Any]] = [
            [
                "WAVEFORM_NAME_1",
                "WAVEFORM_TYPE_1",
                "WAVEFORM_LENGTH_1",
                "WAVEFORM_DATA_1",
            ],
            ["test_wfm", 1, 2, (0x2000, 0x2000)],
        ]

        result = _parser2(waveformlist)
        assert "test_wfm" in result
        assert len(result) == 1


# ===========================================================================
# Tests for _parser3
# ===========================================================================


class TestParser3:
    """Tests for _parser3 that produces the final output tuple."""

    def _make_wfmdict(self) -> dict[str, dict[str, np.ndarray]]:
        """Create a mock wfmdict as produced by _parser2."""
        return {
            "wfm_ch1_elem1": {
                "wfm": np.array([0.0, 0.5, 1.0]),
                "m1": np.array([1.0, 0.0, 0.0]),
                "m2": np.array([0.0, 1.0, 0.0]),
            },
            "wfm_ch1_elem2": {
                "wfm": np.array([0.1, 0.2, 0.3]),
                "m1": np.array([0.0, 0.0, 1.0]),
                "m2": np.array([1.0, 0.0, 0.0]),
            },
            "wfm_ch2_elem1": {
                "wfm": np.array([-1.0, 0.0, 1.0]),
                "m1": np.array([0.0, 0.0, 0.0]),
                "m2": np.array([1.0, 1.0, 1.0]),
            },
            "wfm_ch2_elem2": {
                "wfm": np.array([-0.5, 0.0, 0.5]),
                "m1": np.array([1.0, 1.0, 1.0]),
                "m2": np.array([0.0, 0.0, 0.0]),
            },
        }

    def _make_sequencelist(self) -> list[list[Any]]:
        """Create a mock sequencelist with 2 channels, 2 elements."""
        names = [
            # Element 1
            "SEQUENCE_WAIT_1",
            "SEQUENCE_LOOP_1",
            "SEQUENCE_JUMP_1",
            "SEQUENCE_GOTO_1",
            "SEQUENCE_WAVEFORM_NAME_CH_1_1",
            "SEQUENCE_WAVEFORM_NAME_CH_2_1",
            # Element 2
            "SEQUENCE_WAIT_2",
            "SEQUENCE_LOOP_2",
            "SEQUENCE_JUMP_2",
            "SEQUENCE_GOTO_2",
            "SEQUENCE_WAVEFORM_NAME_CH_1_2",
            "SEQUENCE_WAVEFORM_NAME_CH_2_2",
        ]
        values: list[Any] = [
            # Element 1
            1,  # WAIT
            5,  # LOOP
            0,  # JUMP off
            2,  # GOTO element 2
            "wfm_ch1_elem1",
            "wfm_ch2_elem1",
            # Element 2
            0,  # WAIT
            1,  # LOOP
            -1,  # JUMP next
            0,  # GOTO off
            "wfm_ch1_elem2",
            "wfm_ch2_elem2",
        ]
        return [names, values]

    def test_output_structure(self) -> None:
        """_parser3 returns a tuple of 8 elements."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        result = _parser3(sequencelist, wfmdict)

        assert len(result) == 8
        _wfms, _m1s, _m2s, _nreps, _waits, _gotos, _jumps, _channels = result

    def test_waveforms_per_channel(self) -> None:
        """Waveforms should be grouped by channel."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        wfms, _m1s, _m2s, _nreps, _waits, _gotos, _jumps, _channels = _parser3(
            sequencelist, wfmdict
        )

        # 2 channels
        assert len(wfms) == 2
        # Each channel has 2 elements
        assert len(wfms[0]) == 2
        assert len(wfms[1]) == 2

    def test_waveform_values(self) -> None:
        """Verify actual waveform array values match."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        wfms, _m1s, _m2s, _nreps, _waits, _gotos, _jumps, _channels = _parser3(
            sequencelist, wfmdict
        )

        # Channel 1, element 1
        npt.assert_allclose(wfms[0][0], [0.0, 0.5, 1.0])
        # Channel 2, element 2
        npt.assert_allclose(wfms[1][1], [-0.5, 0.0, 0.5])

    def test_markers(self) -> None:
        """Verify marker arrays are correctly assigned."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        _wfms, m1s, m2s, _nreps, _waits, _gotos, _jumps, _channels = _parser3(
            sequencelist, wfmdict
        )

        # Channel 1, element 1: m1=[1,0,0], m2=[0,1,0]
        npt.assert_array_equal(m1s[0][0], [1.0, 0.0, 0.0])
        npt.assert_array_equal(m2s[0][0], [0.0, 1.0, 0.0])

    def test_sequence_settings(self) -> None:
        """Verify nreps, waits, gotos, jumps."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        _wfms, _m1s, _m2s, nreps, waits, gotos, jumps, _channels = _parser3(
            sequencelist, wfmdict
        )

        assert nreps == [5, 1]
        assert waits == [1, 0]
        assert gotos == [2, 0]
        assert jumps == [0, -1]

    def test_channels(self) -> None:
        """Verify channel numbers are extracted."""
        wfmdict = self._make_wfmdict()
        sequencelist = self._make_sequencelist()
        _wfms, _m1s, _m2s, _nreps, _waits, _gotos, _jumps, channels = _parser3(
            sequencelist, wfmdict
        )

        assert 1 in channels
        assert 2 in channels
        assert len(channels) == 2

    def test_single_channel_single_element(self) -> None:
        """Minimal case: one channel, one sequence element."""
        wfmdict = {
            "only_wfm": {
                "wfm": np.array([0.0]),
                "m1": np.array([1.0]),
                "m2": np.array([0.0]),
            }
        }
        sequencelist: list[list[Any]] = [
            [
                "SEQUENCE_WAIT_1",
                "SEQUENCE_LOOP_1",
                "SEQUENCE_JUMP_1",
                "SEQUENCE_GOTO_1",
                "SEQUENCE_WAVEFORM_NAME_CH_1_1",
            ],
            [0, 1, 0, 0, "only_wfm"],
        ]

        wfms, m1s, _m2s, nreps, _waits, _gotos, _jumps, channels = _parser3(
            sequencelist, wfmdict
        )

        assert len(wfms) == 1
        assert len(wfms[0]) == 1
        npt.assert_array_equal(wfms[0][0], [0.0])
        npt.assert_array_equal(m1s[0][0], [1.0])
        assert nreps == [1]
        assert channels == [1]


# ===========================================================================
# Tests for parse_awg_file (end-to-end)
# ===========================================================================


class TestParseAwgFile:
    """End-to-end tests for parse_awg_file."""

    def _build_complete_awg_file(self, tmp_path: Path) -> Path:
        """Build a complete binary AWG file for end-to-end testing."""
        filepath = tmp_path / "complete.awg"

        records = b""

        # --- Instrument settings ---
        records += _make_record("MAGIC", struct.pack("<h", 1))
        records += _make_record("VERSION", struct.pack("<h", 1))
        records += _make_record("SAMPLING_RATE", struct.pack("<d", 1e9))
        records += _make_record("RUN_MODE", struct.pack("<h", 4))  # Sequence

        # --- Waveform 1 (for channel 1) ---
        records += _make_record("WAVEFORM_NAME_21", b"ch1_wfm\x00")
        records += _make_record("WAVEFORM_TYPE_21", struct.pack("<h", 1))
        records += _make_record("WAVEFORM_LENGTH_21", struct.pack("<l", 3))
        records += _make_record(
            "WAVEFORM_TIMESTAMP_21", struct.pack("<8H", 2021, 3, 1, 0, 0, 0, 0, 0)
        )
        # 3 samples: midscale, midscale+m1, midscale+m2
        records += _make_record(
            "WAVEFORM_DATA_21", struct.pack("<3H", 0x2000, 0x6000, 0xA000)
        )

        # --- Waveform 2 (for channel 2) ---
        records += _make_record("WAVEFORM_NAME_22", b"ch2_wfm\x00")
        records += _make_record("WAVEFORM_TYPE_22", struct.pack("<h", 1))
        records += _make_record("WAVEFORM_LENGTH_22", struct.pack("<l", 3))
        records += _make_record(
            "WAVEFORM_TIMESTAMP_22", struct.pack("<8H", 2021, 3, 1, 0, 0, 0, 0, 0)
        )
        # 3 samples: all zeros (wf=-1), all max (wf≈+1), midscale
        records += _make_record(
            "WAVEFORM_DATA_22", struct.pack("<3H", 0x0000, 0x3FFF, 0x2000)
        )

        # --- Sequence element 1 ---
        records += _make_record("SEQUENCE_WAIT_1", struct.pack("<h", 1))
        records += _make_record("SEQUENCE_LOOP_1", struct.pack("<l", 2))
        records += _make_record("SEQUENCE_JUMP_1", struct.pack("<h", 0))
        records += _make_record("SEQUENCE_GOTO_1", struct.pack("<h", 0))
        records += _make_record("SEQUENCE_WAVEFORM_NAME_CH_1_1", b"ch1_wfm\x00")
        records += _make_record("SEQUENCE_WAVEFORM_NAME_CH_2_1", b"ch2_wfm\x00")

        filepath.write_bytes(records)
        return filepath

    def test_parse_awg_file_returns_tuple_and_dict(self, tmp_path: Path) -> None:
        """parse_awg_file should return (tuple, dict)."""
        filepath = self._build_complete_awg_file(tmp_path)
        result = parse_awg_file(str(filepath))

        assert isinstance(result, tuple)
        assert len(result) == 2
        callsig, instdict = result
        assert isinstance(instdict, dict)
        assert len(callsig) == 8

    def test_parse_awg_file_instrument_settings(self, tmp_path: Path) -> None:
        """Instrument settings should be correctly parsed."""
        filepath = self._build_complete_awg_file(tmp_path)
        _callsig, instdict = parse_awg_file(str(filepath))

        assert instdict["MAGIC"] == 1
        assert instdict["VERSION"] == 1
        assert instdict["SAMPLING_RATE"] == pytest.approx(1e9)
        # RUN_MODE=4 is translated to "Sequence"
        assert instdict["RUN_MODE"] == "Sequence"

    def test_parse_awg_file_waveform_values(self, tmp_path: Path) -> None:
        """Waveform values should be correctly unpacked end-to-end."""
        filepath = self._build_complete_awg_file(tmp_path)
        callsig, _instdict = parse_awg_file(str(filepath))

        wfms, m1s, m2s, _nreps, _waits, _gotos, _jumps, _channels = callsig

        # Channel 1 waveform: midscale -> 0.0 for all 3 samples
        npt.assert_allclose(wfms[0][0], [0.0, 0.0, 0.0])
        # Channel 1 markers: m1=[0,1,0], m2=[0,0,1]
        npt.assert_array_equal(m1s[0][0], [0.0, 1.0, 0.0])
        npt.assert_array_equal(m2s[0][0], [0.0, 0.0, 1.0])

        # Channel 2 waveform: -1, ~+1, 0
        expected_wf2 = [-1.0, (16383 - 8192) / 8192, 0.0]
        npt.assert_allclose(wfms[1][0], expected_wf2)

    def test_parse_awg_file_sequence_settings(self, tmp_path: Path) -> None:
        """Sequence settings are correctly parsed end-to-end."""
        filepath = self._build_complete_awg_file(tmp_path)
        callsig, _instdict = parse_awg_file(str(filepath))

        _wfms, _m1s, _m2s, nreps, waits, gotos, jumps, _channels = callsig

        assert nreps == [2]
        assert waits == [1]
        assert gotos == [0]
        assert jumps == [0]

    def test_parse_awg_file_channels(self, tmp_path: Path) -> None:
        """Channel numbers should be correctly identified."""
        filepath = self._build_complete_awg_file(tmp_path)
        callsig, _instdict = parse_awg_file(str(filepath))

        wfms, _m1s, _m2s, _nreps, _waits, _gotos, _jumps, channels = callsig

        assert sorted(channels) == [1, 2]
        assert len(wfms) == 2

    def test_parse_awg_file_multiple_elements(self, tmp_path: Path) -> None:
        """Test with multiple sequence elements."""
        filepath = tmp_path / "multi_elem.awg"
        records = b""

        # Instrument settings
        records += _make_record("MAGIC", struct.pack("<h", 1))
        records += _make_record("VERSION", struct.pack("<h", 1))
        records += _make_record("SAMPLING_RATE", struct.pack("<d", 1e9))

        # Two waveforms
        records += _make_record("WAVEFORM_NAME_21", b"wfm_a\x00")
        records += _make_record("WAVEFORM_TYPE_21", struct.pack("<h", 1))
        records += _make_record("WAVEFORM_LENGTH_21", struct.pack("<l", 2))
        records += _make_record("WAVEFORM_TIMESTAMP_21", struct.pack("<8H", *([0] * 8)))
        records += _make_record("WAVEFORM_DATA_21", struct.pack("<2H", 0x2000, 0x2000))

        records += _make_record("WAVEFORM_NAME_22", b"wfm_b\x00")
        records += _make_record("WAVEFORM_TYPE_22", struct.pack("<h", 1))
        records += _make_record("WAVEFORM_LENGTH_22", struct.pack("<l", 2))
        records += _make_record("WAVEFORM_TIMESTAMP_22", struct.pack("<8H", *([0] * 8)))
        records += _make_record("WAVEFORM_DATA_22", struct.pack("<2H", 0x3FFF, 0x0000))

        # Sequence element 1 (channel 1)
        records += _make_record("SEQUENCE_WAIT_1", struct.pack("<h", 1))
        records += _make_record("SEQUENCE_LOOP_1", struct.pack("<l", 10))
        records += _make_record("SEQUENCE_JUMP_1", struct.pack("<h", 0))
        records += _make_record("SEQUENCE_GOTO_1", struct.pack("<h", 2))
        records += _make_record("SEQUENCE_WAVEFORM_NAME_CH_1_1", b"wfm_a\x00")

        # Sequence element 2 (channel 1)
        records += _make_record("SEQUENCE_WAIT_2", struct.pack("<h", 0))
        records += _make_record("SEQUENCE_LOOP_2", struct.pack("<l", 1))
        records += _make_record("SEQUENCE_JUMP_2", struct.pack("<h", -1))
        records += _make_record("SEQUENCE_GOTO_2", struct.pack("<h", 0))
        records += _make_record("SEQUENCE_WAVEFORM_NAME_CH_1_2", b"wfm_b\x00")

        filepath.write_bytes(records)

        callsig, _instdict = parse_awg_file(str(filepath))
        wfms, _m1s, _m2s, nreps, waits, gotos, jumps, _channels = callsig

        assert len(wfms) == 1  # 1 channel
        assert len(wfms[0]) == 2  # 2 elements
        assert nreps == [10, 1]
        assert waits == [1, 0]
        assert gotos == [2, 0]
        assert jumps == [0, -1]
        # First wfm: midscale -> 0.0
        npt.assert_allclose(wfms[0][0], [0.0, 0.0])
        # Second wfm: max then min -> ~+1, -1
        expected = [(16383 - 8192) / 8192, -1.0]
        npt.assert_allclose(wfms[0][1], expected)
