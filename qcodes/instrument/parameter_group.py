from typing import Dict, Union, Sequence, List

from qcodes.utils.metadata import Metadatable
from qcodes.instrument.parameter import Parameter
from qcodes.utils.helpers import full_class

value_types = Union[int, float, str]


class ParameterGroup(Metadatable):
    """


    TODO: It would be handy to be able to pick out a single value from a nested
    level for cases where this is in all outer levers
    TODO: This still needs docstrings, handling of dependencies as in array
    parameters. and correct snapshot handling.

    """
    def __init__(self, name: str,
                 *parameters: Union[Parameter, 'ParameterGroup'],
                 instrument=None) -> None:
        super().__init__()
        self.__parameters = parameters
        self.__parameter_dict = {}
        self.__name = name
        if instrument:
            self.__instrument = instrument
            self.__full_name = f"{instrument.name}_{name}"
        else:
            self.__instrument = None
            self.__full_name = name
        for parameter in parameters:
            self.__parameter_dict[parameter.qualified_name] = parameter

    def get(self) -> Dict['str', Union[dict, value_types]]:
        captured_values = {}

        for parameter in self.__parameters:
            captured_values[parameter.qualified_name] = parameter.get()
        return captured_values

    @property
    def name(self):
        return self.__name

    @property
    def full_name(self):
        return self.__full_name

    @property
    def short_name(self):
        return self.__name

    @property
    def name_parts(self) -> List[str]:
        name_parts = [self.name]
        parent_inst = self.__instrument
        while parent_inst is not None:
            name_parts.append(parent_inst.short_name)
            parent_inst = parent_inst.parent
        name_parts.reverse()
        return name_parts


    @property
    def parameter_dict(self):
        return self.__parameter_dict

    def set(self, values: Dict[str, Union[dict, value_types]]):

        for param_name, param_value in values.items():
            getattr(self, param_name).set(param_value)

    def __getattr__(self, name: str) -> Parameter:
        if name in self.__parameter_dict.keys():
            return self.__parameter_dict[name]

        raise AttributeError(f"'{self.__class__.__name__}' object has"
                             f" no attribute '{name}'")


    def snapshot_base(self, update: bool=False,
                      params_to_skip_update: Sequence[str]=None):

        snap = {}
        membersdict = {param_name: param.snapshot(update=update) for param_name,
                       param in self.__parameter_dict.items()}
        snap['members'] = membersdict
        snap['__class__'] = full_class(self)
        return snap
