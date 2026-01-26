"""
Benchmarks for flopy.discretization grid operations including:
- cellid <-> node number conversions
- grid intersection operations
- grid geometry properties
"""

import pytest

from autotest.test_grid_cases import GridCases
from flopy.utils.geometry import LineString, Point

STRUCTURED_GRIDS = {
    "small": GridCases.structured_small(),
    "medium": GridCases.structured_medium(),
    "large": GridCases.structured_large(),
}


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_get_lrc(benchmark, grid):
    nodes = list(range(grid.nnodes))
    benchmark(lambda: grid.get_lrc(nodes))


@pytest.mark.benchmark
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_get_node(benchmark, grid):
    cellids = [
        (lay, row, col)
        for lay in range(grid.nlay)
        for row in range(0, grid.nrow)
        for col in range(0, grid.ncol)
    ]
    benchmark(lambda: grid.get_node(cellids=cellids))


@pytest.mark.benchmark
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_intersect_linestring(benchmark, grid):
    line = LineString([(0, 0), (grid.ncol, grid.nrow)])
    benchmark(lambda: grid.intersect(line, return_all_intersections=True))


@pytest.mark.benchmark
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_intersect_point(benchmark, grid):
    point = Point(50, 50)
    benchmark(lambda: grid.intersect(point))


@pytest.mark.benchmark
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_extent(benchmark, grid):
    benchmark(lambda: grid.extent)


@pytest.mark.benchmark
@pytest.mark.parametrize("grid", STRUCTURED_GRIDS.values(), ids=STRUCTURED_GRIDS.keys())
def test_structured_grid_xyzcellcenters(benchmark, grid):
    benchmark(lambda: grid.xyzcellcenters)
