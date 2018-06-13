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
                 parent=None) -> None:
        super().__init__()
        self.__parameter_dict = {}
        self.__name = name
        if parent is not None:
            self.__parent = parent
        else:
            self.__parent = None
        for parameter in parameters:
            qualified_name = "_".join(parameter.name_parts)
            self.__parameter_dict[qualified_name] = parameter

    def get(self) -> Dict['str', Union[dict, value_types]]:
        captured_values = {}

        for parameter in self.__parameter_dict.values():
            qualified_name = "_".join(parameter.name_parts)
            captured_values[qualified_name] = parameter.get()
        return captured_values

    @property
    def full_name(self):
        return "_".join(self.name_parts)

    @property
    def short_name(self):
        return self.__name

    @property
    def name_parts(self) -> List[str]:
        if self.__parent is not None:
            name_parts = self.__parent.name_parts
        else:
            name_parts = []
        name_parts.append(self.short_name)
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
