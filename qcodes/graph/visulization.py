"""
Utils for visualizing StationGraphs. Note that these only work in
Jupyter and require you to have ipycytoscape installed. This can be
installed with ``pip install qchar[live_plotting]``
"""
import ipycytoscape
import ipywidgets
import networkx as nx

from .graph import StationGraph

DEFAULT_STYLE = [
    {
        "selector": "node",
        "css": {
            "content": "data(id)",
            "text-valign": "center",
            "color": "white",
            "text-outline-width": 2,
            "text-outline-color": "#11479e",
            "background-color": "#11479e",
        },
    },
    {
        "selector": ":selected",
        "css": {
            "background-color": "black",
            "line-color": "black",
            "target-arrow-color": "black",
            "source-arrow-color": "black",
            "text-outline-color": "black",
        },
    },
    {"selector": "edge", "style": {"width": 4, "line-color": "#9dbaea"}},
    {
        "selector": "edge.directed.Edge_Active",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#9dbaea",
        },
    },
    {
        "selector": "edge.directed.Edge_Inactive",
        "style": {
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "red",
            "line-color": "red",
        },
    },
    {"selector": "edge.multiple_edges", "style": {"curve-style": "bezier"}},
]


def _set_default_style_and_layout(graphwidget: ipycytoscape.CytoscapeWidget) -> None:
    graphwidget.user_zooming_enabled = True
    graphwidget.set_style(DEFAULT_STYLE)
    graphwidget.min_zoom = 0.2
    graphwidget.max_zoom = 5
    graphwidget.set_layout(name="cola", avoidOverlap=True, maxSimulationTime=4000)
    graphwidget.wheel_sensitivity = 0.1


def draw(station_graph: StationGraph, disjoint: bool = True) -> ipywidgets.HBox:
    """
    Visualize a StationGraph as ipycytoscape widgets.
    These will be returned embedded in an ipywidgets container with
    one or more subwidgets depending on the value of disjoint.

    Args:
        station_graph: A StationGraph object to visualize
        disjoint: Should each disjoint graph be drawn in its own widget?.

    Returns: An ipywidgets container that contains one or more
        individual ipycytoscape widgets.

    """
    graph = station_graph._graph  # pylint: disable=W0212
    return _draw_networkx_graph(graph, disjoint=disjoint)


def _draw_networkx_graph(graph: nx.DiGraph, disjoint: bool = True) -> ipywidgets.HBox:
    """
    Create an Cytoscape graphwidget from a networkx style graph.
    """

    temp_graph = _create_cytoscape_compatible_graph(graph)

    if disjoint:
        graphwidgets = []
        components = [
            temp_graph.subgraph(c).copy()
            for c in nx.weakly_connected_components(temp_graph)
        ]
        for component in components:
            graphwidget = ipycytoscape.CytoscapeWidget()
            graphwidget.graph.add_graph_from_networkx(component, directed=True)
            graphwidgets.append(graphwidget)
    else:
        graphwidget = ipycytoscape.CytoscapeWidget()
        graphwidget.graph.add_graph_from_networkx(temp_graph, directed=True)
        graphwidgets = [graphwidget]

    for graphwidget in graphwidgets:
        _set_default_style_and_layout(graphwidget)

    return ipywidgets.HBox(graphwidgets)


def _create_cytoscape_compatible_graph(nxgraph: nx.DiGraph) -> nx.DiGraph:
    """Transform a networkx DiGraph into a format that can better be visualized
    by ipycytoscape"""
    nodes_dict = {}
    cytoscapegraph = nx.DiGraph()
    for node in nxgraph.nodes():
        new_node = CustomNode(node, classes="node")
        nodes_dict[node] = new_node
        cytoscapegraph.add_node(new_node)
    for edge, edgeattrs in nxgraph.edges.items():
        cytoscapegraph.add_edge(nodes_dict[edge[0]], nodes_dict[edge[1]])
        cytoscapegraph[nodes_dict[edge[0]]][nodes_dict[edge[1]]]["classes"] = str(
            edgeattrs["value"]
        ).replace(".", "_")

    return cytoscapegraph


class CustomNode(ipycytoscape.Node):
    """
    A node class that contains the correct information for visualization
    with ipycytoscape
    """

    def __init__(self, name: str, classes: str = ""):
        super().__init__()
        self.data["id"] = name
        self.classes = classes


def show_active_edges(
    station_graph: StationGraph,
    disjoint: bool = True,
) -> ipywidgets.HBox:
    """
    Visualize a StationGraphs active edges as ipycytoscape widgets.
    These will be returned embedded in an ipywidgets container with
    one or more subwidgets depending on the value of disjoint.

    Args:
        station_graph: A StationGraph object to visualize
        disjoint: Should each disjoint graph be drawn in its own widget?.

    Returns: An ipywidgets container that contains one or more
        individual ipycytoscape widgets.

    """

    active_edges = _get_active_edges(station_graph)
    temp_graph = nx.DiGraph()
    for node1, node2 in active_edges:
        temp_graph.add_edge(node1, node2)
    subgraphs = _find_disjoint_subgraphs(temp_graph)

    if not disjoint:
        graphwidget = ipycytoscape.CytoscapeWidget()
        for subgraph in subgraphs:
            graphwidget.graph.add_graph_from_networkx(subgraph, directed=True)
        graphwidgets = [graphwidget]
    else:
        graphwidgets = []
        for subgraph in subgraphs:
            graphwidget = ipycytoscape.CytoscapeWidget()

            graphwidget.graph.add_graph_from_networkx(subgraph, directed=True)
            graphwidgets.append(graphwidget)

    for graphwidget in graphwidgets:
        _set_default_style_and_layout(graphwidget)
    return ipywidgets.HBox(graphwidgets)


def _get_active_edges(graph: StationGraph) -> list:
    active_edges = [
        (str(edge[0]), str(edge[1]))
        for edge in graph.edges
        if graph[edge].active is True
    ]
    return active_edges


def _get_subgraph_edges(graph: nx.DiGraph) -> list:
    edges = [edge for edge in graph.edges if graph.edges[edge] is not None]
    return edges


def _find_disjoint_subgraphs(graph: nx.DiGraph) -> list:
    subgraph_iterator = nx.weakly_connected_components(graph)
    temp_list = list(subgraph_iterator)
    subgraphs = [nx.to_directed(nx.subgraph(graph, subgraph)) for subgraph in temp_list]
    return subgraphs
