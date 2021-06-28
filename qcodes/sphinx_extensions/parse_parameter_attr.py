import inspect
from typing import Any

from sphinx.util.inspect import safe_getattr

from qcodes.instrument.base import Instrument, InstrumentBase


def qcodes_parameter_attr_getter(object: Any, name: str, *default: Any) -> Any:
    if (
        inspect.isclass(object)
        and issubclass(object, InstrumentBase)
        and "resolution" in name
    ):
        print(f"Getting attribute {name} on {object}")
        return safe_getattr(object, name, default)
    else:
        return safe_getattr(object, name, default)


def setup(app):
    """Called by sphinx to setup the extension."""
    app.setup_extension("sphinx.ext.autodoc")  # Require autodoc extension

    app.add_autodoc_attrgetter(object, qcodes_parameter_attr_getter)
    # app.connect("autodoc-process-signature", clear_parameter_method_signature)

    return {
        "version": "0.1",
        "parallel_read_safe": True,  # Not tested, should not be an issue
        "parallel_write_safe": True,  # Not tested, should not be an issue
    }
