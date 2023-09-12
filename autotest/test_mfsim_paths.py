"""
Test various path-management-related scenarios for MFSimulation
"""


import os
from shutil import copytree
import pytest
import platform
from modflow_devtools.markers import requires_exe
from modflow_devtools.misc import set_dir

from flopy.mf6 import MFSimulation, ModflowTdis, ModflowGwf


pytestmark = pytest.mark.mf6


def to_win_sep(s):
    return s.replace("/", "\\")


def to_posix_sep(s):
    return s.replace("\\", "/")


def to_os_sep(s):
    return s.replace("\\", os.sep).replace("/", os.sep)


@requires_exe("mf6")
def test_load_and_run_sim_when_namefile_uses_filenames(
    function_tmpdir, example_data_path
):
    ws = function_tmpdir / "ws"
    ml_name = "freyberg"
    nam_name = "mfsim.nam"
    nam_path = ws / nam_name
    copytree(example_data_path / f"mf6-{ml_name}", ws)

    sim = MFSimulation.load(nam_name, sim_ws=ws)
    sim.check()
    success, buff = sim.run_simulation(report=True)
    assert success


@requires_exe("mf6")
def test_load_and_run_sim_when_namefile_uses_abs_paths(
    function_tmpdir, example_data_path
):
    ws = function_tmpdir / "ws"
    ml_name = "freyberg"
    nam_name = "mfsim.nam"
    nam_path = ws / nam_name
    copytree(example_data_path / f"mf6-{ml_name}", ws)

    with set_dir(ws):
        lines = open(nam_path).readlines()
        with open(nam_path, "w") as f:
            for l in lines:
                pattern = f"{ml_name}."
                if pattern in l:
                    l = l.replace(
                        pattern, str(ws.absolute()) + os.sep + pattern
                    )
                f.write(l)

    sim = MFSimulation.load(nam_name, sim_ws=ws)
    sim.check()
    success, buff = sim.run_simulation(report=True)
    assert success


@requires_exe("mf6")
@pytest.mark.parametrize("sep", ["win", "posix"])
def test_load_and_run_sim_when_namefile_uses_rel_paths(
    function_tmpdir, example_data_path, sep
):
    ws = function_tmpdir / "ws"
    ml_name = "freyberg"
    nam_name = "mfsim.nam"
    nam_path = ws / nam_name
    copytree(example_data_path / f"mf6-{ml_name}", ws)

    with set_dir(ws):
        lines = open(nam_path).readlines()
        with open(nam_path, "w") as f:
            for l in lines:
                pattern = f"{ml_name}."
                if pattern in l:
                    if sep == "win":
                        l = to_win_sep(
                            l.replace(
                                pattern, "../" + ws.name + "/" + ml_name + "."
                            )
                        )
                    else:
                        l = to_posix_sep(
                            l.replace(
                                pattern, "../" + ws.name + "/" + ml_name + "."
                            )
                        )
                f.write(l)

    sim = MFSimulation.load(nam_name, sim_ws=ws)
    sim.check()

    # don't run simulation with Windows sep on Linux or Mac
    if sep == "win" and platform.system() != "Windows":
        return

    success, buff = sim.run_simulation(report=True)
    assert success


@pytest.mark.skip(reason="currently flopy uses OS-specific path separators")
@pytest.mark.parametrize("sep", ["win", "posix"])
def test_write_simulation_always_writes_posix_path_separators(
    function_tmpdir, example_data_path, sep
):
    ws = function_tmpdir / "ws"
    ml_name = "freyberg"
    nam_name = "mfsim.nam"
    nam_path = ws / nam_name
    copytree(example_data_path / f"mf6-{ml_name}", ws)

    with set_dir(ws):
        lines = open(nam_path).readlines()
        with open(nam_path, "w") as f:
            for l in lines:
                pattern = f"{ml_name}."
                if pattern in l:
                    if sep == "win":
                        l = to_win_sep(
                            l.replace(
                                pattern, "../" + ws.name + "/" + ml_name + "."
                            )
                        )
                    else:
                        l = to_posix_sep(
                            l.replace(
                                pattern, "../" + ws.name + "/" + ml_name + "."
                            )
                        )
                f.write(l)

    sim = MFSimulation.load(nam_name, sim_ws=ws)
    sim.write_simulation()

    lines = open(ws / "mfsim.nam").readlines()
    assert all("\\" not in l for l in lines)


@pytest.mark.parametrize("use_paths", [True, False])
def test_set_sim_path(function_tmpdir, use_paths):
    sim_name = "testsim"
    model_name = "testmodel"
    exe_name = "mf6"

    # set up simulation
    tdis_name = f"{sim_name}.tdis"
    sim = MFSimulation(
        sim_name=sim_name,
        version="mf6",
        exe_name=exe_name,
        sim_ws=function_tmpdir,
    )

    new_ws = function_tmpdir / "new_ws"
    new_ws.mkdir()
    sim.set_sim_path(new_ws if use_paths else str(new_ws))

    tdis_rc = [(6.0, 2, 1.0), (6.0, 3, 1.0)]
    tdis = ModflowTdis(
        sim, time_units="DAYS", nper=2, perioddata=tdis_rc
    )

    # create model instance
    model = ModflowGwf(
        sim, modelname=model_name, model_nam_file=f"{model_name}.nam"
    )

    sim.write_simulation()

    assert len([p for p in function_tmpdir.glob("*") if p.is_file()]) == 0
    assert len([p for p in new_ws.glob("*") if p.is_file()]) > 0
