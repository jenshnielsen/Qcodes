from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Union

from typing_extensions import Protocol

from qcodes.instrument.base import InstrumentBase

from .parameter_predicates import (
    has_constant_meter_name,
    has_constant_source_name,
    is_settable,
)

if TYPE_CHECKING:
    from .graph import Node


class _VarargsNodeAppraiser(Protocol):
    def __call__(self, *nodes: Node) -> int:
        pass


SingleNodeAppraiser = Callable[[Node], int]


NodeAppraiser = Union[
    SingleNodeAppraiser,
    Callable[[Node, Node], int],
    Callable[[Node, Node, Node], int],
    _VarargsNodeAppraiser,
]

_NodePredicate = Callable[[Node], bool]


def always_true(*_: Node) -> bool:
    return True


def source_count_of_node(node: Node) -> int:
    return sum(is_settable(parameter) for parameter in node.parameters)


def meter_count_of_node(node: Node) -> int:
    return sum(hasattr(parameter, "get") for parameter in node.parameters) and not any(
        is_settable(parameter) for parameter in node.parameters
    )


def node_is_source(node: Node) -> bool:
    return source_count_of_node(node) > 0


def node_is_meter(node: Node) -> bool:
    return meter_count_of_node(node) > 0


def node_has_unit(*units: Optional[str]) -> _NodePredicate:
    return lambda node: any(parameter.unit in units for parameter in node.parameters)


def node_has_parameter_from_instrument_named(name: str) -> _NodePredicate:
    return lambda node: any(
        parameter.instrument.full_name == name
        for parameter in node.parameters
        if parameter.instrument is not None
    )


def node_has_parameter_name(*names: str) -> _NodePredicate:
    return lambda node: any(parameter.name in names for parameter in node.parameters)


def node_is_constant_source(node: Node) -> bool:
    return any(has_constant_source_name(parameter) for parameter in node.parameters)


def node_is_constant_meter(node: Node) -> bool:
    return any(has_constant_meter_name(parameter) for parameter in node.parameters)


def node_is_source_with_name(name: str, unit: Optional[str] = None) -> _NodePredicate:
    has_name = node_has_parameter_name(name)
    has_unit = node_has_unit(unit)
    return lambda node: has_name(node) and node_is_source(node) and has_unit(node)


def node_is_meter_with_name(name: str, unit: Optional[str] = None) -> _NodePredicate:
    has_name = node_has_parameter_name(name)
    has_unit = node_has_unit(unit)
    return lambda node: has_name(node) and node_is_meter(node) and has_unit(node)


def node_is_instrument(instrument: InstrumentBase) -> _NodePredicate:
    def node_is_instrument_inner(node: Node) -> bool:
        parameters = list(node.parameters)
        if len(parameters) == 0:
            raise TypeError(
                f"Cannot determine the instrument of "
                f"node {node} that has no parameters."
            )
        return any(parameter.instrument is instrument for parameter in parameters)

    return node_is_instrument_inner


def node_is_general_ground(unit: Optional[str]) -> _NodePredicate:
    return node_is_source_with_name("ground", unit=unit)


node_is_ground = node_is_general_ground("V")
