from pytest import fixture
from typing import List


from qcodes.instrument.parameter_group import ParameterGroup
from qcodes.instrument.parameter import Parameter


@fixture
def some_dummy_parameters() -> List[Parameter]:

    dummy_parameters = []
    for name,value in zip(['a', 'b', 'c'],range(3)):
        dummy_parameters.append(Parameter(name=name,
                                label=name.upper(),
                                initial_value=value,
                                set_cmd=None, get_cmd=None))
    return dummy_parameters

def test_parameter_group_basic(some_dummy_parameters):

    pg = ParameterGroup(*some_dummy_parameters)
    expected_values = {'a': 0, 'b': 1, 'c': 2}
    set_values = {'a': 21, 'b': 11, 'c': 33}
    assert pg.get() == expected_values
    pg.set(set_values)
    assert pg.get() == set_values

