from qcodes.graph.visulization import draw
from qcodes.instrument_drivers.connector import Connector
from qcodes.station import Station
from qcodes.tests.instrument_mocks import DummyChannelInstrument


def test_basic():
    #  todo fixtures for closing instruments etc
    instr = DummyChannelInstrument("instr")
    conn = Connector(
        "conn",
        connections=({"name": "a", "endpoints": ("instr_ChanC", "instr_ChanB")},),
    )

    station = Station()

    station.add_component(instr)
    station.add_component(conn)
    draw(station._create_station_graph())
