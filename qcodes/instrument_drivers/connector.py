import re
from difflib import get_close_matches
from typing import Any, Sequence, Tuple

from typing_extensions import NotRequired, TypedDict

from qcodes.graph.graph import (
    BasicEdge,
    ConnectorNode,
    EdgeStatus,
    EdgeType,
    MutableStationGraph,
    StationGraph,
)
from qcodes.instrument.base import Instrument


class ConnectorMapping(TypedDict):
    name: NotRequired[str]
    endpoints: Tuple[str, str]
    ohms: NotRequired[float]


class Connector(Instrument):
    """
    Connector is an instrument with the primary purpose of creating static connections among other
    instruments.  Examples include cables and daughterboards. Each Connector may have an arbitrary
    number of "connections".  For example, a 32-pin microD cable will have 32 separate connections. Each
    connection can have an arbitrary number of "endpoints".  The Connector graph contains, for each
    connection, a node for the connection and an (bidirectional) edge between the connection and each of
    its endpoints.

    Wire-like connections will typically have two endpoints, one for each end of the wire.  ConnectorDicts
    can be connected two each other in series.  For example,
    InstrumentA -- ConnectorDict1 -- ConnectorDict2 -- InstrumentB
    In this case, connections for one of the two ConnectorDicts (say ConnectorDict2) will each have two
    endpoints (one for ConnectorDict1 and one for InstrumentB).  The other Connector (ConnectorDict1)
    may have just a single endpoint (InstrumentA) for each connection.  Endpoints to the neighboring
    Connector (ConnectorDict2) may be omitted (since they were already included in ConnectorDict2).


    Args:
        name: Connector/Instrument name
        connections: List of dictionaries holding parameters of the connector

            Dictionary Parameters:
                name: (optional)
                    A unique identifier for each line in the connector.
                    Note that the same names across different connectors is still valid.
                    Format of resultant name will be in the form
                    ``<connector_instrument>["<name>"]``
                endpoints:
                    A tuple of strings, each of which specifies edges to and from the connection.
                ohms: (optional)
                    a resistance value with type int, float

    """

    def __init__(
        self, name: str, connections: Sequence[ConnectorMapping], **kwargs: Any
    ):

        super().__init__(name, **kwargs)
        self._graph = MutableStationGraph()
        self._are_connection_names_unique(connections)
        self._connections = connections
        self._add_subgraph()

    @staticmethod
    def _are_connection_names_unique(connections: Sequence[ConnectorMapping]) -> None:
        names = {
            connection.get("name", str(index))
            for index, connection in enumerate(connections)
        }
        if len(names) != len(connections):
            raise KeyError("Names must have a unique ID")

    def _add_subgraph(self) -> None:
        """
        Function to add a multiterminal graph to a connector that supports routing
        will add something like this to the subgraph:
        --- edge
        O connector node with resistance
        X unknown next/previous nodes
        X---O---X
        """
        for index, dictionary in enumerate(self._connections):
            dict_id = dictionary.get("name", str(index))
            connector_node = f"{self.name}[{dict_id}]"
            name = substitute_non_identifier_characters(f"resistance_{connector_node}")

            self.instrument_graph[connector_node] = ConnectorNode(nodeid=name)
            for endpoint in dictionary["endpoints"]:
                self._add_edges_to_graph(endpoint, connector_node)

    @staticmethod
    def _check_similar_key(name: str, dictionary: ConnectorMapping) -> None:
        """checks to see if a key in the yaml is similar to name"""
        key_list = get_close_matches(name, dictionary.keys())
        if len(key_list) != 0:
            raise ValueError(
                f"{key_list[0]} key is not defined correctly in connection for name, {name}"
            )

    def _add_edges_to_graph(self, node1: str, node2: str) -> None:
        self.instrument_graph[node1, node2] = BasicEdge(
            edge_type=EdgeType.ELECTRICAL_CONNECTION, edge_status=EdgeStatus.INACTIVE
        )
        self.instrument_graph[node2, node1] = BasicEdge(
            edge_type=EdgeType.ELECTRICAL_CONNECTION, edge_status=EdgeStatus.INACTIVE
        )

    def quell(self) -> None:
        pass

    @property
    def instrument_graph(self) -> StationGraph:
        return self._graph


def substitute_non_identifier_characters(
    node_name: str, valid_character: str = "_"
) -> str:
    """
    Substitutes invalid characters based on the constraint node_name.isidentifier()
    """
    return re.sub("[^0-9a-zA-Z_]", valid_character, node_name)
