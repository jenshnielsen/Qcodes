from pytest import fixture
from typing import List


from qcodes.instrument.parameter_group import ParameterGroup
from qcodes.instrument.parameter import Parameter


@fixture
def some_dummy_parameters() -> List[Parameter]:

    dummy_parameters = []
    for name, value in zip(['a', 'b', 'c'], range(3)):
        dummy_parameters.append(Parameter(name=name,
                                label=name.upper(),
                                initial_value=value,
                                set_cmd=None, get_cmd=None))
    return dummy_parameters

@fixture
def more_dummy_parameters() -> List[Parameter]:

    dummy_parameters = []
    for name, value in zip(['d', 'e', 'f'], range(3,6)):
        dummy_parameters.append(Parameter(name=name,
                                label=name.upper(),
                                initial_value=value,
                                set_cmd=None, get_cmd=None))
    return dummy_parameters


def test_parameter_group_basic(some_dummy_parameters):

    pg = ParameterGroup('mypg', *some_dummy_parameters)
    expected_values = {'a': 0, 'b': 1, 'c': 2}
    set_values = {'a': 21, 'b': 11, 'c': 33}

    assert pg.name == 'mypg'
    assert pg.get() == expected_values
    for parameter_name, expected_value in expected_values.items():
        assert getattr(pg, parameter_name).get() == expected_value
    pg.set(set_values)
    assert pg.get() == set_values
    for parameter_name, expected_value in set_values.items():
        assert getattr(pg, parameter_name).get() == expected_value


def test_nested_parameter_group(some_dummy_parameters,
                                more_dummy_parameters):

    pg1 = ParameterGroup('pg1', *some_dummy_parameters)
    pg2 = ParameterGroup('pg2', *more_dummy_parameters)

    outerpg = ParameterGroup('outerpg', pg1, pg2)

    expected_values1 = {'a': 0, 'b': 1, 'c': 2}
    expected_values2 = {'d': 3, 'e': 4, 'f': 5}
    expected_values = {'pg1': expected_values1,
                       'pg2': expected_values2}
    assert outerpg.get() == expected_values
