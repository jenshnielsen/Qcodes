"""
Tests for connections that QCoDeS opens on behalf of a DataSet or an
Experiment: they are released when no longer needed, closed when their owner
is garbage collected, and transparently reopened when needed again.
"""

from __future__ import annotations

import gc
import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import numpy as np
import pytest

from qcodes.dataset import (
    Measurement,
    close_all_connections,
    connect,
    get_open_connections,
    load_by_id,
    new_experiment,
)
from qcodes.dataset.data_set import DataSet
from qcodes.dataset.experiment_container import Experiment
from qcodes.parameters import Parameter

if TYPE_CHECKING:
    from pathlib import Path


def _run_measurement() -> int:
    x = Parameter("x", set_cmd=None, get_cmd=None)
    y = Parameter("y", set_cmd=None, get_cmd=None)
    meas = Measurement()
    meas.register_parameter(x)
    meas.register_parameter(y, setpoints=(x,))
    with meas.run() as datasaver:
        for v in np.linspace(0, 1, 5):
            datasaver.add_result((x, v), (y, 2 * v))
    return datasaver.run_id


@pytest.mark.usefixtures("experiment")
def test_dataset_connection_is_released_after_measurement() -> None:
    x = Parameter("x", set_cmd=None, get_cmd=None)
    meas = Measurement()
    meas.register_parameter(x)
    with meas.run() as datasaver:
        datasaver.add_result((x, 1))
        ds = datasaver.dataset
        assert isinstance(ds, DataSet)
        conn = ds.conn
        assert not conn.closed

    assert conn.closed
    assert conn not in get_open_connections()


@pytest.mark.usefixtures("experiment")
def test_released_dataset_connection_is_reopened_on_use() -> None:
    run_id = _run_measurement()
    ds = load_by_id(run_id)
    assert isinstance(ds, DataSet)
    data = ds.get_parameter_data()

    close_all_connections()

    np.testing.assert_array_equal(ds.get_parameter_data()["y"]["y"], data["y"]["y"])
    assert ds.conn in get_open_connections()


@pytest.mark.usefixtures("experiment")
def test_connection_is_closed_when_owner_is_garbage_collected() -> None:
    run_id = _run_measurement()
    ds = load_by_id(run_id)
    assert isinstance(ds, DataSet)
    conn = ds.conn
    assert not conn.closed

    del ds
    gc.collect()

    assert conn.closed


@pytest.mark.usefixtures("empty_temp_db")
def test_experiment_connection_is_reopened() -> None:
    exp = new_experiment("exp", sample_name="sample")
    exp.conn.close()

    assert exp.name == "exp"
    assert not exp.conn.closed


@pytest.mark.usefixtures("empty_temp_db")
def test_shared_connection_is_reopened_by_borrower() -> None:
    exp = new_experiment("exp", sample_name="sample")
    meas = Measurement(exp=exp)
    x = Parameter("x", set_cmd=None, get_cmd=None)
    meas.register_parameter(x)
    with meas.run() as datasaver:
        datasaver.add_result((x, 1))
    ds = datasaver.dataset
    assert isinstance(ds, DataSet)
    assert ds.conn is exp.conn

    # closing the connection, as the experiment's finalizer would, must not
    # break the dataset that borrowed it
    exp.conn.close()
    del exp
    gc.collect()

    assert ds.exp_name == "exp"
    assert not ds.conn.closed


def test_user_supplied_connection_is_not_reopened(tmp_path: Path) -> None:
    conn = connect(tmp_path / "temp.db")
    exp = Experiment(name="exp", sample_name="sample", conn=conn)

    conn.close()

    with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
        _ = exp.name


def test_user_supplied_connection_is_not_closed_with_owner(tmp_path: Path) -> None:
    with closing(connect(tmp_path / "temp.db")) as conn:
        exp = Experiment(name="exp", sample_name="sample", conn=conn)
        del exp
        gc.collect()

        assert not conn.closed


def test_reopening_does_not_create_a_deleted_database(tmp_path: Path) -> None:
    db_path = tmp_path / "temp.db"
    exp = Experiment(name="exp", sample_name="sample", path_to_db=str(db_path))
    exp.conn.close()
    db_path.unlink()

    with pytest.raises(sqlite3.OperationalError, match="unable to open database"):
        _ = exp.conn

    assert not db_path.exists()
