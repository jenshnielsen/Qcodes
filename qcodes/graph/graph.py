from __future__ import annotations

import abc
import logging
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    Union,
)

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
        """Unique name of the Port with elements separated by .
        Equivalent to parent.name + . + self.short_name
        """
        pass


class Node(abc.ABC):
    def __init__(self, *, nodeid: NodeId):
        self._nodeid = nodeid

    @property
    def nodeid(self) -> str:
        return self._nodeid

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
    def sources(self) -> Iterable[Node]:
        pass

    @abc.abstractmethod
    def ports(self) -> Iterable[Port]:
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


class Router(Protocol):
    """
    Router class for dynamic routing of station components during
    experimental runs.
    """

    def route_to_source(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = None
    ) -> None:
        pass

    def route_to_meter(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = None
    ) -> None:
        pass

    def route_to_ground(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        pass

    def route_to_float(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        pass

    def route_to_highz(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        pass

    def connect(
        self,
        connections: Mapping[NodeId, Sequence[NodeId]],
    ) -> None:
        """
        Connect the Sources (keys) to the terminals (values) given.

        Args:
            connections: A mapping from NodeId of a source to a sequence of NodeIds for the
                terminals that this source node should be connected to.
        Raises:
            RoutingError: If the set of terminal and source nodes could not be
                connected.
        """
        pass

    def route(
        self,
        *terminal_ids: Union[NodeId, Iterable[NodeId]],
        source_appraiser: NodeAppraiser,
    ) -> None:
        """Routes a set of terminal nodes to the corresponding set of "source" nodes with the highest appraisal value.

        Args:
            terminal_ids: Identifiers of the terminals to route.
                Identifiers may be enclosed in an iterable (e.g., list, tuple, generator) in which case the enclosed
                terminals will all be routed to the same source.
            source_appraiser:  A function that evaluates a set of candidate source nodes.
                The number of arguments given to source_appraiser will match the number of terminal_ids.
                The appraiser must return an integer-like value.  A positive return value means that the set
                of source nodes may be routed to the terminals.  A non-positive value means that
                the set of source nodes may not be routed to the terminals.  Then set of sources
                nodes with the highest appraisal value is used for the route.
        Raises:
            RoutingError: The set of terminal nodes could not be routed with the given appraiser.
        """
        pass

    def eligible_sources_of(
        self, terminal_id: NodeId, source_appraiser: NodeAppraiser = always_true
    ) -> Iterable[NodeId]:
        pass

    def vacate(self, terminal_id: NodeId) -> None:
        pass
