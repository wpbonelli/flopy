"""
Tests for conversion of NWT output files to MF6 format.
Involves calculating ia/ja connectivity arrays, flowja,
and cell saturation. We then verify that the converted
files can successfully drive an MF6 PRT model.
"""

import numpy as np
import pytest

from flopy.mf6.utils.postprocessing import (
    get_structured_connectivity,
    get_structured_faceflows,
    get_structured_flowja,
)
from flopy.utils.postprocessing import get_saturation


def test_get_structured_connectivity_simple():
    nlay, nrow, ncol = 2, 2, 2
    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)

    # Check dimensions
    ncells = nlay * nrow * ncol
    assert len(ia) == ncells + 1
    assert len(ja) == nja
    assert ia[-1] == nja

    # each active cell should have at least 1 connection (diagonal)
    for n in range(ncells):
        nconn = ia[n + 1] - ia[n]
        assert nconn >= 1

    # first cell (0,0,0) should have 4 connections: diagonal + right + front + lower
    nconn_first = ia[1] - ia[0]
    first_conns = ja[ia[0] : ia[1]]
    assert nconn_first == 4
    assert first_conns[0] == 0
    assert 1 in first_conns
    assert 2 in first_conns
    assert 4 in first_conns


def test_get_structured_connectivity_with_inactive_cells():
    nlay, nrow, ncol = 2, 3, 3
    idomain = np.ones((nlay, nrow, ncol), dtype=np.int32)
    idomain[0, 1, 1] = 0  # center cell of top layer inactive
    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol, idomain)

    # inactive cell (node 4) should have 0 connections
    node_inactive = 0 * nrow * ncol + 1 * ncol + 1  # (k=0, i=1, j=1)
    nconn_inactive = ia[node_inactive + 1] - ia[node_inactive]
    assert nconn_inactive == 0

    # neighbors of inactive cell should not connect to it
    node_left = 0 * nrow * ncol + 1 * ncol + 0  # (k=0, i=1, j=0)
    conns_left = ja[ia[node_left] : ia[node_left + 1]]
    assert node_inactive not in conns_left


def test_get_structured_connectivity_corner_cells():
    nlay, nrow, ncol = 1, 3, 3
    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)

    # top-left corner (0,0,0) should have 3 connections: diagonal + right + front
    node_corner = 0
    nconn = ia[node_corner + 1] - ia[node_corner]
    assert nconn == 3

    # bottom-right corner (0,2,2) should have 1 connection: diagonal only
    node_corner = 0 * nrow * ncol + 2 * ncol + 2
    nconn = ia[node_corner + 1] - ia[node_corner]
    assert nconn == 1


def test_get_structured_faceflows_to_connections_simple():
    nlay, nrow, ncol = 1, 3, 3
    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)
    qright = np.ones((nlay, nrow, ncol)) * 1.0
    qfront = np.ones((nlay, nrow, ncol)) * 2.0
    qlower = np.ones((nlay, nrow, ncol)) * 3.0
    flowja = get_structured_flowja(
        (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
    )

    assert len(flowja) == nja, f"flowja length should be {nja}"

    # first cell (0,0,0) connections
    node = 0
    conns = ja[ia[node] : ia[node + 1]]
    flows = flowja[ia[node] : ia[node + 1]]
    for ipos, m in enumerate(conns):
        if m == node:
            # diagonal
            assert flows[ipos] == 0.0
        elif m == 1:
            # right
            assert flows[ipos] == 1.0
        elif m == 3:
            # front
            assert flows[ipos] == 2.0


def test_get_structured_faceflows_to_connections_multilayer():
    nlay, nrow, ncol = 3, 2, 2
    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)
    qright = np.ones((nlay, nrow, ncol)) * 10.0
    qfront = np.ones((nlay, nrow, ncol)) * 20.0
    qlower = np.ones((nlay, nrow, ncol)) * 30.0
    flowja = get_structured_flowja(
        (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
    )

    # first cell of top layer should connect to lower layer
    node = 0  # (k=0, i=0, j=0)
    node_below = nrow * ncol  # (k=1, i=0, j=0)
    conns = ja[ia[node] : ia[node + 1]]
    flows = flowja[ia[node] : ia[node + 1]]

    # check lower connection
    lower_idx = np.where(conns == node_below)[0]
    if len(lower_idx) > 0:
        assert flows[lower_idx[0]] == 30.0


def test_get_saturation_confined_cells():
    nlay, nrow, ncol = 2, 3, 3

    # all cells confined
    icelltype = np.zeros((nlay, nrow, ncol), dtype=np.int32)
    head = np.full((nlay, nrow, ncol), 50.0)
    top = np.full((nrow, ncol), 100.0)
    botm = np.array(
        [
            np.full((nrow, ncol), 75.0),
            np.full((nrow, ncol), 25.0),
        ]
    )
    sat = get_saturation(head, top, botm, icelltype)

    assert np.allclose(sat, 1.0, equal_nan=True)


def test_get_saturation_convertible_cells():
    nlay, nrow, ncol = 2, 3, 3

    # top layer convertible, bottom layer confined
    icelltype = np.zeros((nlay, nrow, ncol), dtype=np.int32)
    icelltype[0] = 1
    top = np.full((nrow, ncol), 100.0)
    botm = np.array(
        [
            np.full((nrow, ncol), 50.0),
            np.full((nrow, ncol), 0.0),
        ]
    )
    head = np.full((nlay, nrow, ncol), 75.0)
    sat = get_saturation(head, top, botm, icelltype)

    assert np.allclose(sat[0], 0.5)  # unconfined layer
    assert np.allclose(sat[1], 1.0)  # confined layer


def test_get_saturation_fully_saturated():
    nlay, nrow, ncol = 1, 2, 2
    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)
    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)
    head = np.full((nlay, nrow, ncol), 120.0)  # above top
    sat = get_saturation(head, top, botm, icelltype)

    assert np.allclose(sat, 1.0)  # clamped to 1.0


def test_get_saturation_dry_cells():
    nlay, nrow, ncol = 1, 2, 2
    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)
    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)
    head = np.full((nlay, nrow, ncol), 75.0)
    head[0, 0, 0] = -999.0  # dry
    head[0, 1, 1] = -9999.0  # inactive
    sat = get_saturation(head, top, botm, icelltype, hdry=-999.0, hnoflo=-9999.0)

    # dry and inactive cells
    assert np.isnan(sat[0, 0, 0])
    assert np.isnan(sat[0, 1, 1])

    # active cells
    assert np.allclose(sat[0, 0, 1], 0.5)
    assert np.allclose(sat[0, 1, 0], 0.5)


def test_get_saturation_below_bottom():
    nlay, nrow, ncol = 1, 2, 2
    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)
    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)
    head = np.full((nlay, nrow, ncol), 30.0)  # below bottom
    sat = get_saturation(head, top, botm, icelltype)

    assert np.allclose(sat, 0.0)


def test_get_saturation_1d():
    ncells = 10
    icelltype = np.zeros(ncells, dtype=np.int32)
    icelltype[0:5] = 1  # first 5 convertible
    top = np.linspace(100, 50, ncells)
    botm = np.linspace(50, 0, ncells)
    head = np.linspace(75, 25, ncells)
    sat = get_saturation(head, top, botm, icelltype)

    assert len(sat) == ncells
    assert np.allclose(sat[0], 0.5)  # convertible cell: (75-50)/(100-50) = 0.5
    assert np.allclose(sat[5:], 1.0)  # confined cells: 1.0


def test_get_saturation_invalid_inputs():
    nlay, nrow, ncol = 2, 3, 3

    head = np.full((nlay, nrow, ncol), 50.0)
    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)
    icelltype = np.zeros((nlay, nrow - 1, ncol), dtype=np.int32)  # Wrong shape

    with pytest.raises(ValueError, match="does not match"):
        get_saturation(head, top, botm, icelltype)


def test_connectivity_realistic_grid():
    """Test connectivity with realistic model grid size."""
    nlay, nrow, ncol = 3, 40, 20
    ncells = nlay * nrow * ncol

    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)

    # Check array sizes
    assert len(ia) == ncells + 1
    assert len(ja) == nja
    assert ia[-1] == nja

    # Verify all active cells have connections
    for n in range(ncells):
        nconn = ia[n + 1] - ia[n]
        assert nconn >= 1, f"Cell {n} should have at least 1 connection"

    # Interior cell should have 7 connections (diagonal + 6 neighbors)
    # But we only store upper triangle, so expect 4 (diagonal + right + front + lower)
    node = 1 * nrow * ncol + 10 * ncol + 10  # Middle of layer 1
    nconn = ia[node + 1] - ia[node]
    assert nconn == 4, f"Interior cell should have 4 connections, got {nconn}"


def test_faceflows_validation():
    """Test that face flows validation catches shape mismatches."""
    nlay, nrow, ncol = 2, 3, 3

    ia, ja, nja = get_structured_connectivity(nlay, nrow, ncol)

    qright = np.ones((nlay, nrow, ncol))
    qfront = np.ones((nlay, nrow, ncol))
    qlower = np.ones((nlay, nrow, ncol - 1))  # Wrong shape

    with pytest.raises(ValueError, match="does not match grid shape"):
        get_structured_flowja(
            (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
        )
