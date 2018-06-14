from typing import Dict, Union, Sequence, List

from qcodes.utils.metadata import Metadatable
from qcodes.instrument.parameter import Parameter
from qcodes.instrument.base import InstrumentBase
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
                 parent: Union['ParameterGroup', InstrumentBase]=None,
                 names=None) -> None:
        super().__init__()
        # the order of __parameter_dict is importatant but since we
        # are only supporting python 3.6+ we can assume that the dict is
        # ordered. For 3.6 insertion order is an implementation detail but for
        # 3.7 it's guarantied.
        self.__parameter_dict = {}
        self.__name = name
        if parent is not None:
            self.__parent = parent
        else:
            self.__parent = None
        if names is not None:
            assert len(names) == len(parameters)
            for name, parameter in zip(names, parameters):
                self.add_member(parameter, name)
        else:
            for parameter in parameters:
                self.add_member(parameter)

    def get(self) -> Dict['str', Union[dict, value_types]]:
        captured_values = {}

        for name, parameter in self.__parameter_dict.items():
            captured_values[name] = parameter.get()
        return captured_values

    def add_member(self, new_member: Union['ParameterGroup', Parameter],
                   name=None) -> None:
        if name is None:
            name = new_member.short_name

        if name in self.__parameter_dict.keys():
            raise RuntimeError(f"{name} was already "
                               f"added to {self.full_name}")
        self.__parameter_dict[name] = new_member


    @property
    def parent(self) -> Union['ParameterGroup', InstrumentBase]:
        return self.__parent

    @parent.setter
    def set_parent(self, parent: Union['ParameterGroup', InstrumentBase]):
        self.__parent = parent

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

    def __getattr__(self, name: str) -> Union['ParameterGroup', Parameter]:
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
