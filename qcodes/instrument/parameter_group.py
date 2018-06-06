from qcodes.instrument.parameter import Parameter
from typing import Dict, Union

valuetypes = Union[int, float, str]

class ParameterGroup:

    def __init__(self, *parameters: Parameter) -> None:
        self.__parameters = parameters


    def get(self) -> Dict['str', Union[dict, valuetypes]]:
        captured_values = {}

        for parameter in self.__parameters:
            captured_values[parameter.name] = parameter.get()
        return captured_values

    def set(self, values: Dict[str, Union[dict, valuetypes]]):

        for param_name, param_value in values.items():
            getattr(self, param_name).set(param_value)
