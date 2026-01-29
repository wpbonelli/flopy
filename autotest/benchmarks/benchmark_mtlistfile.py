import pytest

from flopy.utils.mtlistfile import MtListBudget


@pytest.mark.benchmark
def test_mtlistfile_load(benchmark, example_data_path):
    list_file = example_data_path / "mt3d_test" / "mf2kmt3d" / "mnw" / "t5.lst"
    benchmark(lambda: MtListBudget(str(list_file)).gw_data)
