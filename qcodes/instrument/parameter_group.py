from qcodes.instrument.parameter import Parameter
from typing import Dict, Union

value_types = Union[int, float, str]


class ParameterGroup:
    """


    TODO: It would be handy to be able to pick out a single value from a nested
    level for cases where this is in all outer levers
    TODO: This still needs docstrings, handling of dependencies as in array
    parameters. and correct snapshot handling.

    """
    def __init__(self, name: str, *parameters: Union[Parameter,
                                                     'ParameterGroup']) -> None:
        self.__parameters = parameters
        self.__parameter_dict = {}
        self.__name = name
        for parameter in parameters:
            self.__parameter_dict[parameter.name] = parameter

    def get(self) -> Dict['str', Union[dict, value_types]]:
        captured_values = {}

        for parameter in self.__parameters:
            captured_values[parameter.name] = parameter.get()
        return captured_values

    @property
    def name(self):
        return self.__name

    def set(self, values: Dict[str, Union[dict, value_types]]):

        for param_name, param_value in values.items():
            getattr(self, param_name).set(param_value)

    def __getattr__(self, name: str) -> Parameter:
        if name in self.__parameter_dict.keys():
            return self.__parameter_dict[name]

        raise AttributeError(f"'{self.__class__.__name__}' object has"
                             f" no attribute '{name}'")

