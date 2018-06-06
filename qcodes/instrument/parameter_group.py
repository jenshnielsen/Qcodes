from qcodes.instrument.parameter import Parameter
from typing import Dict, Union

value_types = Union[int, float, str]


class ParameterGroup:

    def __init__(self, *parameters: Parameter) -> None:
        self.__parameters = parameters
        self.__parameter_dict = {}

        for parameter in parameters:
            self.__parameter_dict[parameter.name] = parameter

        for parameter in self.__parameters:
            assert parameter is self.__parameter_dict[parameter.name]

    def get(self) -> Dict['str', Union[dict, value_types]]:
        captured_values = {}

        for parameter in self.__parameters:
            captured_values[parameter.name] = parameter.get()
        return captured_values

    def set(self, values: Dict[str, Union[dict, value_types]]):

        for param_name, param_value in values.items():
            getattr(self, param_name).set(param_value)

    def __getattr__(self, name: str) -> Parameter:
        if name in self.__parameter_dict.keys():
            return self.__parameter_dict[name]

        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
