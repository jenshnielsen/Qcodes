"""
Station level routing for lab equipment and device specific experiments.
"""
import itertools
import logging
import warnings
from collections import defaultdict
from typing import (
    Any,
    Dict,
    FrozenSet,
    Generic,
    Hashable,
    Iterable,
    Mapping,
    Optional,
    Sequence,
    Set,
    Tuple,
    TypeVar,
    Union,
    overload,
)

from typing_extensions import Protocol

from .appraisal import (
    NodeAppraiser,
    SingleNodeAppraiser,
    always_true,
    node_has_unit,
    node_is_constant_meter,
    node_is_constant_source,
    node_is_general_ground,
    node_is_meter,
    node_is_source,
    node_is_source_with_name,
)
from .graph import EdgeId, Node, NodeId, StationGraph
from .utils.iteration import lazy_product

_OrderedEdgePath = Iterable[Tuple[NodeId, ...]]
_OrderedEdgePathGroup = Iterable[_OrderedEdgePath]
_Path = Iterable[NodeId]
_PathGroup = Iterable[_Path]
_SourceIdGroup = Iterable[NodeId]
_TerminalIdGroup = Iterable[NodeId]


_LOG = logging.getLogger(__name__)


class HasGraph(Protocol):
    graph: StationGraph


class Router:
    """
    Router class for dynamic routing of station components during
    experimental runs.
    """

    def __init__(self, station: HasGraph):
        self._graph = _RoutingGraphAdapter(station.graph)
        self._initialize_active_edges()

        self._activate_dynamic_edges()

    def _activate_dynamic_edges(self) -> None:
        for node in self._graph.nodes:
            if hasattr(self._graph[node], "activate_to_source"):
                dynamic_sources = tuple(self.eligible_sources_of(node))
                for source in dynamic_sources:
                    self._connect(source_ids=[source], terminal_ids=[node])

        # This must be called after dynamic edges are connected in order
        # to make the activated nodes routable via connect later
        # pylint: disable=protected-access
        self._graph._terminals_routed_to = defaultdict(set)

    def _initialize_active_edges(self) -> None:
        for edge_id in self._graph.edges:
            if self._graph[edge_id].active is True:
                for edge in zip(edge_id, edge_id[1:]):
                    self._graph.activate_edge(edge, edge_id[-1])
                for node in edge_id[:-1]:
                    self._graph.activate_node(node, edge_id[-1])

    def route_to_source(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = None
    ) -> None:
        def predicate(node: Node) -> int:
            return (
                node_is_source(node)
                and not node_is_constant_source(node)
                and node_has_unit(unit)(node)
            )

        self.route(terminal_id, source_appraiser=predicate)

    def route_to_meter(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = None
    ) -> None:
        def predicate(node: Node) -> bool:
            return (
                node_is_meter(node)
                and not node_is_constant_meter(node)
                and node_has_unit(unit)(node)
            )

        self.route(terminal_id, source_appraiser=predicate)

    def route_to_ground(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        self.route(terminal_id, source_appraiser=node_is_general_ground(unit=unit))

    def route_to_float(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        predicate = node_is_source_with_name("float", unit=unit)
        self.route(terminal_id, source_appraiser=predicate)

    def route_to_highz(
        self, terminal_id: Union[NodeId, Iterable[NodeId]], unit: Optional[str] = "V"
    ) -> None:
        predicate = node_is_source_with_name("highz", unit=unit)
        self.route(terminal_id, source_appraiser=predicate)

    def connect_by_dict(
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
        sources = (tuple(connections.keys()),)
        terminals = tuple(val for val in connections.values())
        self.connect(sources, terminals)

    def connect(
        self,
        source_ids: Union[NodeId, _TerminalIdGroup, Iterable[_TerminalIdGroup]],
        terminal_ids: Union[NodeId, _TerminalIdGroup, Iterable[_TerminalIdGroup]],
    ) -> None:
        """
        Connect the given source_ids to the given terminal_ids.

        In the following an iterable of source_ids (terminal_ids)
        is referred to as a source group (terminal group).
        It is also assumed that exactly one source group and one
        or more terminal groups are supplied to the function.

        Each source in the source group is connected to the terminals in the matching
        terminal group. E.g. the first source is connected to
        all terminals in the first terminal group and the second source to all
        terminals in the second terminal group.
        It is therefore required that the number of sources is equal to the
        number of terminal groups.

        Note: For backwards compatibility source_ids is given as an iterable
        of source groups. (An iterable of iterables of NodeIds).
        It is however, an error for the iterable of source groups to have more than
        one element.

        Args:
            source_ids: Either a single NodeId of a source, an iterable of NodeIds
                or an iterable of iterables of NodeIds.  ``NodeId1`` is equivalent to
                ``[[NodeId1]]`` and ``[NodeId1, NodeId2]`` is equivalent to
                ``[[NodeId1], [NodeId2]]``.
            terminal_ids: Either a single NodeId of a terminal, an iterable of NodeIds
                or an iterable of iterables of NodeIds.  ``NodeId1`` is equivalent to
                ``[[NodeId1]]`` and ``[NodeId1, NodeId2]`` is equivalent to
                ``[[NodeId1], [NodeId2]]``.
        Raises:
            RoutingError: If the set of terminals and sources nodes could not be
                connected, the number of sources and terminal groups does not match
                or more than one source group is supplied.
        """

        source_ids = _tuple_wrap(source_ids)
        terminal_ids = _tuple_wrap(terminal_ids)

        terminal_groups = [_tuple_wrap(terminal_id) for terminal_id in terminal_ids]
        source_groups = [_tuple_wrap(terminal_id) for terminal_id in source_ids]
        if len(source_groups) > 1:
            raise RoutingError("More than one source group supplied to connect.")
        self._connect(source_groups, terminal_groups)

    def _connect(
        self,
        source_ids: Union[NodeId, _SourceIdGroup, Iterable[_SourceIdGroup]],
        terminal_ids: Union[NodeId, _TerminalIdGroup, Iterable[_TerminalIdGroup]],
    ) -> None:

        source_ids = _tuple_wrap(source_ids)
        terminal_ids = _tuple_wrap(terminal_ids)

        terminal_groups = [_tuple_wrap(terminal_id) for terminal_id in terminal_ids]
        source_groups = [_tuple_wrap(terminal_id) for terminal_id in source_ids]

        num_terminal_groups = len(terminal_groups)

        num_sources_in_groups = [len(source_group) for source_group in source_groups]

        if not all(
            num_sources == num_terminal_groups for num_sources in num_sources_in_groups
        ):
            raise RoutingError(
                f"Trying to route source groups with the following number of sources "
                f"each : {num_sources_in_groups} to "
                f"{num_terminal_groups} terminal group(s). "
                f"Each source group must have as many sources as there "
                f"are terminal groups."
            )

        _log_connections(source_groups, terminal_groups)

        finder = _RouteFinder(self._graph)
        paths = finder.find_paths_for(source_groups, terminal_groups)

        if paths is None:
            raise RoutingError(
                f"No available routes between {source_groups} and {terminal_groups}."
            )

        ordered_paths = self._order_paths_for_activation(paths)
        self._activate_ordered_paths(ordered_paths)

        for terminal in list(set(itertools.chain(*terminal_groups))):
            self._graph.activate_node(terminal, terminal)

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
        finder = _SourceFinder(self._graph, source_appraiser)
        terminal_groups = [_tuple_wrap(terminal_id) for terminal_id in terminal_ids]
        source_groups = finder.find_eligible_source_groups(*terminal_ids)
        self._connect(source_groups, terminal_groups)

    def joint_route_per_same_eligible_sources(
        self,
        terminal_ids: Iterable[NodeId],
        source_appraiser: SingleNodeAppraiser,
    ) -> None:
        """Routes terminal nodes with same eligible sources jointly using the appraiser.

        Args:
            terminal_ids: An iterable (e.g., list, tuple, generator) of identifiers of the
                terminals to route.
            source_appraiser: A function that evaluates a single candidate source node. The
                appraiser must return an integer-like value. A positive return value means that
                the source node may be routed to the terminals. A non-positive value means that
                the source node may not be routed to the terminals. Then the sources node with
                the highest appraisal value is used for the route.
        Raises:
            RoutingError: The set of terminal nodes could not be routed with the given appraiser.
        """
        eligibles_per_terminal: Dict[str, FrozenSet[str]] = {
            terminal: frozenset(
                self.eligible_sources_of(terminal, source_appraiser=source_appraiser)
            )
            for terminal in terminal_ids
        }

        terminals_per_eligible_sources: Dict[FrozenSet[str], Set[str]]
        terminals_per_eligible_sources = defaultdict(set)
        for terminal, eligible_sources in eligibles_per_terminal.items():
            terminals_per_eligible_sources[eligible_sources].add(terminal)

        groups_of_unique_eligible_sources = tuple(
            set(eligible_sources)
            for eligible_sources in terminals_per_eligible_sources.keys()
        )
        shared_sources_among_unique_eligible_groups = (
            set.intersection(*groups_of_unique_eligible_sources)
            if len(groups_of_unique_eligible_sources) > 1
            else set()
        )

        if len(shared_sources_among_unique_eligible_groups) > 0:
            warnings.warn(
                f"{terminal_ids} found to have overlapping unique sources that "
                f"they can be routed to, hence the routing may not be successful: "
                f"{shared_sources_among_unique_eligible_groups}"
            )

        for (
            terminals_with_same_eligible_sources
        ) in terminals_per_eligible_sources.values():
            self.route(
                terminals_with_same_eligible_sources, source_appraiser=source_appraiser
            )

    def eligible_sources_of(
        self, terminal_id: NodeId, source_appraiser: NodeAppraiser = always_true
    ) -> Iterable[NodeId]:
        finder = _SourceFinder(self._graph, source_appraiser)
        source_groups = finder.find_eligible_source_groups(terminal_id)
        return (next(iter(sources)) for sources in source_groups)

    def vacate(self, terminal_id: NodeId) -> None:
        vacation_graph = self._graph.routed_subgraph_of(terminal_id)
        nodes_ordered_from_terminal_node = tuple(
            vacation_graph.breadth_first_nodes_from(terminal_id, reverse=True)
        )
        for node in nodes_ordered_from_terminal_node:
            self._graph.deactivate_node(node, terminal_id)
        for node in nodes_ordered_from_terminal_node:
            for predecessor in vacation_graph.predecessors_of(node):
                self._graph.deactivate_edge((predecessor, node), terminal_id)

    @staticmethod
    def _order_paths_for_activation(paths: _PathGroup) -> _OrderedEdgePathGroup:
        ordered_edge_paths = []
        for nodes_in_path in (tuple(path) for path in paths):
            tmp_ordered_edge_paths = []
            terminal = nodes_in_path[-1]
            for edge in zip(nodes_in_path, nodes_in_path[1:]):
                edge_to_terminal = edge + (terminal,)
                tmp_ordered_edge_paths.append(tuple(edge_to_terminal))
            ordered_edge_paths.append(tmp_ordered_edge_paths)

        return ordered_edge_paths

    def _activate_ordered_paths(self, ordered_paths: _OrderedEdgePathGroup) -> None:
        for ordered_edges in itertools.zip_longest(*ordered_paths):
            for edge_with_terminal_id in ordered_edges:
                if edge_with_terminal_id is not None:
                    source_id, delegate_id, terminal_id = edge_with_terminal_id
                    edge = (source_id, delegate_id)
                    self._graph.activate_edge(edge, terminal_id)
                    self._graph.activate_node(source_id, terminal_id)


class RoutingError(Exception):
    pass


class _RoutingGraphAdapter:
    def __init__(self, graph: StationGraph):
        self._graph = graph
        self._terminals_routed_to: Dict[
            Union[NodeId, EdgeId], Set[NodeId]
        ] = defaultdict(set)

    @property
    def edges(self) -> Iterable[EdgeId]:
        return self._graph.edges

    @property
    def nodes(self) -> Iterable[NodeId]:
        return self._graph.nodes

    def __getitem__(self, key: Union[NodeId, EdgeId]) -> Any:
        return self._graph[key]

    def routed_subgraph_of(self, terminal_id: NodeId) -> StationGraph:
        def edge_has_matching_terminal_id(edge: EdgeId) -> bool:
            terminal_ids = self._terminals_routed_to[edge]
            return terminal_id in terminal_ids

        return StationGraph.subgraph_of(
            self._graph, is_edge_included=edge_has_matching_terminal_id
        )

    def make_search_graph_for(self, terminal_ids: Iterable[NodeId]) -> StationGraph:
        eligible_ids = (None, *terminal_ids)

        def is_included(identifier: Union[NodeId, EdgeId]) -> bool:
            terminal_ids = self._terminals_routed_to[identifier]
            return (len(terminal_ids) == 0) or (
                len(terminal_ids.intersection(eligible_ids)) > 0
            )

        return StationGraph.subgraph_of(
            self._graph, is_edge_included=is_included, is_node_included=is_included
        )

    def activate_node(self, node: NodeId, terminal_id: NodeId) -> None:
        self._graph[node].activate()
        node_terminal_ids = self._terminals_routed_to[node]
        node_terminal_ids.add(terminal_id)

    def deactivate_node(self, node: NodeId, terminal_id: NodeId) -> None:
        node_terminal_ids = self._terminals_routed_to[node]
        node_terminal_ids.remove(terminal_id)
        if len(node_terminal_ids) == 0:
            self._graph[node].deactivate()

    def activate_edge(self, edge_id: EdgeId, terminal_id: NodeId) -> None:
        source, delegate = (self._graph[node] for node in edge_id)
        delegate.add_source(source)
        terminal_ids = self._terminals_routed_to[edge_id]
        terminal_ids.add(terminal_id)
        self._graph[edge_id].activate()

    def deactivate_edge(self, edge_id: EdgeId, terminal_id: NodeId) -> None:
        terminal_ids = self._terminals_routed_to[edge_id]
        terminal_ids.remove(terminal_id)
        if len(terminal_ids) == 0:
            source, delegate = (self._graph[node] for node in edge_id)
            delegate.remove_source(source)
            self._graph[edge_id].deactivate()


class _SourceFinder:
    """Finds nodes that meet the source_appraiser criteria and returns them as eligible_source_groups"""

    def __init__(self, graph: _RoutingGraphAdapter, source_appraiser: NodeAppraiser):
        self._graph = graph
        self._appraiser = source_appraiser

    def find_eligible_source_groups(
        self,
        *terminal_ids: Union[NodeId, Iterable[NodeId]],
    ) -> Tuple[Tuple[NodeId, ...], ...]:
        terminal_groups = [_tuple_wrap(terminal_id) for terminal_id in terminal_ids]
        terminal_sources = map(self._nearest_sources_available_to, terminal_groups)
        appraisals: Iterable[Tuple[int, Tuple[str, ...]]] = (
            (self._appraise(sources), sources)
            for sources in itertools.product(*terminal_sources)
        )
        if _LOG.isEnabledFor(logging.DEBUG):
            appraisals = list(appraisals)
            _LOG.debug(
                f"Found the following appraisals of potential sources for {terminal_groups}: "
                f"{appraisals}"
            )
        eligible_appraisals = filter(lambda pair: pair[0] > 0, appraisals)
        sorted_appraisals = sorted(eligible_appraisals, key=lambda pair: -pair[0])
        eligible_sources = tuple(sources for appraisal, sources in sorted_appraisals)
        _LOG.info(
            f"Found the following eligible sources for {terminal_groups}: {eligible_sources}"
        )
        if len(eligible_sources) == 0:
            raise RoutingError(f"No eligible sources found for {terminal_groups}.")
        return eligible_sources

    def _nearest_sources_available_to(
        self, terminal_ids: _TerminalIdGroup
    ) -> _SourceIdGroup:
        search_graph = self._graph.make_search_graph_for(terminal_ids)
        searcher = _GraphSearcher(search_graph)

        def total_distance_to(source_id: NodeId) -> int:
            return sum(
                searcher.distance_between(source_id, terminal_id)
                for terminal_id in terminal_ids
            )

        source_groups = [
            searcher.ascending_distance_sources_of(terminal_id)
            for terminal_id in terminal_ids
        ]
        if len(source_groups) == 1:
            return source_groups[0]
        sources_in_common = _intersection_of(*source_groups)
        return sorted(sources_in_common, key=total_distance_to)

    def _appraise(self, source_ids: _SourceIdGroup) -> int:
        return self._appraiser(*[self._graph[source_id] for source_id in source_ids])


class _RouteFinder:
    """
    Finds optimal routes between source and terminals"""

    def __init__(self, graph: _RoutingGraphAdapter):
        self._graph = graph

    def find_paths_for(
        self,
        source_groups: Iterable[_SourceIdGroup],
        terminal_groups: Iterable[_TerminalIdGroup],
    ) -> Optional[_PathGroup]:
        routes = self._calculate_routes(source_groups, terminal_groups)
        try:
            path_groups = next(iter(routes))
            paths: Iterable[Iterable[NodeId]] = itertools.chain(*path_groups)
            if _LOG.isEnabledFor(logging.DEBUG):
                paths = tuple(tuple(path) for path in paths)
                _LOG.debug(f"Found the following paths: {paths}")
            return paths
        except StopIteration:
            return None

    def _calculate_routes(
        self,
        source_groups: Iterable[_SourceIdGroup],
        terminal_groups: Iterable[_TerminalIdGroup],
    ) -> Iterable[Iterable[_PathGroup]]:
        return itertools.chain.from_iterable(
            self._disjoint_paths_among(terminal_groups, sources)
            for sources in source_groups
        )

    def _disjoint_paths_among(
        self, terminal_groups: Iterable[_TerminalIdGroup], source_ids: _SourceIdGroup
    ) -> Iterable[Iterable[_PathGroup]]:
        shortest_path_groups = [
            self._shortest_paths_between(source_id, terminal_ids)
            for source_id, terminal_ids in zip(source_ids, terminal_groups)
        ]
        # If terminal groups intersect, then the corresponding path groups
        # cannot be disjoint since they intersect at the terminals.  Merging
        # such groups first admits a simple check for disjointedness of the
        # remaining groups.
        merged_path_groups = _merge_path_groups_with_intersecting_terminals(
            shortest_path_groups, terminal_groups
        )
        return filter(_path_groups_are_disjoint, lazy_product(*merged_path_groups))

    def _shortest_paths_between(
        self, source_id: NodeId, terminal_ids: _TerminalIdGroup
    ) -> Iterable[_PathGroup]:
        search_graph = self._graph.make_search_graph_for(terminal_ids)
        independent_paths = [
            search_graph.shortest_paths_between(source_id, terminal_id)
            for terminal_id in terminal_ids
        ]
        return lazy_product(*independent_paths)


class _GraphSearcher:
    def __init__(self, graph: StationGraph):
        self._graph = graph

    def ascending_distance_sources_of(self, terminal_id: NodeId) -> _SourceIdGroup:
        nodes = self._graph.breadth_first_nodes_from(terminal_id, reverse=True)
        is_a_source = _BreadthFirstSourcePredicate(self._graph)
        return filter(is_a_source, nodes)

    def distance_between(self, source_id: NodeId, terminal_id: NodeId) -> int:
        shortest_paths = self._graph.shortest_paths_between(source_id, terminal_id)
        return len(tuple(next(shortest_paths)))


class _BreadthFirstSourcePredicate:
    """
    When used in conjunction with a breadth-first search, this predicate
    identifies eligible source nodes in the given `StationGraph` object.
    """

    def __init__(self, graph: StationGraph):
        self._graph = graph
        self._visited_non_sources: Set[str] = set()

    def __call__(self, node: NodeId) -> bool:
        if self._has_a_source_ancestor(node) or hasattr(
            self._graph[node], "is_eligible_source"
        ):
            return True

        self._visited_non_sources.add(node)
        return False

    def _has_a_source_ancestor(self, node: NodeId) -> bool:
        predecessors = set(self._graph.predecessors_of(node))
        return len(predecessors - self._visited_non_sources) == 0


def _intersection_of(*iterables: Iterable) -> Iterable:
    return set.intersection(*map(set, iterables))


def _path_groups_are_disjoint(path_groups: Iterable[_PathGroup]) -> bool:
    node_groups = (_nodes_in_path_group(paths) for paths in path_groups)
    nodes = tuple(itertools.chain(*node_groups))
    return len(nodes) == len(set(nodes))


def _merge_path_groups_with_intersecting_terminals(
    path_groups_list: Sequence[Iterable[_PathGroup]],
    terminal_groups: Iterable[_TerminalIdGroup],
) -> Iterable[Iterable[_PathGroup]]:
    disjoint_partition_indexes = _disjoint_partition_indexes_of(terminal_groups)
    path_groups_list_folded_by_terminal_intersections = [
        (path_groups_list[index] for index in indexes)
        for indexes in disjoint_partition_indexes
    ]
    return map(
        _path_group_product_of, path_groups_list_folded_by_terminal_intersections
    )


_T = TypeVar("_T")


def _path_group_product_of(
    path_groups_iterable: Iterable[Iterable[_PathGroup]],
) -> Iterable[_PathGroup]:
    def flatten(folded_paths: Iterable[Iterable[_T]]) -> Tuple[_T, ...]:
        return tuple(itertools.chain(*folded_paths))

    return map(flatten, lazy_product(*path_groups_iterable))


def _disjoint_partition_indexes_of(
    groups: Iterable[Iterable[Hashable]],
) -> Sequence[Sequence[int]]:
    partition: _DisjointPartition[int] = _DisjointPartition()
    sets = (set(elements) for elements in groups)
    for index, elements in enumerate(sets):
        partition.insert(elements, key=index)
    return tuple(partition.keys())


THashable = TypeVar("THashable", bound=Hashable)


class _DisjointPartition(Generic[THashable]):
    """
    Maintains a partition of sets with the following properties:
    1. The set union corresponding to each part of the partition is disjoint from all other parts.
    2. The number of parts is maximized, subject to the first constaint.

    This data structure has behavioral similarities to the union-find (aka disjoint-set) data structure.
    A key feature an difference is that `DisjointPartition` preserves the set identifiers for each
    part of the partition.
    """

    @staticmethod
    def _union_key_of(
        new_key: THashable, *existing_keys: Tuple[THashable, ...]
    ) -> Tuple[THashable, ...]:
        return tuple(itertools.chain([new_key], *existing_keys))

    def __init__(self) -> None:
        self._partition: Dict[Tuple[THashable, ...], Set] = {}

    def insert(self, elements: Set, key: THashable) -> Tuple[THashable, ...]:
        intersecting_sets = self._sets_that_intersect_with(elements)
        union_key = self._union_key_of(key, *intersecting_sets.keys())
        self._partition[union_key] = set.union(elements, *intersecting_sets.values())
        for intersecting_key in intersecting_sets:
            del self._partition[intersecting_key]
        return union_key

    def keys(self) -> Iterable[Tuple[THashable, ...]]:
        return self._partition.keys()

    def values(self) -> Iterable[Set]:
        return self._partition.values()

    def _sets_that_intersect_with(
        self, elements: Set
    ) -> Dict[Tuple[THashable, ...], Set]:
        return {
            key: partitioned_set
            for key, partitioned_set in self._partition.items()
            if len(partitioned_set & elements) > 0
        }


def _nodes_in_path_group(paths: _PathGroup) -> Set[NodeId]:
    return set(itertools.chain(*paths))


T = TypeVar("T")


@overload
def _tuple_wrap(thing: NodeId) -> Tuple[NodeId]:
    ...


@overload
def _tuple_wrap(thing: Iterable[T]) -> Tuple[T, ...]:
    ...


def _tuple_wrap(
    thing: Union[NodeId, Iterable[T]]
) -> Union[Tuple[NodeId], Tuple[T, ...]]:
    if isinstance(thing, NodeId):
        return (thing,)
    return tuple(thing)


def _log_connections(
    source_ids: Sequence[Sequence[NodeId]], terminal_ids: Sequence[Sequence[NodeId]]
) -> None:

    for i, terminals in enumerate(terminal_ids):
        potential_sources = [sources[i] for sources in source_ids]
        _LOG.info(
            f"Connecting terminals: {terminals} to one of the sources: {potential_sources}"
        )
