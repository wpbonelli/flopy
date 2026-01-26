"""
Benchmarks for flopy.utils.Util2d and Util3d operations including:
- Array creation
- External file I/O
- get_file_entry() performance
"""

import numpy as np
import pytest

from flopy.utils import Util2d, Util3d

SIZES = {
    "small": {"nlay": 3, "nrow": 10, "ncol": 10},
    "medium": {"nlay": 10, "nrow": 1000, "ncol": 1000},
    "large": {"nlay": 20, "nrow": 2000, "ncol": 2000},
}


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util2d_create(benchmark, size):
    dims = SIZES[size]
    shape = (dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    benchmark(lambda: Util2d(None, shape, np.float32, data.copy(), "test"))


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util3d_create(benchmark, size):
    dims = SIZES[size]
    shape = (dims["nlay"], dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    benchmark(lambda: Util3d(None, shape, np.float32, data.copy(), "test"))


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util2d_external_write(benchmark, function_tmpdir, size):
    dims = SIZES[size]
    shape = (dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    u2d = Util2d(None, shape, np.float32, data, "test")
    fpath = function_tmpdir / "test_array.dat"

    def write_external():
        u2d.write(str(fpath))
        return u2d

    benchmark(write_external)


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util3d_external_write(benchmark, function_tmpdir, size):
    dims = SIZES[size]
    shape = (dims["nlay"], dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    u3d = Util3d(None, shape, np.float32, data, "test")
    fpath = function_tmpdir / "test_array3d.dat"

    def write_external():
        u3d.write(str(fpath))
        return u3d

    benchmark(write_external)


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util2d_array_copy(benchmark, size):
    dims = SIZES[size]
    shape = (dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    u2d = Util2d(None, shape, np.float32, data, "test")
    benchmark(lambda: u2d.array.copy())


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("size", ["small", "medium", "large"])
def test_util3d_array_copy(benchmark, size):
    dims = SIZES[size]
    shape = (dims["nlay"], dims["nrow"], dims["ncol"])
    data = np.random.random(shape)
    u3d = Util3d(None, shape, np.float32, data, "test")
    benchmark(lambda: u3d.array.copy())
