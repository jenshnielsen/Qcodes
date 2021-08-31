from __future__ import annotations

import abc
import itertools
from enum import Enum
from typing import (
    Any,
    Callable,
    Iterable,
    Iterator,
    Optional,
    Set,
    Tuple,
    Union,
    overload,
)

import networkx

from qcodes.instrument.parameter import Parameter

NodeId = str  # pylint: disable=invalid-name; This is a type alias, not a constant.
EdgeId = Tuple[NodeId, NodeId]  # pylint: disable=invalid-name;
ValueType = Union["StationGraph.Node", "StationGraph.Edge"]


class StationGraph:
    class Node(abc.ABC):
        class SourceError(Exception):
            pass

        @property
        @abc.abstractmethod
        def parameters(self) -> Iterable[Parameter]:
            pass

        @abc.abstractmethod
        def add_source(self, source: StationGraph.Node) -> None:
            pass

        @abc.abstractmethod
        def remove_source(self, source: StationGraph.Node) -> None:
            pass

        @abc.abstractmethod
        def activate(self) -> None:
            pass

        @abc.abstractmethod
        def deactivate(self) -> None:
            pass

    class Edge(Enum):
        Active = True
        Inactive = False
        Parent = "Parent"

    def __init__(self, graph: Optional[networkx.DiGraph] = None):
        if graph is None:
            self._graph = networkx.DiGraph()
        else:
            self._graph = graph

    @overload
    def __getitem__(self, identifier: NodeId) -> StationGraph.Node:
        ...

    @overload
    def __getitem__(self, identifier: EdgeId) -> StationGraph.Edge:
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


class MutableStationGraph(StationGraph):
    def __setitem__(self, identifier: Union[NodeId, EdgeId], value: ValueType) -> None:
        if isinstance(identifier, tuple):
            self._graph.add_edge(*identifier)
        else:
            self._graph.add_node(identifier)
        super().__setitem__(identifier, value)

    def as_station_graph(self) -> StationGraph:
        return StationGraph(self._graph)
