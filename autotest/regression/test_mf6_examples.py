from pathlib import Path
from shutil import copytree

import pytest
from autotest.conftest import requires_exe
from autotest.regression.conftest import is_nested

from flopy.devtools import compare_heads
from flopy.mf6 import MFSimulation

pytestmark = pytest.mark.mf6


@requires_exe("mf6")
@pytest.mark.slow
@pytest.mark.regression
def test_mf6_example_simulations(tmpdir, mf6_example_namfiles):
    namfile = Path(mf6_example_namfiles[0])  # pull the first model's namfile
    nested = is_nested(namfile)
    tmpdir = Path(tmpdir / "workspace")
    cmpdir = tmpdir / "compare"
    srcdir = namfile.parent.parent if nested else namfile.parent

    print(
        f"Running example scenario {srcdir.name} with {len(mf6_example_namfiles)} model(s)"
    )

    # copy model files into working directory
    copytree(src=srcdir, dst=tmpdir)

    # run models in order received (should be alphabetical, so gwf precedes gwt)
    for namfile in mf6_example_namfiles:
        namfile_path = Path(namfile).resolve()
        namfile_name = namfile_path.name
        model_path = namfile_path.parent

        # working directory must be named according to the name file's parent (e.g.
        # 'mf6gwf') because coupled models refer to each other with relative paths
        wrkdir = Path(tmpdir / model_path.name) if nested else tmpdir

        # load and run simulation
        sim = MFSimulation.load(
            namfile_name, version="mf6", exe_name="mf6", sim_ws=str(wrkdir)
        )
        success, buff = sim.run_simulation(report=True, silent=True)
        assert success

        # change to comparison workspace, write files and rerun
        sim.simulation_data.mfpath.set_sim_path(str(cmpdir))
        sim.write_simulation()
        success, _ = sim.run_simulation()
        assert success

        # compare heads
        headfiles1 = [p for p in wrkdir.glob("*.hds")]
        headfiles2 = [p for p in cmpdir.glob("*.hds")]
        assert compare_heads(
            None,
            None,
            precision="double",
            text="head",
            files1=[str(p) for p in headfiles1],
            files2=[str(p) for p in headfiles2],
            outfile=str(cmpdir / "head_compare.dat"),
        )
