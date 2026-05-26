import numpy as np

from qcodes.dataset.data_set import DataSet
from qcodes.parameters import ParamSpecBase


class TestFinalizeResDictStandalones:
    """Tests for DataSet._finalize_res_dict_standalones static method."""

    def test_single_numeric_scalar(self):
        """A single numeric scalar parameter produces one dict with a float."""
        param = ParamSpecBase("voltage", "numeric")
        result_dict = {param: np.array(3.14)}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"voltage": 3.14}]
        assert isinstance(res[0]["voltage"], float)

    def test_single_numeric_array(self):
        """A single numeric array parameter produces one dict per element."""
        param = ParamSpecBase("current", "numeric")
        values = np.array([1.0, 2.0, 3.0])
        result_dict = {param: values}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"current": 1.0}, {"current": 2.0}, {"current": 3.0}]

    def test_single_text_scalar(self):
        """A single text scalar parameter produces one dict with a string."""
        param = ParamSpecBase("label", "text")
        result_dict = {param: np.array("hello")}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"label": "hello"}]
        assert isinstance(res[0]["label"], str)

    def test_single_text_array(self):
        """A single text array parameter produces one dict per stringified element."""
        param = ParamSpecBase("names", "text")
        values = np.array(["alice", "bob", "charlie"])
        result_dict = {param: values}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [
            {"names": "alice"},
            {"names": "bob"},
            {"names": "charlie"},
        ]
        for item in res:
            assert isinstance(item["names"], str)

    def test_single_complex_scalar(self):
        """A single complex scalar parameter produces one dict with a complex value."""
        param = ParamSpecBase("impedance", "complex")
        result_dict = {param: np.array(1 + 2j)}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"impedance": complex(1 + 2j)}]
        assert isinstance(res[0]["impedance"], complex)

    def test_single_complex_array(self):
        """A single complex array parameter produces one dict per element."""
        param = ParamSpecBase("signal", "complex")
        values = np.array([1 + 0j, 0 + 1j, 1 + 1j])
        result_dict = {param: values}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [
            {"signal": (1 + 0j)},
            {"signal": (0 + 1j)},
            {"signal": (1 + 1j)},
        ]

    def test_unknown_type_returns_raw_value(self):
        """An unknown/other type (e.g. 'array' or 'blob') returns the raw value."""
        param = ParamSpecBase("raw_data", "array")
        value = np.array([1, 2, 3])
        result_dict = {param: value}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert len(res) == 1
        assert "raw_data" in res[0]
        np.testing.assert_array_equal(res[0]["raw_data"], value)

    def test_unknown_type_array_scalar(self):
        """An 'array' type with a scalar value returns the raw value as-is."""
        param = ParamSpecBase("spectrum", "array")
        value = np.array(42)
        result_dict = {param: value}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert len(res) == 1
        assert "spectrum" in res[0]
        np.testing.assert_array_equal(res[0]["spectrum"], value)

    def test_multiple_parameters_different_types(self):
        """Multiple parameters of different types are all processed correctly."""
        numeric_param = ParamSpecBase("voltage", "numeric")
        text_param = ParamSpecBase("status", "text")
        complex_param = ParamSpecBase("impedance", "complex")

        result_dict = {
            numeric_param: np.array(5.0),
            text_param: np.array("ok"),
            complex_param: np.array(3 + 4j),
        }
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert {"voltage": 5.0} in res
        assert {"status": "ok"} in res
        assert {"impedance": (3 + 4j)} in res
        assert len(res) == 3

    def test_empty_dict_returns_empty_list(self):
        """An empty input dict produces an empty result list."""
        result_dict = {}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == []

    def test_numeric_array_multiple_values_one_dict_per_value(self):
        """A numeric array with N values produces exactly N dicts."""
        param = ParamSpecBase("measurements", "numeric")
        values = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
        result_dict = {param: values}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert len(res) == 5
        for i, val in enumerate(values):
            assert res[i] == {"measurements": val}

    def test_text_array_produces_stringified_values(self):
        """A text array converts each element to a string via str()."""
        param = ParamSpecBase("info", "text")
        # Use an object array to preserve original types through str() conversion
        values = np.array([123, 45.6, "hello"], dtype=object)
        result_dict = {param: values}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert len(res) == 3
        for item in res:
            assert isinstance(item["info"], str)
        assert res[0] == {"info": "123"}
        assert res[1] == {"info": "45.6"}
        assert res[2] == {"info": "hello"}

    def test_numeric_scalar_integer_converted_to_float(self):
        """A numeric scalar integer value is converted to float."""
        param = ParamSpecBase("count", "numeric")
        result_dict = {param: np.array(7)}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"count": 7.0}]
        assert isinstance(res[0]["count"], float)

    def test_complex_scalar_from_real_number(self):
        """A real number stored as complex type is converted to complex."""
        param = ParamSpecBase("z", "complex")
        result_dict = {param: np.array(5.0)}
        res = DataSet._finalize_res_dict_standalones(result_dict)
        assert res == [{"z": (5.0 + 0j)}]
        assert isinstance(res[0]["z"], complex)
