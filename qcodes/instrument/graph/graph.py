from __future__ import annotations

import itertools
from enum import Enum
from typing import Any, Callable, Iterator, Optional, Tuple, Union, overload

import networkx
from typing_extensions import Protocol, TypeAlias

NodeId = str
EdgeId = Tuple[NodeId, NodeId]


class Node(Protocol):
    def activate(self) -> None:
        pass

    def deactivate(self) -> None:
        pass

    def add_source(self, source: Node) -> None:
        pass

    def remove_source(self, source: Node) -> None:
        pass

    @property
    def is_active(self) -> bool:
        pass


class Edge(Enum):
    Active = True
    Inactive = False


ValueType = Union[Node, Edge]


class StationGraph:
    @classmethod
    def compose(cls, *graphs: StationGraph) -> StationGraph:
        composition = networkx.DiGraph()
        for graph in graphs:
            composition = networkx.compose(composition, graph._graph)
        composed = StationGraph(composition)
        for edge in composed.edges:
            if composed[edge] is not Edge.Inactive:
                source = composed[edge[0]]
                assert source is not None
                destination = composed[edge[1]]
                assert destination is not None
                destination.add_source(source)
        return composed

    @classmethod
    def prune(cls, graph: StationGraph) -> StationGraph:
        pruned = graph._graph.copy()
        orphans = [
            node_id for node_id, node in pruned.nodes.items() if "value" not in node
        ]
        for node_id in orphans:
            pruned.remove_node(node_id)
        return StationGraph(pruned)

    @classmethod
    def subgraph_of(
        cls,
        graph: StationGraph,
        is_node_included: Callable[[NodeId], bool] = lambda _: True,
        is_edge_included: Callable[[EdgeId], bool] = lambda _: True,
    ) -> StationGraph:
        def _is_edge_included(start: NodeId, end: NodeId) -> bool:
            return is_edge_included((start, end))

        subgraph = networkx.classes.graphviews.subgraph_view(
            graph._graph,  # pylint: disable=protected-access
            filter_node=is_node_included,
            filter_edge=_is_edge_included,
        )
        return StationGraph(subgraph)

    def __init__(self, graph: Optional[networkx.DiGraph] = None):
        if graph is None:
            self._graph = networkx.DiGraph()
        else:
            self._graph = graph

    @overload
    def __getitem__(self, identifier: NodeId) -> Optional[Node]:
        ...

    @overload
    def __getitem__(self, identifier: EdgeId) -> Optional[Edge]:
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

    def draw(self) -> None:
        """
        Draw station graph using :py:meth:`networkx.draw` and:

          * show labels of the nodes
          * show non-``None`` values of the edges (actually, showing string
            representation of ``value`` attribute of the edges if that
            ``value`` is not ``None``)
          * color active edges in red, and other edges in black
          * color nodes without values in yellow, and other nodes in blue

        """
        graph = self._graph

        positions = networkx.spring_layout(graph)

        edge_values = networkx.get_edge_attributes(graph, "value")
        edge_labels = {
            edge_name: edge_label if edge_label is not None else ""
            for edge_name, edge_label in edge_values.items()
        }

        edge_colors = [
            "k" if graph[node_from][node_to]["value"] is None else "r"
            for node_from, node_to in graph.edges()
        ]

        node_colors = [
            "b" if "value" in graph.nodes[node] else "y" for node in graph.nodes
        ]

        networkx.draw(
            graph,
            positions,
            with_labels=True,
            edge_color=edge_colors,
            width=1,
            node_size=50,
            node_color=node_colors,
        )

        networkx.draw_networkx_edge_labels(graph, positions, edge_labels=edge_labels)

    def draw_spring(self, **kwargs: Any) -> None:
        return networkx.draw_spring(self._graph, with_labels=True, **kwargs)

    def draw_spectral(self, **kwargs: Any) -> None:
        return networkx.draw_spectral(self._graph, with_labels=True, **kwargs)

    def draw_circular(self, **kwargs: Any) -> None:
        return networkx.draw_circular(self._graph, with_labels=True, **kwargs)

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
            self._graph.add_node(identifier)
        super().__setitem__(identifier, value)

    def as_station_graph(self) -> StationGraph:
        return StationGraph(self._graph)
