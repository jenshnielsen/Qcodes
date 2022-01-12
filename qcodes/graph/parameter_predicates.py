from qcodes.instrument.parameter import Parameter


def is_settable(parameter: Parameter) -> bool:
    settable = getattr(parameter, "settable", None)
    if settable is not None:
        return settable

    return hasattr(parameter, "set")


def has_constant_source_name(parameter: Parameter) -> bool:
    return parameter.short_name in ("ground", "ground_force", "highz", "float")


def has_constant_meter_name(parameter: Parameter) -> bool:
    return parameter.short_name in ("ground_sense",)
