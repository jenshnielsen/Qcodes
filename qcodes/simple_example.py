from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from typing_extensions import reveal_type

from qcodes.parameters import Parameter
from qcodes.tests.instrument_mocks import DummyBase


class DummyInstrument(DummyBase):
    def __init__(
        self,
        name: str = "dummy",
        gates: Sequence[str] = ("dac1", "dac2", "dac3"),
        **kwargs: Any,
    ):
        """
        Create a dummy instrument that can be used for testing

        Args:
            name: name for the instrument
            gates: list of names that is used to create parameters for
                            the instrument
        """
        super().__init__(name, **kwargs)
        self.myparameter = Parameter(
            "myparameter", get_cmd=None, set_cmd=None, initial_value=0, instrument=self
        )


if __name__ == "__main__":
    instr = DummyInstrument("instr")

    reveal_type(instr.myparameter)

    reveal_type(instr.myparameter.instrument)
