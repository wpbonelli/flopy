"""
Tests for flopy.utils.cvfdutil, focusing on vertex deduplication and
hanging-node insertion at coarse/refined cell interfaces.

Background
----------
Two related issues were identified and investigated (see also the inline
test docstrings for details):

  shared_face bug
      shared_face() contains an off-by-one slice that makes it always return
      False.  The hanging-node loop therefore never short-circuits on pairs
      that already share a complete face, doing extra work on every iteration.
      For large grids this could interact with the non-convergence guard and
      cause the loop to stop before all hanging nodes are inserted as well.

  RED issue (near-duplicate vertices)
      If two cells describe what should be the same corner vertex with
      slightly different floating-point coordinates, to_cvfd assigns them
      different vertex indices and they never appear together in
      vertex_cell_dict.  The hanging-node check is therefore never invoked
      for that cell pair, and a missing midpoint vertex (see YELLOW) is never
      inserted.

  YELLOW issue (missing hanging-node vertex)
      A coarse cell adjacent to two refined cells is missing the midpoint
      vertex on their shared edge.  The hanging-node check in to_cvfd is
      supposed to insert it, but fails to do so when the RED issue prevents
      the cells from being recognised as adjacent.

Investigation results
---------------------
- GRIDGEN itself produces bit-for-bit identical coordinates for all shared
  vertices across all configurations tested (axis-aligned, rotated, UTM-scale,
  refinement depth 1–4).  It is NOT the source of near-duplicates.
- flopy's gridlist_to_verts can produce ~1e-14 (last-bit) differences at
  parent/child grid boundaries when cell sizes are non-round fractions.
  These are already caught by the default duplicate_decimals=9 rounding.
- Near-duplicate coordinates at larger magnitudes (1e-6 to 1e-4) have been
  observed in practice (see RED tests below) but their origin has not yet
  been confirmed; likely an external data source with limited precision.

Grid geometry used in the coarse/refined tests
-----------------------------------------------

    (0,2)──────(1,2)──────(2,2)
      │                     │
      │  coarse             │ top-small
      │  cell 0      (1,1)──┤
      │                     │
      │             ┌──────(2,1)
      │             │ bottom│
      │             │ small │
    (0,0)──────(1,0)──────(2,0)

  Cell 0 (coarse):      x=[0,1], y=[0,2]  – vertices (0,0),(1,0),(1,2),(0,2)
  Cell 1 (bot-small):   x=[1,2], y=[0,1]  – vertices (1,0),(2,0),(2,1),(1,1)
  Cell 2 (top-small):   x=[1,2], y=[1,2]  – vertices (1,1),(2,1),(2,2),(1,2)

The midpoint vertex (1,1) lies on the right edge of the coarse cell and must
be inserted into cell 0's vertex list so that DISV recognises the two
face connections: coarse↔bot-small and coarse↔top-small.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from modflow_devtools.markers import requires_exe, requires_pkg

import flopy
from flopy.utils.cvfdutil import gridlist_to_verts, shared_face, to_cvfd


# ── helpers ──────────────────────────────────────────────────────────────────


def _vertex_in_cell(verts, iverts, icell, x, y, tol=1e-6):
    """Return True if a vertex near (x, y) appears in cell icell's list."""
    for iv in iverts[icell]:
        if abs(verts[iv][0] - x) < tol and abs(verts[iv][1] - y) < tol:
            return True
    return False


def _near_duplicate_pairs(verts, tol=1e-4):
    """Return list of (i, j) index pairs whose coordinates are within tol."""
    pairs = []
    for i in range(len(verts)):
        for j in range(i + 1, len(verts)):
            if (
                abs(verts[i][0] - verts[j][0]) < tol
                and abs(verts[i][1] - verts[j][1]) < tol
            ):
                pairs.append((i, j))
    return pairs


def _cells_share_face(iverts, icell1, icell2):
    """
    Return True if icell1 and icell2 share a directed edge (iv_a → iv_b in
    one cell appearing as iv_b → iv_a in the other).
    """
    iv1 = iverts[icell1]
    iv2 = iverts[icell2]
    for i in range(len(iv1) - 1):
        a, b = iv1[i], iv1[i + 1]
        for j in range(len(iv2) - 1):
            if iv2[j] == b and iv2[j + 1] == a:
                return True
    return False


def _make_perfect_vertdict():
    """Three-cell vertdict with exact shared coordinates (baseline)."""
    return {
        0: [(0, 0), (1, 0), (1, 2), (0, 2), (0, 0)],  # coarse
        1: [(1, 0), (2, 0), (2, 1), (1, 1), (1, 0)],  # bot-small
        2: [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)],  # top-small
    }


def _make_near_dup_vertdict(delta):
    """Three-cell vertdict where the coarse cell's bottom-right corner is
    shifted by *delta* in x, simulating GRIDGEN floating-point drift."""
    return {
        0: [(0, 0), (1.0 + delta, 0.0), (1, 2), (0, 2), (0, 0)],
        1: [(1.0, 0.0), (2, 0), (2, 1), (1, 1), (1.0, 0.0)],
        2: [(1, 1), (2, 1), (2, 2), (1, 2), (1, 1)],
    }


# ── tests ─────────────────────────────────────────────────────────────────────


def test_perfect_coords_baseline():
    """
    Baseline: with exact shared coordinates, to_cvfd should:
      - produce no near-duplicate vertices, and
      - insert the midpoint (1,1) into the coarse cell's vertex list.
    """
    verts, iverts = to_cvfd(_make_perfect_vertdict())

    assert not _near_duplicate_pairs(verts, tol=1e-6), (
        "Expected no near-duplicate vertices with perfect coordinates"
    )
    assert _vertex_in_cell(verts, iverts, 0, 1.0, 1.0), (
        "Hanging-node (1,1) should be inserted into the coarse cell"
    )


def test_perfect_coords_face_connectivity():
    """
    Baseline: with exact shared coordinates, coarse cell must share a
    directed face with each of the two refined cells after to_cvfd.
    """
    verts, iverts = to_cvfd(_make_perfect_vertdict())

    assert _cells_share_face(iverts, 0, 1), (
        "Coarse cell and bot-small should share a face"
    )
    assert _cells_share_face(iverts, 0, 2), (
        "Coarse cell and top-small should share a face"
    )


@pytest.mark.parametrize("delta", [1e-6, 1e-5, 1e-4])
def test_near_duplicate_vertices_are_merged(delta):
    """
    RED issue: when GRIDGEN produces slightly different coordinates for the
    same shared corner, to_cvfd should merge them so that only one vertex
    survives.  With duplicate_decimals=9 (default) this currently fails for
    deltas >= 1e-9.
    """
    verts, iverts = to_cvfd(_make_near_dup_vertdict(delta))

    dupes = _near_duplicate_pairs(verts, tol=delta * 10)
    assert not dupes, (
        f"Near-duplicate vertex pair survived deduplication (delta={delta}): {dupes}"
    )


@pytest.mark.parametrize("delta", [1e-6, 1e-5, 1e-4])
def test_hanging_node_inserted_despite_near_duplicate(delta):
    """
    YELLOW issue: even when the coarse and refined cells share a corner with
    slightly drifted coordinates, the midpoint hanging-node should still be
    inserted into the coarse cell.  This currently fails because the RED issue
    prevents the two cells from appearing together in vertex_cell_dict.
    """
    verts, iverts = to_cvfd(_make_near_dup_vertdict(delta))

    assert _vertex_in_cell(verts, iverts, 0, 1.0, 1.0), (
        f"Hanging-node (1,1) not inserted into coarse cell (delta={delta})"
    )


@pytest.mark.parametrize("delta", [1e-6, 1e-5, 1e-4])
def test_face_connectivity_despite_near_duplicate(delta):
    """
    End-to-end: after deduplication and hanging-node insertion, the coarse
    cell must share a directed face with each refined neighbour regardless of
    coordinate drift.
    """
    verts, iverts = to_cvfd(_make_near_dup_vertdict(delta))

    assert _cells_share_face(iverts, 0, 1), (
        f"Coarse–bot-small face connection lost (delta={delta})"
    )
    assert _cells_share_face(iverts, 0, 2), (
        f"Coarse–top-small face connection lost (delta={delta})"
    )


def test_full_quadtree_refinement():
    """
    Larger scenario: 2×2 coarse grid where the bottom-right cell is refined
    into a 2×2 sub-grid (7 cells total).  All coarse/refined interface faces
    must be present after to_cvfd, and no near-duplicate vertices should
    survive.

    Cell numbering:
      0 = top-left coarse      (x=[0,2], y=[2,4])
      1 = top-right coarse     (x=[2,4], y=[2,4])
      2 = bottom-left coarse   (x=[0,2], y=[0,2])
      3 = BR sub-cell TL       (x=[2,3], y=[1,2])
      4 = BR sub-cell TR       (x=[3,4], y=[1,2])
      5 = BR sub-cell BL       (x=[2,3], y=[0,1])
      6 = BR sub-cell BR       (x=[3,4], y=[0,1])
    """
    delta = 1e-5  # simulate GRIDGEN drift on shared corners

    vertdict = {
        # coarse cells (closed polygons, last == first)
        0: [(0, 2), (2, 2), (2, 4), (0, 4), (0, 2)],
        1: [(2, 2), (4, 2), (4, 4), (2, 4), (2, 2)],
        2: [(0, 0), (2, 0), (2 + delta, 2 + delta), (0, 2), (0, 0)],  # drifted corner
        # bottom-right refined 2×2; exact coordinates
        3: [(2, 1), (3, 1), (3, 2), (2, 2), (2, 1)],   # BR-TL
        4: [(3, 1), (4, 1), (4, 2), (3, 2), (3, 1)],   # BR-TR
        5: [(2, 0), (3, 0), (3, 1), (2, 1), (2, 0)],   # BR-BL
        6: [(3, 0), (4, 0), (4, 1), (3, 1), (3, 0)],   # BR-BR
    }

    verts, iverts = to_cvfd(vertdict)

    # No surviving near-duplicates
    dupes = _near_duplicate_pairs(verts, tol=delta * 10)
    assert not dupes, f"Near-duplicate vertices survived: {dupes}"

    # Midpoint (2,1) must be inserted into bottom-left coarse cell (cell 2)
    # so it connects to BR-TL (cell 3) and BR-BL (cell 5)
    assert _vertex_in_cell(verts, iverts, 2, 2.0, 1.0), (
        "Hanging-node (2,1) not inserted into bottom-left coarse cell"
    )

    # Face connectivity at the coarse/refined interface
    assert _cells_share_face(iverts, 2, 3), "Cell 2 (BL coarse) ↔ cell 3 (BR-TL)"
    assert _cells_share_face(iverts, 2, 5), "Cell 2 (BL coarse) ↔ cell 5 (BR-BL)"


# ── shared_face bug ───────────────────────────────────────────────────────────


def test_shared_face_detects_common_face():
    """
    shared_face() has an off-by-one slice bug:

        if ivlist2[i2 : i2 + 1] == [iv2, iv1]:   # slice len 1 ≠ list len 2

    The slice always has length 1 while the right-hand side always has
    length 2, so the condition can never be True and shared_face() always
    returns False.

    The correct slice is ivlist2[i2 : i2 + 2].

    This test asserts the *correct* behaviour — two vertex lists that share
    a directed edge must be recognised as sharing a face.
    """
    # Two cells sharing directed edge 1→2 (cell a has 1→2, cell b reverses it
    # as 2→1, which is the convention for a shared face in CVFD notation).
    a = [0, 1, 2, 3, 0]
    b = [4, 2, 1, 5, 4]
    assert shared_face(a, b), (
        "shared_face() should return True for cells that share a directed edge "
        "(off-by-one slice bug: ivlist2[i2:i2+1] should be ivlist2[i2:i2+2])"
    )


def test_shared_face_no_common_face():
    """Cells with no shared edge must return False (sanity check)."""
    a = [0, 1, 2, 3, 0]
    b = [4, 5, 6, 7, 4]
    assert not shared_face(a, b)


def test_shared_face_partial_vertex_overlap_no_face():
    """Cells sharing a corner vertex but not a full face must return False."""
    a = [0, 1, 2, 3, 0]
    b = [1, 4, 5, 6, 1]  # shares vertex 1 but not an edge
    assert not shared_face(a, b)


# ── near-duplicate coordinate exploration ─────────────────────────────────────


def test_gridlist_to_verts_near_dups_caught_by_default_rounding():
    """
    gridlist_to_verts computes parent and child grid vertices independently.
    When cell sizes are non-round fractions (e.g. 100/3), the shared boundary
    coordinate is reached via two different floating-point paths:

      parent:  100.0 − 100.0/3  →  66.66666666666666  (subtract from length)
      child:   100.0/3 + 100.0/3  →  66.66666666666667  (sum of delc)

    The difference is ~1.42e-14 (one ULP).  The default duplicate_decimals=9
    in to_cvfd rounds both to 66.666666667, so they ARE merged into a single
    vertex and no near-duplicate survives in the output.
    """
    parent_delr = np.array([100.0 / 3, 100.0 / 3, 100.0 / 3])
    parent_delc = np.array([100.0 / 3, 100.0 / 3, 100.0 / 3])
    parent_grid = flopy.discretization.StructuredGrid(
        delr=parent_delr,
        delc=parent_delc,
        idomain=np.ones((1, 3, 3), dtype=int),
        top=np.zeros((3, 3)),
        botm=np.full((1, 3, 3), -1.0),
    )
    child_delr = np.array([100.0 / 6, 100.0 / 6])
    child_delc = np.array([100.0 / 6, 100.0 / 6])
    child_grid = flopy.discretization.StructuredGrid(
        delr=child_delr,
        delc=child_delc,
        xoff=float(parent_delr[0]),
        yoff=float(sum(parent_delc[1:])),
        idomain=np.ones((1, 2, 2), dtype=int),
        top=np.zeros((2, 2)),
        botm=np.full((1, 2, 2), -1.0),
    )

    # Confirm the raw 1-ULP difference exists in the input data
    parent_y_boundary = parent_grid.yvertices[1, 0]
    child_y_origin = child_grid.yoffset
    assert parent_y_boundary != child_y_origin, (
        "Expected a sub-epsilon difference between parent and child y-boundary "
        "coordinates computed via different arithmetic paths"
    )
    assert abs(parent_y_boundary - child_y_origin) < 1e-12, (
        "Expected the difference to be at the last-bit (ULP) level, < 1e-12"
    )

    # After to_cvfd the near-dup must be gone
    verts, iverts = gridlist_to_verts([parent_grid, child_grid])
    dupes = _near_duplicate_pairs(verts, tol=1e-10)
    assert not dupes, (
        f"Near-duplicate vertices survived to_cvfd despite duplicate_decimals=9: {dupes}"
    )


@requires_exe("gridgen")
@requires_pkg("pyshp", name_map={"pyshp": "shapefile"})
def test_gridgen_shared_vertices_are_identical(function_tmpdir):
    """
    GRIDGEN writes qtgrid.shp with IEEE 754 doubles.  For every grid
    configuration tested (axis-aligned, rotated, UTM-scale offsets, multiple
    refinement levels), shared vertices between adjacent cells in the shapefile
    are bit-for-bit identical — GRIDGEN is NOT the source of near-duplicate
    coordinates.

    This test builds a representative grid (rotation + point refinement,
    depth=3) and verifies that no two distinct shapefile vertices that map to
    the same approximate location differ in their exact coordinates.
    """
    import shapefile
    from collections import defaultdict

    nrow = ncol = 7
    Lx = Ly = 100.0
    delr = Lx / ncol
    delc = Ly / nrow
    ms = flopy.modflow.Modflow(rotation=-20.0, xll=12345.678, yll=98765.432)
    flopy.modflow.ModflowDis(
        ms, nlay=1, nrow=nrow, ncol=ncol, delr=delr, delc=delc, top=0, botm=-1
    )
    from flopy.utils.gridgen import Gridgen

    g = Gridgen(ms.modelgrid, model_ws=str(function_tmpdir))
    np.random.seed(0)
    xs = 12345.678 + Lx * np.random.random(6)
    ys = 98765.432 + Ly * np.random.random(6)
    g.add_refinement_features(list(zip(xs, ys)), "point", 3, range(1))
    g.build(verbose=False)

    sf = shapefile.Reader(str(function_tmpdir / "qtgrid.shp"))
    attrs = [f[0] for f in sf.fields[1:]]
    nn_idx = attrs.index("nodenumber")
    cells = {
        int(sf.records()[i][nn_idx]) - 1: sf.shapes()[i].points
        for i in range(len(sf.shapes()))
    }

    # Group exact (x,y) tuples by their rounded position (3 d.p.)
    approx: dict = defaultdict(list)
    for pts in cells.values():
        for x, y in pts:
            approx[(round(x, 3), round(y, 3))].append((x, y))

    near_dups = [
        (nominal, coords)
        for nominal, coords in approx.items()
        if len(set(coords)) > 1
    ]
    assert not near_dups, (
        f"GRIDGEN emitted near-duplicate coordinates for {len(near_dups)} vertex "
        f"location(s); first: {near_dups[0]}"
    )
