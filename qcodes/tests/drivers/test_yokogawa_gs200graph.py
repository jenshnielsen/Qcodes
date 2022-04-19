import pytest

import qcodes.instrument.sims as sims
from qcodes.instrument_drivers.yokogawa.GS200Graph import GS200

VISALIB = sims.__file__.replace("__init__.py", "Yokogawa_GS200.yaml@sim")


@pytest.fixture(scope="function", name="gs200")
def _make_gs200():
    gs200 = GS200("GS200", address="GPIB0::1::INSTR", visalib=VISALIB)
    yield gs200

    gs200.close()


def test_basic_init(gs200):

    idn = gs200.get_idn()
    assert idn["vendor"] == "QCoDeS Yokogawa Mock"
