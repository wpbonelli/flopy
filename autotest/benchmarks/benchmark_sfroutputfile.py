import pytest

from flopy.utils.sfroutputfile import SfrFile


@pytest.mark.benchmark
def test_sfrfile_load(benchmark, example_data_path):
    sfr_file = example_data_path / "freyberg_usg" / "freyberg.usg.sfr"
    benchmark(lambda: SfrFile(str(sfr_file)))


@pytest.mark.fixture
def sfrf(example_data_path) -> SfrFile:
    return SfrFile(str(example_data_path / "freyberg_usg" / "freyberg.usg.sfr"))


@pytest.mark.benchmark
def test_sfrfile_get_nstrm(benchmark, sfrf):
    benchmark(sfrf.get_nstrm)


@pytest.mark.benchmark
def test_sfrfile_get_results(benchmark, sfrf):
    benchmark(sfrf.get_results)


@pytest.mark.benchmark
def test_sfrfile_get_times(benchmark, sfrf):
    benchmark(sfrf.get_times)


@pytest.mark.benchmark
def test_sfrfile_get_dataframe(benchmark, sfrf):
    benchmark(sfrf.get_dataframe)
