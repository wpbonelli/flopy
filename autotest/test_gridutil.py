from itertools import product

import numpy as np
import pytest
from modflow_devtools.markers import requires_pkg

from flopy.utils.gridutil import (
    get_disu_kwargs,
    get_disu_kwargs_from_disv,
    get_disv_kwargs,
    get_disv_kwargs_from_disu,
    get_lni,
    uniform_flow_field,
)


@pytest.mark.parametrize(
    "ncpl, nn, expected_layer, expected_ni",
    [
        (10, 0, 0, 0),
        ([10, 10], 0, 0, 0),
        ([10, 10], 10, 1, 0),
        ([10, 10], 9, 0, 9),
        ([10, 10], 15, 1, 5),
        ([10, 20], 29, 1, 19),
    ],
)
def test_get_lni(ncpl, nn, expected_layer, expected_ni):
    # pair with next neighbor unless last in layer,
    # in which case pair with previous neighbor
    t = 1
    if nn == 9 or nn == 29:
        t = -1

    nodes = [nn, nn + t]
    lni = get_lni(ncpl, nodes)
    assert isinstance(lni, list)
    i = 0
    for actual_layer, actual_ni in lni:
        assert actual_layer == expected_layer
        assert actual_ni == expected_ni + (i * t)
        i += 1


def test_get_lni_no_nodes():
    lni = get_lni(10, [])
    assert isinstance(lni, list)
    assert len(lni) == 0


@pytest.mark.parametrize(
    "ncpl, nodes, expected",
    [
        (5, [14], [(2, 4)]),
        (10, [14], [(1, 4)]),
        (20, [14], [(0, 14)]),
        (20, [14, 24], [(0, 14), (1, 4)]),
    ],
)
def test_get_lni_infers_layer_count_when_int_ncpl(ncpl, nodes, expected):
    lni = get_lni(ncpl, nodes)
    assert isinstance(lni, list)
    for i, ln in enumerate(lni):
        assert ln == expected[i]


@requires_pkg("shapely")
@pytest.mark.parametrize(
    "nlay, nrow, ncol, delr, delc, tp, botm",
    [
        (
            1,
            61,
            61,
            np.array(61 * [50]),
            np.array(61 * [50]),
            -10,
            np.array([-30.0]),
        ),
        (
            2,
            61,
            61,
            np.array(61 * [50]),
            np.array(61 * [50]),
            -10,
            np.array([-30.0, -50.0]),
        ),
        (
            1,  # nlay
            3,  # nrow
            4,  # ncol
            np.array(4 * [4.0]),  # delr
            np.array(3 * [3.0]),  # delc
            -10,  # top
            -30.0,  # botm
        ),
    ],
)
def test_get_disu_kwargs(nlay, nrow, ncol, delr, delc, tp, botm):
    kwargs = get_disu_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=delr,
        delc=delc,
        tp=tp,
        botm=botm,
        return_vertices=True,
    )

    assert kwargs["nodes"] == nlay * nrow * ncol
    assert kwargs["nvert"] == (nrow + 1) * (ncol + 1)

    area = np.array([dr * dc for (dr, dc) in product(delr, delc)], dtype=float)
    area = np.array(nlay * [area]).flatten()
    assert np.array_equal(kwargs["area"], area)

    # TODO: test other properties
    # print(kwargs["iac"])
    # print(kwargs["ihc"])
    # print(kwargs["ja"])
    # print(kwargs["nja"])


@requires_pkg("shapely")
@pytest.mark.parametrize(
    "nlay, nrow, ncol, delr, delc, tp, botm",
    [
        (
            1,
            61,
            61,
            np.array(61 * [50.0]),
            np.array(61 * [50.0]),
            -10.0,
            -50.0,
        ),
        (
            2,
            61,
            61,
            np.array(61 * [50.0]),
            np.array(61 * [50.0]),
            -10.0,
            [-30.0, -50.0],
        ),
    ],
)
def test_get_disv_kwargs(nlay, nrow, ncol, delr, delc, tp, botm):
    kwargs = get_disv_kwargs(
        nlay=nlay, nrow=nrow, ncol=ncol, delr=delr, delc=delc, tp=tp, botm=botm
    )

    assert kwargs["nlay"] == nlay
    assert kwargs["ncpl"] == nrow * ncol
    assert kwargs["nvert"] == (nrow + 1) * (ncol + 1)

    # TODO: test other properties
    # print(kwargs["vertices"])
    # print(kwargs["cell2d"])


@requires_pkg("shapely")
@pytest.mark.parametrize(
    "qx, qy, qz, nlay, nrow, ncol",
    [
        (1, 0, 0, 1, 1, 10),
        (0, 1, 0, 1, 1, 10),
        (0, 0, 1, 1, 1, 10),
        (1, 0, 0, 1, 10, 10),
        (1, 0, 0, 2, 10, 10),
        (1, 1, 0, 2, 10, 10),
        (1, 1, 1, 2, 10, 10),
        (2, 1, 1, 2, 10, 10),
    ],
)
def test_uniform_flow_field(qx, qy, qz, nlay, nrow, ncol):
    shape = nlay, nrow, ncol
    spdis, flowja = uniform_flow_field(qx, qy, qz, shape)

    assert spdis.shape == (nlay * nrow * ncol,)
    for i, t in enumerate(spdis.flatten()):
        assert t[0] == t[1] == i
        assert t[3] == qx
        assert t[4] == qy
        assert t[5] == qz

    # TODO: check flowja
    # print(flowja.shape)


@requires_pkg("shapely")
@pytest.mark.parametrize(
    "nlay, nrow, ncol",
    [
        (1, 5, 5),  # Single layer
        (2, 5, 5),  # Multi-layer
        (3, 10, 10),  # Larger grid
    ],
)
def test_disu_to_disv_conversion(nlay, nrow, ncol):
    """Test DISU -> DISV conversion via roundtrip from structured grid."""
    # Create structured grid parameters
    delr = np.full(ncol, 100.0)
    delc = np.full(nrow, 100.0)
    tp = 10.0
    botm = np.linspace(-10.0, -10.0 * (nlay + 1), nlay + 1)[1:]

    # Convert to DISU with vertices
    disu_kwargs = get_disu_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=delr,
        delc=delc,
        tp=tp,
        botm=botm,
        return_vertices=True,
    )

    # Convert DISU to DISV
    disv_kwargs = get_disv_kwargs_from_disu(
        nodes=disu_kwargs["nodes"],
        iac=disu_kwargs["iac"],
        ja=disu_kwargs["ja"],
        ihc=disu_kwargs["ihc"],
        vertices=disu_kwargs["vertices"],
        cell2d=disu_kwargs["cell2d"],
        top=disu_kwargs["top"],
        bot=disu_kwargs["bot"],
    )

    # Verify dimensions
    assert disv_kwargs["nlay"] == nlay
    assert disv_kwargs["ncpl"] == nrow * ncol
    assert disv_kwargs["nvert"] == (nrow + 1) * (ncol + 1)

    # Verify top/botm shapes
    assert disv_kwargs["top"].shape == (nrow * ncol,)
    assert disv_kwargs["botm"].shape == (nlay, nrow * ncol)

    # Verify vertices were deduplicated (DISU may have 3D vertices)
    # DISV should have fewer or equal vertices
    assert disv_kwargs["nvert"] <= disu_kwargs["nvert"]

    # Verify cell2d format
    assert len(disv_kwargs["cell2d"]) == nrow * ncol
    for cell in disv_kwargs["cell2d"]:
        assert len(cell) >= 4  # [icell, xc, yc, nverts, ...]
        assert cell[3] == 4  # Rectangular cells have 4 vertices


@requires_pkg("shapely")
def test_disu_to_disv_non_layered_rejection():
    """Test that non-layered grids are rejected."""
    # Create a DISU grid
    nlay, nrow, ncol = 2, 3, 3
    disu_kwargs = get_disu_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=100.0,
        delc=100.0,
        tp=10.0,
        botm=[-10.0, -20.0],
        return_vertices=True,
    )

    # Corrupt ihc array to break layering - make layer numbers non-consecutive
    # Original should have layers [1, 1, 1, ..., 2, 2, 2, ...] in diagonal
    # Make it [1, 1, 1, ..., 5, 5, 5, ...] (skip layers 2, 3, 4)
    from flopy.utils.gridgen import get_ia_from_iac

    ihc_bad = disu_kwargs["ihc"].copy()
    ia = get_ia_from_iac(disu_kwargs["iac"])
    # Set second layer's diagonal positions to 5 instead of 2
    nodes_per_layer = nrow * ncol
    for i in range(nodes_per_layer, nlay * nodes_per_layer):
        ihc_bad[ia[i]] = 5  # Non-consecutive layer number

    # Should raise ValueError
    with pytest.raises(ValueError, match="does not have layered structure"):
        get_disv_kwargs_from_disu(
            nodes=disu_kwargs["nodes"],
            iac=disu_kwargs["iac"],
            ja=disu_kwargs["ja"],
            ihc=ihc_bad,
            vertices=disu_kwargs["vertices"],
            cell2d=disu_kwargs["cell2d"],
            top=disu_kwargs["top"],
            bot=disu_kwargs["bot"],
        )


@requires_pkg("shapely")
def test_disu_to_disv_missing_vertices():
    """Test that missing vertices/cell2d raises error."""
    nlay, nrow, ncol = 1, 3, 3
    disu_kwargs = get_disu_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=100.0,
        delc=100.0,
        tp=10.0,
        botm=[-10.0],
        return_vertices=False,  # Don't include vertices
    )

    # Should raise ValueError for missing vertices
    with pytest.raises(ValueError, match="vertices and cell2d are required"):
        get_disv_kwargs_from_disu(
            nodes=disu_kwargs["nodes"],
            iac=disu_kwargs["iac"],
            ja=disu_kwargs["ja"],
            ihc=disu_kwargs["ihc"],
            vertices=None,
            cell2d=None,
            top=disu_kwargs["top"],
            bot=disu_kwargs["bot"],
        )


@requires_pkg("shapely")
def test_disu_to_disv_vertex_deduplication():
    """Test that vertices are properly deduplicated."""
    nlay, nrow, ncol = 2, 3, 3

    # Create DISU grid
    disu_kwargs = get_disu_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=100.0,
        delc=100.0,
        tp=10.0,
        botm=[-10.0, -20.0],
        return_vertices=True,
    )

    # Manually duplicate some vertices with different z (simulating 3D DISU)
    # This simulates what a GSF file might have
    original_verts = disu_kwargs["vertices"]
    duplicated_verts = []
    for v in original_verts:
        # Add original
        duplicated_verts.append(v)
        # Add duplicate with different (fake) z coordinate
        duplicated_verts.append((v[0] + 1000, v[1], v[2], v[1] + 0.5))

    # Update cell2d to reference duplicated vertices
    cell2d_updated = []
    for c2d in disu_kwargs["cell2d"]:
        icell = c2d[0]
        xc, yc = c2d[1], c2d[2]
        nverts = c2d[3]
        iverts = [iv * 2 for iv in c2d[4 : 4 + nverts]]  # Reference duplicated verts
        cell2d_updated.append([icell, xc, yc, nverts] + iverts)

    # Convert should deduplicate
    disv_kwargs = get_disv_kwargs_from_disu(
        nodes=disu_kwargs["nodes"],
        iac=disu_kwargs["iac"],
        ja=disu_kwargs["ja"],
        ihc=disu_kwargs["ihc"],
        vertices=duplicated_verts,
        cell2d=cell2d_updated,
        top=disu_kwargs["top"],
        bot=disu_kwargs["bot"],
    )

    # Should have deduplicated back to original count
    assert disv_kwargs["nvert"] <= len(duplicated_verts)
    # In this case, should be exactly the original count
    assert disv_kwargs["nvert"] == len(original_verts)


@requires_pkg("shapely")
@pytest.mark.parametrize(
    "nlay, nrow, ncol",
    [
        (1, 5, 5),  # Single layer
        (2, 5, 5),  # Multi-layer
        (3, 10, 10),  # Larger grid
    ],
)
def test_disv_to_disu_conversion(nlay, nrow, ncol):
    """Test DISV -> DISU conversion."""
    # Create DISV grid from structured grid
    disv_kwargs = get_disv_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=100.0,
        delc=100.0,
        tp=10.0,
        botm=np.linspace(-10.0, -10.0 * (nlay + 1), nlay + 1)[1:],
    )

    # Convert to DISU
    disu_kwargs = get_disu_kwargs_from_disv(
        nlay=disv_kwargs["nlay"],
        ncpl=disv_kwargs["ncpl"],
        vertices=disv_kwargs["vertices"],
        cell2d=disv_kwargs["cell2d"],
        top=disv_kwargs["top"],
        botm=disv_kwargs["botm"],
    )

    # Verify dimensions
    assert disu_kwargs["nodes"] == nlay * nrow * ncol
    assert disu_kwargs["nvert"] == (nrow + 1) * (ncol + 1)

    # Verify connectivity arrays
    assert len(disu_kwargs["iac"]) == disu_kwargs["nodes"]
    assert len(disu_kwargs["ja"]) == disu_kwargs["nja"]
    assert len(disu_kwargs["ihc"]) == disu_kwargs["nja"]

    # Verify top/bot shapes
    assert disu_kwargs["top"].shape == (nlay * nrow * ncol,)
    assert disu_kwargs["bot"].shape == (nlay * nrow * ncol,)

    # Verify cell2d expanded for all layers
    assert len(disu_kwargs["cell2d"]) == nlay * nrow * ncol


@requires_pkg("shapely")
def test_disv_to_disu_roundtrip():
    """Test DISV -> DISU -> DISV roundtrip conversion."""
    nlay, nrow, ncol = 2, 3, 3

    # Create original DISV grid
    disv_orig = get_disv_kwargs(
        nlay=nlay,
        nrow=nrow,
        ncol=ncol,
        delr=100.0,
        delc=100.0,
        tp=10.0,
        botm=[-10.0, -20.0],
    )

    # Convert to DISU
    disu_kwargs = get_disu_kwargs_from_disv(
        nlay=disv_orig["nlay"],
        ncpl=disv_orig["ncpl"],
        vertices=disv_orig["vertices"],
        cell2d=disv_orig["cell2d"],
        top=disv_orig["top"],
        botm=disv_orig["botm"],
    )

    # Convert back to DISV
    disv_final = get_disv_kwargs_from_disu(
        nodes=disu_kwargs["nodes"],
        iac=disu_kwargs["iac"],
        ja=disu_kwargs["ja"],
        ihc=disu_kwargs["ihc"],
        vertices=disu_kwargs["vertices"],
        cell2d=disu_kwargs["cell2d"],
        top=disu_kwargs["top"],
        bot=disu_kwargs["bot"],
    )

    # Verify roundtrip preserved dimensions
    assert disv_final["nlay"] == disv_orig["nlay"]
    assert disv_final["ncpl"] == disv_orig["ncpl"]
    assert disv_final["nvert"] == disv_orig["nvert"]

    # Verify elevations preserved (within tolerance)
    assert np.allclose(disv_final["top"], disv_orig["top"])
    assert np.allclose(disv_final["botm"], disv_orig["botm"])
