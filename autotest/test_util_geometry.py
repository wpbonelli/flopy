import numpy as np
import pytest
from autotest.test_grid_cases import GridCases

from flopy.utils.geometry import is_clockwise, point_in_polygon


def test_does_isclockwise_work():
    # Create some points
    verts = []
    verts.append([0, 20.0000, 30.0000])
    verts.append([1, 18.9394, 25.9806])
    verts.append([2, 21.9192, 25.3013])
    verts.append([3, 22.2834, 27.5068])

    # List the points above in counter-clockwise order
    iv = [0, 0, 1, 2, 3]

    # Organize the previous info into lists of x an y data
    xv, yv = [], []
    xyverts = []
    for v in iv[1:]:
        tiv, txv, tyv = verts[v]
        xv.append(txv)
        yv.append(tyv)

    # is_clockwise() should fail and return false
    rslt = is_clockwise(xv, yv)

    assert bool(rslt) is False, "is_clockwise() failed"


def test_point_in_polygon_basic():
    grid = GridCases().structured_small()
    xpts = grid.xcellcenters
    ypts = grid.ycellcenters
    poly = grid.verts[grid.iverts[0]].tolist()
    mask = point_in_polygon(xpts, ypts, poly)
    assert mask.sum() == 1
    assert mask[0, 0] == True
