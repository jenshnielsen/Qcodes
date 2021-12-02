from __future__ import annotations

import abc
import logging
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Iterable, Tuple, Union

from typing_extensions import Protocol

NodeId = str
EdgeId = Tuple[NodeId, NodeId]
ValueType = Union["Node", "Edge"]


_LOG = logging.getLogger(__name__)


ConnectionAttributeType = Any

if TYPE_CHECKING:
    from qcodes.instrument.base import InstrumentBase
    from qcodes.instrument.channel import ChannelList
    from qcodes.instrument.parameter import Parameter, _BaseParameter


# The Port Protocol is a minimal interface for a InstrumentChannel.
class Port(Protocol):

    parameters: Dict[str, _BaseParameter]
    submodules: Dict[str, Union[InstrumentBase, ChannelList]]

    @property
    def short_name(self) -> str:
        """Short name of the instrument"""
        pass

    @property
    def full_name(self) -> str:
        """Unique name of the Port with elements separated by ."""
        pass


class Node(abc.ABC):
    def __init__(self, *, name: str = "Node"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    @abc.abstractmethod
    def parameters(self) -> Iterable[Parameter]:
        pass

    def add_source(self, source: Node) -> None:
        _LOG.info(f"Adding Source {source.name} to Node: {self.name}")

    def remove_source(self, source: Node) -> None:
        _LOG.info(f"Removing Source {source.name} from Node: {self.name}")

    def activate(self) -> None:
        _LOG.info(f"Activating Node: {self.name}")

    def deactivate(self) -> None:
        _LOG.info(f"Deactivating Node: {self.name}")

    @abc.abstractmethod
    def sources(self) -> Iterable[Port]:
        pass

    @abc.abstractmethod
    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        pass

    @property
    def active(self) -> bool:
        pass


class Edge(abc.ABC):
    @property
    @abc.abstractmethod
    def active(self) -> bool:
        pass
