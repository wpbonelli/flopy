"""
Three different methods to calculate point in polygon intersections
using ray casting are included in this python script. ray casting is a grid
independent method to perform point in polygon intersections:

point_in_polygon() : intesects an array of points with a single polygon
    and returns the points within that polygon
point_in_polygon2() : intersects a point with an entire set of polygons (whole
    model grid) and returns the node number the point intersects with
point_in_polygon3() : intersects an array of points with the entire set of
    polygons (whole model grid) and returns particle_numbers and the associated
    node number it is in.
"""
import numpy as np
import pytest
from pytest_cases import parametrize_with_cases

from flopy.discretization import StructuredGrid


def point_in_polygon(pxs, pys, xverts, yverts):
    """
    Use the ray casting algorithm to determine if a point
    is within a polygon.

    Limitation: computation time scales with number of grid cells

    Parameters
    ----------
    xc : np.ndarray
        2d array of xpoints
    yc : np.ndarray
        2d array of ypoints
    polygon : iterable (list)
        polygon vertices [(x0, y0),....(xn, yn)]
        note: must be closed

    Returns
    -------
    mask: np.array
        True value means point is in polygon!

    """
    ray_count = np.zeros(pxs.shape, dtype=int)
    num = len(xverts)
    j = num - 1
    for i in range(num):
        tmp = xverts[i] + (xverts[j] - xverts[i]) * (
            pys - yverts[i]
        ) / (yverts[j] - yverts[i])

        comp = np.where(
            ((yverts[i] > pys) ^ (yverts[j] > pys)) & (pxs < tmp)
        )

        j = i
        if len(comp[0]) > 0:
            ray_count[comp[0]] += 1

    mask = np.ones(pxs.shape, dtype=bool)
    mask[ray_count % 2 == 0] = False

    particles = np.where(mask)
    if len(particles[0]) > 0:
        return particles[0]


def point_in_polygon2(point, xverts, yverts):
    """
    Point in polygon calculation for calculating which
    grid cell a single point is in on a modelgrid. This
    works with unstructured grids, however xverts and yverts
    need to be conditioned by appending xvert[0] and yvert[0]
    up to the maximum number of verts a single cell has

    Fast method to find the polygon a particle is in on a grid.
    Limitation: computation time scales with number of particles

    Parameters
    ----------
    point : iterable
        x, y location of point
    xverts : np.array
        nverts, ncpl numpy array of x-vertices of grid cells
    yverts : np.array
        nverts, ncpl numpy array of y-vertices of grid cells

    Returns
    -------

    """
    px = point[0]
    py = point[1]

    # these are closed polygon vertices
    xverts = xverts.T
    yverts = yverts.T

    ray_count = np.zeros((xverts.shape[-1],), dtype=int)

    num = len(xverts)
    j = num - 1
    for i in range(num):
        # do point in polygon comparison
        tmp = xverts[i, :] + (xverts[j, :] - xverts[i, :]) * (
            py - yverts[i, :]
        ) / (yverts[j, :] - yverts[i, :])

        comp = np.where(
            ((yverts[i, :] > py) ^ (yverts[j, :] > py)) & (px < tmp)
        )

        j = i
        if len(comp[0]) > 0:
            ray_count[comp[0]] += 1

    mask = np.ones(ray_count.shape, dtype=bool)
    mask[ray_count % 2 == 0] = False

    node = np.where(mask)

    # return node if point is not outside the grid boundaries
    if len(node[0] > 0):
        return node[0][0]


def point_in_polygon3(points, xverts, yverts):
    """
    Point in polygon calculation for calculating which
    grid cell a single point is in on a modelgrid. This
    works with unstructured grids, however xverts and yverts
    need to be conditioned by appending xvert[0] and yvert[0]
    up to the maximum number of verts a single cell has

    Limitation: Memory limited method. Slower than point in polygon 2

    Parameters
    ----------
    points : np.array
        npoints [x, y] locations of points
    xverts : np.array
        nverts, ncpl numpy array of x-vertices of grid cells
    yverts : np.array
        nverts, ncpl numpy array of y-vertices of grid cells

    Returns
    -------

    """
    px = np.expand_dims(points[:, 0], axis=1)
    py = np.expand_dims(points[:, 1], axis=1)

    # these are closed polygon vertices
    xverts = xverts.T
    yverts = yverts.T

    px = np.zeros((px.size, xverts.shape[1])) + px
    py = np.zeros((py.size, yverts.shape[1])) + py

    ray_count = np.zeros(px.shape, dtype=int)

    num = len(xverts)
    j = num - 1
    for i in range(num):
        # do point in polygon comparison
        tmp = xverts[i, :] + (xverts[j, :] - xverts[i, :]) * (
                py - yverts[i, :]
        ) / (yverts[j, :] - yverts[i, :])

        comp = np.where(
            ((yverts[i, :] > py) ^ (yverts[j, :] > py)) & (px < tmp)
        )

        j = i
        if len(comp[0]) > 0:
            ray_count[comp[0], comp[1]] += 1

    mask = np.ones(ray_count.shape, dtype=bool)
    mask[ray_count % 2 == 0] = False

    imap = np.where(mask)

    # return node if point is not outside the grid boundaries
    if len(imap[0] > 0):
        return imap


class GridCases:
    def structured_small(self):
        nrow = 100
        ncol = 100
        size = nrow * ncol
        delc = np.full((nrow,), 30)
        delr = np.full((ncol,), 30)
        top = np.ones((nrow, ncol))
        botm = np.zeros((1, nrow, ncol))
        idomain = np.ones((1, nrow, ncol))
        grid = StructuredGrid(delc=delc, delr=delr, top=top, botm=botm, idomain=idomain)
        return grid

    def structured_large(self):
        nrow = 1000
        ncol = 100
        size = nrow * ncol
        delc = np.full((nrow,), 30)
        delr = np.full((ncol,), 30)
        top = np.ones((nrow, ncol))
        botm = np.zeros((1, nrow, ncol))
        idomain = np.ones((1, nrow, ncol))
        grid = StructuredGrid(delc=delc, delr=delr, top=top, botm=botm, idomain=idomain)
        return grid


@parametrize_with_cases("grid", GridCases, prefix="structured")
@pytest.mark.parametrize("particles", [1, 1000])
def test_raycast_method1_structured(grid, particles, benchmark):
    # get grid vertex & center locations
    xcenters = grid.xcellcenters.ravel()
    ycenters = grid.ycellcenters.ravel()
    xverts, yverts = grid.cross_section_vertices

    # select random locations to test
    test_nodes = np.random.randint(0, grid.size, size=particles)

    # get point coordinates
    points = np.array([[xcenters[n], ycenters[n]] for n in test_nodes])
    pxs = points.T[0]
    pys = points.T[1]

    # run/benchmark the method
    calc_nodes = np.full((particles,), np.nan, dtype=int)
    def bm():
        for ix, xvert in enumerate(xverts):
            yvert = yverts[ix]
            calc_parts = point_in_polygon(pxs, pys, xvert, yvert)
            if calc_parts is not None:
                calc_nodes[calc_parts] = ix
    benchmark(bm)

    for ix, calc_node in enumerate(calc_nodes):
        assert calc_node == test_nodes[ix]


@parametrize_with_cases("grid", GridCases, prefix="structured")
@pytest.mark.parametrize("particles", [1, 1000])
def test_raycast_method2_structured(grid, particles, benchmark):
    # get grid vertex & center locations
    xcenters = grid.xcellcenters.ravel()
    ycenters = grid.ycellcenters.ravel()
    xverts, yverts = grid.cross_section_vertices

    # select random locations to test
    test_nodes = np.random.randint(0, grid.size, size=particles)

    # run/benchmark the method
    calc_nodes = []
    def bm():
        for n in test_nodes:
            point = [xcenters[n], ycenters[n]]
            calc_node = point_in_polygon2(point, xverts, yverts)
            calc_nodes.append(calc_node)
    benchmark(bm)

    for ix, calc_node in enumerate(calc_nodes):
        assert calc_node == test_nodes[ix]


@parametrize_with_cases("grid", GridCases, prefix="structured")
@pytest.mark.parametrize("particles", [1, 1000])
def test_raycast_method3_structured(grid, particles, benchmark):
    # get grid vertex & center locations
    xcenters = grid.xcellcenters.ravel()
    ycenters = grid.ycellcenters.ravel()
    xverts, yverts = grid.cross_section_vertices

    # select random locations to test
    test_nodes = np.random.randint(0, grid.size, size=particles)

    # run/benchmark the method
    calc_nodes = []
    def bm():
        for n in test_nodes:
            point = [xcenters[n], ycenters[n]]
            calc_node = point_in_polygon3(point, xverts, yverts)
            calc_nodes.append(calc_node)
    benchmark(bm)

    for ix, calc_node in enumerate(calc_nodes):
        assert calc_node == test_nodes[ix]
