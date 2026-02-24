"""
Tests for MF6 connectivity builder and saturation calculator.
"""

import numpy as np
import pytest

from flopy.mf6.utils.binarygrid_util import build_structured_connectivity
from flopy.mf6.utils.postprocessing import get_structured_flowja
from flopy.utils.postprocessing import calculate_saturation


def test_connectivity_simple_grid():
    """Test connectivity builder with simple 2x2x2 grid."""
    nlay, nrow, ncol = 2, 2, 2
    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

    # Check dimensions
    ncells = nlay * nrow * ncol
    assert len(ia) == ncells + 1, f"IA length should be {ncells + 1}"
    assert len(ja) == nja, "JA length should equal nja"
    assert ia[-1] == nja, "Last IA entry should equal nja"

    # Each active cell should have at least 1 connection (diagonal)
    for n in range(ncells):
        nconn = ia[n + 1] - ia[n]
        assert nconn >= 1, f"Cell {n} should have at least 1 connection"

    # First cell (0,0,0) should have 4 connections: diagonal + right + front + lower
    nconn_first = ia[1] - ia[0]
    assert nconn_first == 4, f"First cell should have 4 connections, got {nconn_first}"

    # Verify first cell connections
    first_conns = ja[ia[0] : ia[1]]
    assert first_conns[0] == 0, "First connection should be diagonal (self)"
    assert 1 in first_conns, "Should connect to right neighbor"
    assert 2 in first_conns, "Should connect to front neighbor"
    assert 4 in first_conns, "Should connect to lower neighbor"


def test_connectivity_with_inactive_cells():
    """Test connectivity with inactive cells in IDOMAIN."""
    nlay, nrow, ncol = 2, 3, 3
    idomain = np.ones((nlay, nrow, ncol), dtype=np.int32)

    # Make center cell of top layer inactive
    idomain[0, 1, 1] = 0

    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol, idomain)

    # Inactive cell (node 4) should have 0 connections
    node_inactive = 0 * nrow * ncol + 1 * ncol + 1  # (k=0, i=1, j=1)
    nconn_inactive = ia[node_inactive + 1] - ia[node_inactive]
    assert nconn_inactive == 0, (
        f"Inactive cell should have 0 connections, got {nconn_inactive}"
    )

    # Neighbors of inactive cell should not connect to it
    node_left = 0 * nrow * ncol + 1 * ncol + 0  # (k=0, i=1, j=0)
    conns_left = ja[ia[node_left] : ia[node_left + 1]]
    assert node_inactive not in conns_left, (
        "Active cell should not connect to inactive cell"
    )


def test_connectivity_corner_cells():
    """Test connectivity for corner cells with fewer neighbors."""
    nlay, nrow, ncol = 1, 3, 3

    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

    # Top-left corner (0,0,0) - should have 3 connections: diagonal + right + front
    node_corner = 0
    nconn = ia[node_corner + 1] - ia[node_corner]
    assert nconn == 3, f"Corner cell should have 3 connections, got {nconn}"

    # Bottom-right corner (0,2,2) - should have 1 connection: diagonal only
    node_corner = 0 * nrow * ncol + 2 * ncol + 2
    nconn = ia[node_corner + 1] - ia[node_corner]
    assert nconn == 1, f"Bottom-right corner should have 1 connection, got {nconn}"


def test_faceflows_to_connections_simple():
    """Test mapping face flows to connections."""
    nlay, nrow, ncol = 1, 3, 3

    # Create connectivity
    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

    # Create simple face flows (all positive)
    qright = np.ones((nlay, nrow, ncol)) * 1.0
    qfront = np.ones((nlay, nrow, ncol)) * 2.0
    qlower = np.ones((nlay, nrow, ncol)) * 3.0

    # Map to connections
    flowja = get_structured_flowja(
        (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
    )

    assert len(flowja) == nja, f"flowja length should be {nja}"

    # Check first cell (0,0,0) connections
    node = 0
    conns = ja[ia[node] : ia[node + 1]]
    flows = flowja[ia[node] : ia[node + 1]]

    # Find right, front connections
    for ipos, m in enumerate(conns):
        if m == node:
            # Diagonal should be zero
            assert flows[ipos] == 0.0, "Diagonal flow should be 0"
        elif m == 1:
            # Right connection
            assert flows[ipos] == 1.0, "Right flow should be 1.0"
        elif m == 3:
            # Front connection
            assert flows[ipos] == 2.0, "Front flow should be 2.0"


def test_faceflows_to_connections_multilayer():
    """Test mapping face flows in multilayer grid."""
    nlay, nrow, ncol = 3, 2, 2

    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

    # Create face flows with distinct values per direction
    qright = np.ones((nlay, nrow, ncol)) * 10.0
    qfront = np.ones((nlay, nrow, ncol)) * 20.0
    qlower = np.ones((nlay, nrow, ncol)) * 30.0

    flowja = get_structured_flowja(
        (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
    )

    # Check first cell of top layer connects to lower layer
    node = 0  # (k=0, i=0, j=0)
    node_below = nrow * ncol  # (k=1, i=0, j=0)

    conns = ja[ia[node] : ia[node + 1]]
    flows = flowja[ia[node] : ia[node + 1]]

    # Find lower connection
    lower_idx = np.where(conns == node_below)[0]
    if len(lower_idx) > 0:
        assert flows[lower_idx[0]] == 30.0, "Lower flow should be 30.0"


def test_saturation_confined_cells():
    """Test saturation calculation for confined cells."""
    nlay, nrow, ncol = 2, 3, 3

    # Confined cells - all icelltype = 0
    icelltype = np.zeros((nlay, nrow, ncol), dtype=np.int32)

    # Heads below top
    head = np.full((nlay, nrow, ncol), 50.0)
    top = np.full((nrow, ncol), 100.0)
    botm = np.array(
        [
            np.full((nrow, ncol), 75.0),
            np.full((nrow, ncol), 25.0),
        ]
    )

    sat = calculate_saturation(head, top, botm, icelltype)

    # All confined cells should be fully saturated
    assert np.allclose(sat, 1.0, equal_nan=True), (
        "All confined cells should have saturation = 1.0"
    )


def test_saturation_convertible_cells():
    """Test saturation calculation for convertible (unconfined) cells."""
    nlay, nrow, ncol = 2, 3, 3

    # Top layer convertible, bottom layer confined
    icelltype = np.zeros((nlay, nrow, ncol), dtype=np.int32)
    icelltype[0] = 1

    # Setup elevations
    top = np.full((nrow, ncol), 100.0)
    botm = np.array(
        [
            np.full((nrow, ncol), 50.0),  # Layer 0 bottom
            np.full((nrow, ncol), 0.0),  # Layer 1 bottom
        ]
    )

    # Head at 75 in top layer - should be 50% saturated
    head = np.full((nlay, nrow, ncol), 75.0)

    sat = calculate_saturation(head, top, botm, icelltype)

    # Top layer should be 50% saturated
    expected_sat_top = (75.0 - 50.0) / (100.0 - 50.0)
    assert np.allclose(sat[0], expected_sat_top), (
        f"Top layer saturation should be {expected_sat_top:.2f}, got {sat[0, 0, 0]:.2f}"
    )

    # Bottom layer (confined) should be 100% saturated
    assert np.allclose(sat[1], 1.0), "Bottom layer (confined) should be fully saturated"


def test_saturation_fully_saturated():
    """Test saturation when head exceeds top."""
    nlay, nrow, ncol = 1, 2, 2

    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)

    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)

    # Head above top
    head = np.full((nlay, nrow, ncol), 120.0)

    sat = calculate_saturation(head, top, botm, icelltype)

    # Should be fully saturated (clamped to 1.0)
    assert np.allclose(sat, 1.0), "Cells with head > top should be fully saturated"


def test_saturation_dry_cells():
    """Test saturation with dry cells."""
    nlay, nrow, ncol = 1, 2, 2

    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)

    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)

    # Mix of normal and dry cells
    head = np.full((nlay, nrow, ncol), 75.0)
    head[0, 0, 0] = -999.0  # Dry cell
    head[0, 1, 1] = -9999.0  # Inactive cell

    sat = calculate_saturation(head, top, botm, icelltype, hdry=-999.0, hnoflo=-9999.0)

    # Dry and inactive cells should be NaN
    assert np.isnan(sat[0, 0, 0]), "Dry cell should have NaN saturation"
    assert np.isnan(sat[0, 1, 1]), "Inactive cell should have NaN saturation"

    # Active cells should be properly saturated
    assert np.allclose(sat[0, 0, 1], 0.5), "Active cell should be 50% saturated"
    assert np.allclose(sat[0, 1, 0], 0.5), "Active cell should be 50% saturated"


def test_saturation_below_bottom():
    """Test saturation when head is below cell bottom."""
    nlay, nrow, ncol = 1, 2, 2

    icelltype = np.ones((nlay, nrow, ncol), dtype=np.int32)

    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)

    # Head below bottom
    head = np.full((nlay, nrow, ncol), 30.0)

    sat = calculate_saturation(head, top, botm, icelltype)

    # Saturation should be 0.0 (completely unsaturated)
    assert np.allclose(sat, 0.0), (
        "Cells with head < bottom should have saturation = 0.0"
    )


def test_saturation_1d_arrays():
    """Test saturation calculation with 1D arrays (unstructured)."""
    ncells = 10

    icelltype = np.zeros(ncells, dtype=np.int32)
    icelltype[0:5] = 1  # First 5 convertible

    # Create elevation arrays
    top = np.linspace(100, 50, ncells)
    botm = np.linspace(50, 0, ncells)
    head = np.linspace(75, 25, ncells)

    sat = calculate_saturation(head, top, botm, icelltype)

    assert len(sat) == ncells, f"Saturation array should have {ncells} elements"

    # First cell (convertible): (75-50)/(100-50) = 0.5
    expected_sat_0 = (75.0 - 50.0) / (100.0 - 50.0)
    assert np.allclose(sat[0], expected_sat_0), (
        f"First cell saturation should be {expected_sat_0:.2f}"
    )

    # Last 5 cells (confined) should be 1.0
    assert np.allclose(sat[5:], 1.0), "Confined cells should be fully saturated"


def test_connectivity_realistic_grid():
    """Test connectivity with realistic model grid size."""
    nlay, nrow, ncol = 3, 40, 20
    ncells = nlay * nrow * ncol

    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

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

    ia, ja, nja = build_structured_connectivity(nlay, nrow, ncol)

    qright = np.ones((nlay, nrow, ncol))
    qfront = np.ones((nlay, nrow, ncol))
    qlower = np.ones((nlay, nrow, ncol - 1))  # Wrong shape

    with pytest.raises(ValueError, match="does not match grid shape"):
        get_structured_flowja(
            (qright, qfront, qlower), ia=ia, ja=ja, nlay=nlay, nrow=nrow, ncol=ncol
        )


def test_saturation_validation():
    """Test that saturation validation catches invalid inputs."""
    nlay, nrow, ncol = 2, 3, 3

    head = np.full((nlay, nrow, ncol), 50.0)
    top = np.full((nrow, ncol), 100.0)
    botm = np.full((nlay, nrow, ncol), 50.0)
    icelltype = np.zeros((nlay, nrow - 1, ncol), dtype=np.int32)  # Wrong shape

    with pytest.raises(ValueError, match="does not match"):
        calculate_saturation(head, top, botm, icelltype)
