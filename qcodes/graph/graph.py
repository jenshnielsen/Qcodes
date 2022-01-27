from __future__ import annotations

import abc
import itertools
import logging
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    Iterable,
    Iterator,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

import networkx
from typing_extensions import Protocol

NodeId = str
EdgeId = Tuple[NodeId, NodeId]
ValueType = Union["Port", "EdgeABC"]


_LOG = logging.getLogger(__name__)


ConnectionAttributeType = Any

if TYPE_CHECKING:
    from qcodes.instrument.base import Instrument
    from qcodes.instrument.channel import InstrumentModule
    from qcodes.instrument.parameter import Parameter, _BaseParameter


# The Port Protocol is a minimal interface for a InstrumentChannel.
class Port(Protocol):

    parameters: Dict[str, _BaseParameter]
    instrument_modules: Dict[str, InstrumentModule]

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

    @property
    def activator(self) -> Activator:
        ...


class Activator(abc.ABC):
    def __init__(self, *, port: Port):
        self._port = port

    @property
    @abc.abstractmethod
    def parameters(self) -> Iterable[Parameter]:
        pass

    def add_source(self, source: Port) -> None:
        _LOG.info(f"Adding Source {source.full_name} to Node: {self.port.full_name}")

    def remove_source(self, source: Port) -> None:
        _LOG.info(
            f"Removing Source {source.full_name} from Node: {self.port.full_name}"
        )

    def activate(self) -> None:
        _LOG.info(f"Activating Node: {self.port.full_name}")

    def deactivate(self) -> None:
        _LOG.info(f"Deactivating Node: {self.port.full_name}")

    @property
    def port(self) -> Port:
        return self._port

    @abc.abstractmethod
    def upstream_ports(self) -> Iterable[Port]:
        # todo naming
        pass

    @abc.abstractmethod
    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        pass

    @property
    @abc.abstractmethod
    def active(self) -> bool:
        pass


class EndpointActivator(Activator):
    def __init__(self, *, port: Port, parent: Optional[Port] = None):
        super().__init__(port=port)
        self._parent = parent
        self._sources: Set[Port] = set()

    @property
    def parameters(self) -> Iterable[Parameter]:
        return []

    def add_source(self, source: Port) -> None:
        self._sources.add(source)
        super().add_source(source)

    def remove_source(self, source: Port) -> None:
        self._sources.remove(source)
        super().remove_source(source)

    def activate(self) -> None:
        _LOG.info(f"Activating Node: {self.port.full_name}")

    def deactivate(self) -> None:
        _LOG.info(f"Deactivating Node: {self.port.full_name}")

    def upstream_ports(self) -> Iterable[Port]:
        return itertools.chain.from_iterable(
            source.activator.upstream_ports() for source in self._sources
        )

    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        return {}

    @property
    def active(self) -> bool:
        return False


class InstrumentModuleActivator(Activator):
    def __init__(
        self,
        *,
        port: Port,
        parent: Optional[Port] = None,
    ):
        super().__init__(port=port)
        self._parent = parent

    @property
    def parameters(self) -> Iterable[Parameter]:
        return list(self.port.parameters.values())

    def upstream_ports(self) -> Iterable[Port]:
        return [self.port]

    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        return {}

    @property
    def active(self) -> bool:
        return False


class ConnectorActivator(Activator):
    def __init__(self, *, port: Port):
        super().__init__(port=port)
        self._sources: Set[Port] = set()

    @property
    def parameters(self) -> Iterable[Parameter]:
        return itertools.chain.from_iterable(
            source.parameters for source in self._sources
        )

    def add_source(self, source: Port) -> None:
        super().add_source(source=source)
        self._sources.add(source)

    def remove_source(self, source: Port) -> None:
        super().remove_source(source=source)
        self._sources.remove(source)

    def upstream_ports(self) -> Iterable[Port]:
        return itertools.chain.from_iterable(
            source.activator.upstream_ports() for source in self._sources
        )

    def connection_attributes(self) -> Dict[str, Dict[NodeId, ConnectionAttributeType]]:
        return {}

    @property
    def active(self) -> bool:
        return False


class EdgeType(str, Enum):
    ELECTRICAL_CONNECTION = "electrical_connection"
    PART_OF = "part_of"


class EdgeStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    NOT_ACTIVATABLE = "not_activatable"


class EdgeABC(abc.ABC):
    @property
    @abc.abstractmethod
    def status(self) -> EdgeStatus:
        pass

    @abc.abstractmethod
    def activate(self) -> None:
        pass

    @abc.abstractmethod
    def deactivate(self) -> None:
        pass

    @property
    @abc.abstractmethod
    def type(self) -> EdgeType:
        pass


class BasicEdge(EdgeABC):
    def __init__(
        self, *, edge_type: EdgeType, edge_status: EdgeStatus = EdgeStatus.INACTIVE
    ):
        self._edge_status = edge_status
        self._edge_type = edge_type

    @property
    def status(self) -> EdgeStatus:
        return self._edge_status

    @property
    def type(self) -> EdgeType:
        return self._edge_type

    @property
    def _can_be_activated(self) -> bool:
        return (
            self.status == EdgeStatus.ACTIVE or self.status == EdgeStatus.ACTIVE
        ) and self.type == EdgeType.ELECTRICAL_CONNECTION

    def activate(self) -> None:
        if self._can_be_activated:
            self._edge_status = EdgeStatus.ACTIVE
        else:
            raise NotImplementedError(
                f"Cannot activate an edge of type {self.type} with status {self.status}"
            )

    def deactivate(self) -> None:
        if self._can_be_activated:
            self._edge_status = EdgeStatus.INACTIVE
        else:
            raise NotImplementedError(
                f"Cannot deactivate an edge of type {self.type} with status {self.status}"
            )


T = TypeVar("T", bound="StationGraph")


class StationGraph:
    @classmethod
    def compose(cls: Type[T], *graphs: StationGraph) -> T:
        composition = networkx.DiGraph()
        for graph in graphs:
            composition = networkx.compose(
                composition, graph._graph  # pylint: disable=protected-access
            )
        composed = cls(composition)
        for edge in composed.edges:
            if composed[edge].status == EdgeStatus.ACTIVE:
                source = composed[edge[0]]
                destination = composed[edge[1]]
                destination.add_source(source)
        return composed

    @classmethod
    def prune(cls: Type[T], graph: StationGraph) -> T:
        pruned = graph._graph.copy()  # pylint: disable=protected-access
        orphans = [
            node_id for node_id, node in pruned.nodes.items() if "value" not in node
        ]
        for node_id in orphans:
            pruned.remove_node(node_id)
        return cls(pruned)

    @classmethod
    def subgraph_of(
        cls: Type[T],
        graph: StationGraph,
        is_node_included: Callable[[NodeId], bool] = lambda _: True,
        is_edge_included: Callable[[EdgeId], bool] = lambda _: True,
    ) -> T:
        def _is_edge_included(start: NodeId, end: NodeId) -> bool:
            return is_edge_included((start, end))

        subgraph = networkx.classes.graphviews.subgraph_view(
            graph._graph,  # pylint: disable=protected-access
            filter_node=is_node_included,
            filter_edge=_is_edge_included,
        )
        return cls(subgraph)

    def __init__(self, graph: Optional[networkx.DiGraph] = None):
        if graph is None:
            self._graph = networkx.DiGraph()
        else:
            self._graph = graph

    @overload
    def __getitem__(self, identifier: NodeId) -> Port:
        ...

    @overload
    def __getitem__(self, identifier: EdgeId) -> EdgeABC:
        ...

    def __getitem__(self, identifier: Union[NodeId, EdgeId]) -> Optional[ValueType]:
        if isinstance(identifier, tuple):
            attributes = self._graph[identifier[0]][identifier[1]]
        else:
            attributes = self._graph.nodes[identifier]
        return attributes.get("value")

    def __setitem__(self, identifier: Union[NodeId, EdgeId], value: ValueType) -> None:
        if isinstance(identifier, tuple):
            attributes = self._graph[identifier[0]][identifier[1]]
        else:
            attributes = self._graph.nodes[identifier]
        attributes["value"] = value

    @property
    def nodes(self) -> Iterator[NodeId]:
        return iter(self._graph.nodes)

    @property
    def edges(self) -> Iterator[EdgeId]:
        return iter(self._graph.edges)

    def neighbors_of(self, vertex_id: NodeId) -> Iterator[NodeId]:
        return iter(
            set(
                itertools.chain(
                    self.predecessors_of(vertex_id), self.successors_of(vertex_id)
                )
            )
        )

    def successors_of(self, vertex_id: NodeId) -> Iterator[NodeId]:
        return self._graph.successors(vertex_id)

    def predecessors_of(self, vertex_id: NodeId) -> Iterator[NodeId]:
        return self._graph.predecessors(vertex_id)

    def breadth_first_nodes_from(
        self, node_id: NodeId, reverse: bool = False
    ) -> Iterator[NodeId]:
        edges = networkx.algorithms.traversal.breadth_first_search.bfs_edges(
            self._graph, node_id, reverse=reverse
        )
        return itertools.chain([node_id], map(lambda edge: edge[1], edges))

    def breadth_first_edges_from(
        self, node_id: NodeId, reverse: bool = False
    ) -> Iterator[EdgeId]:
        edges = networkx.algorithms.traversal.breadth_first_search.bfs_edges(
            self._graph, node_id, reverse=reverse
        )
        return itertools.chain(edges)

    def shortest_paths_between(
        self, source: NodeId, destination: NodeId
    ) -> Iterator[Iterator[NodeId]]:
        return networkx.algorithms.simple_paths.shortest_simple_paths(
            self._graph, source, destination
        )


class MutableStationGraph(StationGraph):
    def __setitem__(self, identifier: Union[NodeId, EdgeId], value: ValueType) -> None:
        if isinstance(identifier, tuple):
            self._graph.add_edge(*identifier)
        else:
            print(f"adding node {identifier}")
            self._graph.add_node(identifier)
        super().__setitem__(identifier, value)

    def as_station_graph(self) -> StationGraph:
        return StationGraph(self._graph)
