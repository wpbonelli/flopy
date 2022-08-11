from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1.inset_locator import zoomed_inset_axes
from mpl_toolkits.axes_grid1.inset_locator import mark_inset

import pytest

from flopy.utils.triangle import Triangle
from flopy.utils.voronoi import VoronoiGrid


def test_get_sorted_vertices():
    verts = np.array([[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2], [2, 0], [2, 1], [2, 2]])
    iverts = np.array([[0, 1, 3], [3, 4, 1], [1, 2, 4], [2, 4, 5], [3, 4, 6], [4, 6, 7], [4, 5, 7], [5, 7, 8]])

    # TODO: test sorting


def test_sort_vertices():
    verts = np.array([[0, 0], [0, 1], [0, 2], [1, 0], [1, 1], [1, 2], [2, 0], [2, 1], [2, 2]])
    iverts = np.array([[0, 1, 3], [3, 4, 1], [1, 2, 4], [2, 4, 5], [3, 4, 6], [4, 6, 7], [4, 5, 7], [5, 7, 8]])

    # TODO: test sorting


@pytest.fixture
def rectangular_triangle(tmpdir):
    # set domain extents
    xmin = 0.0
    xmax = 2000.0
    ymin = 0.0
    ymax = 1000.0

    # set minimum angle
    angle_min = 30

    # set maximum area
    area_max = 1000.0

    delr = area_max ** 0.5
    ncol = xmax / delr
    nrow = ymax / delr
    nodes = ncol * nrow

    tri = Triangle(maximum_area=area_max, angle=angle_min, model_ws=str(tmpdir))
    poly = np.array(((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax)))
    tri.add_polygon(poly)
    tri.build(verbose=False)

    return tri


def test_double_vertices(rectangular_triangle):
    tmpdir = Path(rectangular_triangle.model_ws)
    voronoi_grid = VoronoiGrid(rectangular_triangle)

    fig = plt.figure(figsize=(10, 10))
    ax = plt.subplot(1, 1, 1, aspect="equal")
    voronoi_grid.plot(ax=ax, facecolor="none")

    cell = voronoi_grid.iverts[1377]
    cell_verts = voronoi_grid.verts[cell]
    cell_x, cell_y = zip(*cell_verts)

    pad = 10
    axins = zoomed_inset_axes(ax, 4, loc=1)
    axins.set_xlim(min(cell_x) - pad, max(cell_x) + pad)
    axins.set_ylim(min(cell_y) - pad, max(cell_y) + pad)
    mark_inset(ax, axins, loc1=2, loc2=4)

    plt.draw()
    plt.show()


@pytest.fixture
def circle_triangle(tmpdir):
    theta = np.arange(0.0, 2 * np.pi, 0.2)
    radius = 100.0
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    circle_poly = [(x, y) for x, y in zip(x, y)]

    tri = Triangle(maximum_area=1500, angle=30, model_ws=str(tmpdir))
    tri.add_polygon(circle_poly)
    tri.build(verbose=False)

    return tri


def test_circle_triangle_case(circle_triangle):
    tmpdir = Path(circle_triangle.model_ws)
    vor = VoronoiGrid(circle_triangle)
