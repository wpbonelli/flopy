import numpy as np
import pytest

from flopy.mf6.modflow.mfsimulation import MFSimulation
from flopy.modflow.mf import Modflow
from flopy.utils.zonbud import ZoneBudget, ZoneBudget6


def create_zone_array(nlay, nrow, ncol, n_zones=5):
    zones = np.zeros((nlay, nrow, ncol), dtype=np.int32)

    # Create simple zoning pattern
    # Divide grid into roughly equal zones
    zone_width = ncol // n_zones

    for i in range(n_zones):
        start_col = i * zone_width
        end_col = (i + 1) * zone_width if i < n_zones - 1 else ncol
        zones[:, :, start_col:end_col] = i + 1

    return zones


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget_load(benchmark, example_data_path, nzones):
    model_path = example_data_path / "freyberg_multilayer_transient"
    model = Modflow.load(model_path, version="mf2005")
    cbc_path = model_path / "freyberg.cbc"
    zones = create_zone_array(model.nlay, model.nrow, model.ncol, n_zones=nzones)
    benchmark(lambda: ZoneBudget(str(cbc_path), zones, verbose=False))


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget_get_budget(benchmark, example_data_path, nzones):
    model_path = example_data_path / "freyberg_multilayer_transient"
    model = Modflow.load(model_path, version="mf2005")
    cbc_path = model_path / "freyberg.cbc"
    zones = create_zone_array(model.nlay, model.nrow, model.ncol, n_zones=nzones)
    zb = ZoneBudget(str(cbc_path), zones, verbose=False)
    benchmark(zb.get_budget)


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget_get_volumetric_budget(benchmark, example_data_path, nzones):
    model_path = example_data_path / "freyberg_multilayer_transient"
    model = Modflow.load(model_path, version="mf2005")
    cbc_path = model_path / "freyberg.cbc"
    zones = create_zone_array(model.nlay, model.nrow, model.ncol, n_zones=nzones)
    zb = ZoneBudget(str(cbc_path), zones, verbose=False)
    benchmark(zb.get_volumetric_budget)


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget_get_dataframes(benchmark, example_data_path, nzones):
    model_path = example_data_path / "freyberg_multilayer_transient"
    model = Modflow.load(model_path, version="mf2005")
    cbc_path = model_path / "freyberg.cbc"
    zones = create_zone_array(model.nlay, model.nrow, model.ncol, n_zones=nzones)
    zb = ZoneBudget(str(cbc_path), zones, verbose=False)
    benchmark(zb.get_dataframes)


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget6_load(benchmark, example_data_path, nzones):
    sim = MFSimulation.load(sim_ws=example_data_path / "mf6-freyberg")
    gwf = sim.get_model()
    zones = create_zone_array(
        gwf.modelgrid.nlay, gwf.modelgrid.nrow, gwf.modelgrid.ncol, n_zones=nzones
    )
    cbc_path = sim.sim_path / f"{gwf.name}.cbc"
    benchmark(lambda: ZoneBudget6(str(cbc_path), zones, verbose=False))


@pytest.mark.benchmark(min_rounds=2, warmup=False)
@pytest.mark.parametrize("nzones", [3, 10, 50])
def test_zonebudget6_get_budget(benchmark, example_data_path, nzones):
    sim = MFSimulation.load(sim_ws=example_data_path / "mf6-freyberg")
    gwf = sim.get_model()
    zones = create_zone_array(
        gwf.modelgrid.nlay, gwf.modelgrid.nrow, gwf.modelgrid.ncol, n_zones=nzones
    )
    cbc_path = sim.sim_path / f"{gwf.name}.cbc"
    zb = ZoneBudget6(str(cbc_path), zones, verbose=False)
    benchmark(zb.get_budget)
