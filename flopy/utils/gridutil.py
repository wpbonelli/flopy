"""
Grid utilities
"""

import warnings
from collections.abc import Collection, Iterable, Sequence
from math import floor

import numpy as np

from .cvfdutil import centroid_of_polygon, get_disv_gridprops


def get_lni(ncpl, nodes) -> list[tuple[int, int]]:
    """
    Get layer index and within-layer node index (both 0-based).

     | Node count per layer may be an int or array-like of integers.
    An integer ncpl indicates all layers have the same node count.
    If an integer ncpl is less than any specified node numbers, the
    grid is understood to have at least enough layers to contain them.

     | If ncpl is array-like it is understood to describe node count
    per zero-indexed layer.

    Parameters
    ----------
    ncpl: node count per layer (int or array-like of ints)
    nodes : node numbers (array-like of nodes)

    Returns
    -------
        A list of tuples (layer index, node index)
    """

    if not isinstance(ncpl, (int, list, tuple, np.ndarray)):
        raise ValueError("ncpl must be int or array-like")
    if not isinstance(nodes, (list, tuple, np.ndarray)):
        raise ValueError("nodes must be array-like")

    if len(nodes) == 0:
        return []

    if isinstance(ncpl, int):
        # infer min number of layers to hold given node numbers
        layers = range(floor(np.max(nodes) / ncpl) if len(nodes) > 0 else 1)
        counts = [ncpl for _ in layers]
    else:
        counts = list(ncpl)

    tuples = []
    for nn in nodes if nodes else range(sum(counts)):
        csum = np.cumsum([0] + counts)
        layer = max(0, np.searchsorted(csum, nn) - 1)
        nidx = nn - sum(counts[l] for l in range(0, layer))

        # np.searchsorted assigns the first index of each layer
        # to the previous layer in layer 2+, so correct for it
        correct = layer + 1 < len(csum) and nidx == counts[layer]
        tuples.append((layer + 1, 0) if correct else (layer, nidx))

    return tuples


def get_disu_kwargs(
    nlay,
    nrow,
    ncol,
    delr,
    delc,
    tp,
    botm,
    return_vertices=False,
):
    """
    Create args needed to construct a DISU package for a regular
    MODFLOW grid.

    Parameters
    ----------
    nlay : int
        Number of layers
    nrow : int
        Number of rows
    ncol : int
        Number of columns
    delr : numpy.ndarray
        Column spacing along a row
    delc : numpy.ndarray
        Row spacing along a column
    tp : int or numpy.ndarray
        Top elevation(s) of cells in the model's top layer
    botm : numpy.ndarray
        Bottom elevation(s) for each layer
    return_vertices: bool
        If true, then include vertices, cell2d and angldegx in kwargs
    """

    def get_nn(k, i, j):
        return k * nrow * ncol + i * ncol + j

    # delr check
    if np.isscalar(delr):
        delr = delr * np.ones(ncol, dtype=float)
    else:
        assert np.asanyarray(delr).shape == (ncol,), (
            "delr must be array with shape (ncol,), got {}".format(delr.shape)
        )

    # delc check
    if np.isscalar(delc):
        delc = delc * np.ones(nrow, dtype=float)
    else:
        assert np.asanyarray(delc).shape == (nrow,), (
            "delc must be array with shape (nrow,), got {}".format(delc.shape)
        )

    # tp check
    if np.isscalar(tp):
        tp = tp * np.ones((nrow, ncol), dtype=float)
    else:
        assert np.asanyarray(tp).shape == (
            nrow,
            ncol,
        ), "tp must be scalar or array with shape (nrow, ncol), got {}".format(tp.shape)

    # botm check
    if np.isscalar(botm):
        botm = botm * np.ones((nlay, nrow, ncol), dtype=float)
    elif np.asanyarray(botm).shape == (nlay,):
        b = np.empty((nlay, nrow, ncol), dtype=float)
        for k in range(nlay):
            b[k] = botm[k]
        botm = b
    else:
        assert np.asanyarray(botm).shape == (
            nlay,
            nrow,
            ncol,
        ), "botm must be array with shape (nlay, nrow, ncol), got {}".format(botm.shape)

    nodes = nlay * nrow * ncol
    iac = np.zeros((nodes), dtype=int)
    ja = []
    area = np.zeros((nodes), dtype=float)
    top = np.zeros((nodes), dtype=float)
    bot = np.zeros((nodes), dtype=float)
    ihc = []
    cl12 = []
    hwva = []
    angldegx = []
    for k in range(nlay):
        for i in range(nrow):
            for j in range(ncol):
                # diagonal
                n = get_nn(k, i, j)
                ja.append(n)
                iac[n] += 1
                area[n] = delr[j] * delc[i]
                ihc.append(k + 1)  # put layer in diagonal for flopy plotting
                cl12.append(n + 1)
                hwva.append(n + 1)
                angldegx.append(n + 1)
                if k == 0:
                    top[n] = tp[i, j]
                else:
                    top[n] = botm[k - 1, i, j]
                bot[n] = botm[k, i, j]
                # up
                if k > 0:
                    ja.append(get_nn(k - 1, i, j))
                    iac[n] += 1
                    ihc.append(0)
                    dz = botm[k - 1, i, j] - botm[k, i, j]
                    cl12.append(0.5 * dz)
                    hwva.append(delr[j] * delc[i])
                    angldegx.append(0)  # Always Perpendicular to the x-axis
                # back
                if i > 0:
                    ja.append(get_nn(k, i - 1, j))
                    iac[n] += 1
                    ihc.append(1)
                    cl12.append(0.5 * delc[i])
                    hwva.append(delr[j])
                    angldegx.append(90)
                # left
                if j > 0:
                    ja.append(get_nn(k, i, j - 1))
                    iac[n] += 1
                    ihc.append(1)
                    cl12.append(0.5 * delr[j])
                    hwva.append(delc[i])
                    angldegx.append(180)
                # right
                if j < ncol - 1:
                    ja.append(get_nn(k, i, j + 1))
                    iac[n] += 1
                    ihc.append(1)
                    cl12.append(0.5 * delr[j])
                    hwva.append(delc[i])
                    angldegx.append(0)
                # front
                if i < nrow - 1:
                    ja.append(get_nn(k, i + 1, j))
                    iac[n] += 1
                    ihc.append(1)
                    cl12.append(0.5 * delc[i])
                    hwva.append(delr[j])
                    angldegx.append(270)
                # bottom
                if k < nlay - 1:
                    ja.append(get_nn(k + 1, i, j))
                    iac[n] += 1
                    ihc.append(0)
                    if k == 0:
                        dz = tp[i, j] - botm[k, i, j]
                    else:
                        dz = botm[k - 1, i, j] - botm[k, i, j]
                    cl12.append(0.5 * dz)
                    hwva.append(delr[j] * delc[i])
                    angldegx.append(0)  # Always Perpendicular to the x-axis
    ja = np.array(ja, dtype=int)
    nja = ja.shape[0]
    hwva = np.array(hwva, dtype=float)

    # build vertices
    nvert = None
    if return_vertices:
        xv = np.cumsum(delr)
        xv = np.array([0] + list(xv))
        ymax = delc.sum()
        yv = np.cumsum(delc)
        yv = ymax - np.array([0] + list(yv))
        xmg, ymg = np.meshgrid(xv, yv)
        nvert = xv.shape[0] * yv.shape[0]
        verts = np.array(list(zip(xmg.flatten(), ymg.flatten())))
        vertices = []
        for i in range(nvert):
            vertices.append((i, verts[i, 0], verts[i, 1]))

        cell2d = []
        icell = 0
        for k in range(nlay):
            for i in range(nrow):
                for j in range(ncol):
                    iv0 = j + i * (ncol + 1)  # upper left vertex
                    iv1 = iv0 + 1  # upper right vertex
                    iv3 = iv0 + ncol + 1  # lower left vertex
                    iv2 = iv3 + 1  # lower right vertex
                    iverts = [iv0, iv1, iv2, iv3]
                    vlist = [(verts[iv, 0], verts[iv, 1]) for iv in iverts]
                    xc, yc = centroid_of_polygon(vlist)
                    cell2d.append([icell, xc, yc, len(iverts)] + iverts)
                    icell += 1

    kw = {}
    kw["nodes"] = nodes
    kw["nja"] = nja
    kw["nvert"] = nvert
    kw["top"] = top
    kw["bot"] = bot
    kw["area"] = area
    kw["iac"] = iac
    kw["ja"] = ja
    kw["ihc"] = ihc
    kw["cl12"] = cl12
    kw["hwva"] = hwva
    if return_vertices:
        kw["vertices"] = vertices
        kw["cell2d"] = cell2d
        kw["angldegx"] = angldegx
    return kw


def get_disv_kwargs(
    nlay,
    nrow,
    ncol,
    delr,
    delc,
    tp,
    botm,
    xoff=0.0,
    yoff=0.0,
):
    """
    Create args needed to construct a DISV package.

    Parameters
    ----------
    nlay : int
        Number of layers
    nrow : int
        Number of rows
    ncol : int
        Number of columns
    delr : float or numpy.ndarray
        Column spacing along a row with shape (ncol)
    delc : float or numpy.ndarray
        Row spacing along a column with shape (nrow)
    tp : float or numpy.ndarray
        Top elevation(s) of cells in the model's top layer with shape (nrow, ncol)
    botm : list of floats or numpy.ndarray
        Bottom elevation(s) of all cells in the model with shape (nlay, nrow, ncol)
    xoff : float
        Value to add to all x coordinates.  Optional (default = 0.)
    yoff : float
        Value to add to all y coordinates.  Optional (default = 0.)
    """

    # validate input
    ncpl = nrow * ncol

    # delr check
    if np.isscalar(delr):
        delr = delr * np.ones(ncol, dtype=float)
    else:
        assert np.asanyarray(delr).shape == (ncol,), (
            "delr must be array with shape (ncol,), got {}".format(delr.shape)
        )

    # delc check
    if np.isscalar(delc):
        delc = delc * np.ones(nrow, dtype=float)
    else:
        assert np.asanyarray(delc).shape == (nrow,), (
            "delc must be array with shape (nrow,), got {}".format(delc.shape)
        )

    # tp check
    if np.isscalar(tp):
        tp = tp * np.ones((nrow, ncol), dtype=float)
    else:
        assert np.asanyarray(tp).shape == (
            nrow,
            ncol,
        ), "tp must be scalar or array with shape (nrow, ncol), got {}".format(tp.shape)

    # botm check
    if np.isscalar(botm):
        botm = botm * np.ones((nlay, nrow, ncol), dtype=float)
    elif np.asanyarray(botm).shape == (nlay,):
        b = np.empty((nlay, nrow, ncol), dtype=float)
        for k in range(nlay):
            b[k] = botm[k]
        botm = b
    else:
        assert botm.shape == (
            nlay,
            nrow,
            ncol,
        ), "botm must be array with shape (nlay, nrow, ncol), got {}".format(botm.shape)

    # build vertices
    xv = np.cumsum(delr)
    xv = np.array([0] + list(xv))
    ymax = delc.sum()
    yv = np.cumsum(delc)
    yv = ymax - np.array([0] + list(yv))
    xmg, ymg = np.meshgrid(xv, yv)
    verts = np.array(list(zip(xmg.flatten(), ymg.flatten())))
    verts[:, 0] += xoff
    verts[:, 1] += yoff

    # build iverts (list of vertices for each cell)
    iverts = []
    for i in range(nrow):
        for j in range(ncol):
            # number vertices in clockwise order
            iv0 = j + i * (ncol + 1)  # upper left vertex
            iv1 = iv0 + 1  # upper right vertex
            iv3 = iv0 + ncol + 1  # lower left vertex
            iv2 = iv3 + 1  # lower right vertex
            iverts.append([iv0, iv1, iv2, iv3])
    kw = get_disv_gridprops(verts, iverts)

    # reshape and add top and bottom
    kw["top"] = tp.reshape(ncpl)
    kw["botm"] = botm.reshape(nlay, ncpl)
    kw["nlay"] = nlay
    return kw


def get_disv_kwargs_from_disu(
    nodes,
    iac,
    ja,
    ihc,
    vertices,
    cell2d,
    top,
    bot,
    area=None,
    validate_layered=True,
    vertex_decimals=9,
):
    """
    Convert DISU grid parameters to DISV grid parameters.

    This function converts a fully unstructured (DISU) grid to a layered
    vertex (DISV) grid. It only works for DISU grids that have an inherent
    layered structure (constant cells per layer across all layers).

    Parameters
    ----------
    nodes : int
        Number of nodes (cells) in the DISU grid
    iac : array_like
        Number of connections per node plus one (shape: nodes).
        From DISU CONNECTIONDATA block.
    ja : array_like
        Jagged connection array (shape: nja).
        From DISU CONNECTIONDATA block.
    ihc : array_like
        Horizontal connection indicator array (shape: nja).
        For layered grids, diagonal position stores layer number.
        From DISU CONNECTIONDATA block.
    vertices : list of tuples
        List of (iv, x, y) or (iv, x, y, z) vertex tuples.
        From DISU VERTICES block.
    cell2d : list of lists
        List of cell2d records [icell, xc, yc, nvert, iv1, iv2, ...].
        From DISU CELL2D block.
    top : array_like
        Top elevation for each cell (shape: nodes).
        From DISU GRIDDATA block.
    bot : array_like
        Bottom elevation for each cell (shape: nodes).
        From DISU GRIDDATA block.
    area : array_like, optional
        Cell areas (not used in DISV, included for completeness).
    validate_layered : bool, default True
        If True, perform validation that cells are vertically aligned.
    vertex_decimals : int, default 9
        Decimal places for vertex deduplication rounding.

    Returns
    -------
    dict
        Dictionary with keys compatible with ModflowGwfdisv:
        nlay, ncpl, nvert, vertices, cell2d, top, botm

    Raises
    ------
    ValueError
        If grid is not layered (ncpl varies by layer)
        If vertices or cell2d are missing
        If validation checks fail

    Notes
    -----
    This function is designed for grids that are inherently layered (e.g.,
    from MF-USG GSF files) but stored in DISU format. It will not work for:

    1. Truly 3D unstructured grids (e.g., Voronoi, arbitrary tetrahedra)
    2. Grids where horizontal footprint varies by layer
    3. Grids without vertex information

    The conversion leverages the MODFLOW vertical prism assumption: all cells
    are vertical prisms with flat horizontal tops/bottoms. Vertices are
    deduplicated to 2D (x,y) coordinates, discarding z-coordinates.

    Examples
    --------
    >>> from flopy.utils.gridutil import get_disu_kwargs, get_disv_kwargs_from_disu
    >>> # Create DISU grid from structured grid
    >>> disu_kwargs = get_disu_kwargs(
    ...     nlay=2, nrow=5, ncol=5,
    ...     delr=100.0, delc=100.0,
    ...     tp=10.0, botm=[-10.0, -20.0],
    ...     return_vertices=True
    ... )
    >>> # Convert to DISV
    >>> disv_kwargs = get_disv_kwargs_from_disu(
    ...     nodes=disu_kwargs["nodes"],
    ...     iac=disu_kwargs["iac"],
    ...     ja=disu_kwargs["ja"],
    ...     ihc=disu_kwargs["ihc"],
    ...     vertices=disu_kwargs["vertices"],
    ...     cell2d=disu_kwargs["cell2d"],
    ...     top=disu_kwargs["top"],
    ...     bot=disu_kwargs["bot"]
    ... )
    >>> print(disv_kwargs["nlay"], disv_kwargs["ncpl"])
    2 25
    """
    # Import here to avoid circular dependency
    from ..discretization.unstructuredgrid import UnstructuredGrid

    # Validate inputs
    if vertices is None or cell2d is None:
        raise ValueError(
            "Cannot convert DISU to DISV: vertices and cell2d are required. "
            "DISU grid must include vertex information for conversion."
        )

    # Convert to numpy arrays
    iac = np.asarray(iac, dtype=int)
    ja = np.asarray(ja, dtype=int)
    ihc = np.asarray(ihc, dtype=int)
    top = np.asarray(top, dtype=float)
    bot = np.asarray(bot, dtype=float)

    # Step 1: Extract layer structure using ncpl_from_ihc
    ncpl_array = UnstructuredGrid.ncpl_from_ihc(ihc, iac)

    if ncpl_array is None:
        raise ValueError(
            "Cannot convert DISU to DISV: grid does not have layered structure. "
            "The ihc array diagonal positions do not contain monotonically "
            "increasing consecutive layer numbers. This typically occurs with "
            "truly 3D unstructured grids (e.g., Voronoi, arbitrary tetrahedra). "
            "Consider keeping DISU format."
        )

    # Step 2: Validate constant ncpl
    ncpl_unique = np.unique(ncpl_array)
    if len(ncpl_unique) != 1:
        raise ValueError(
            f"Cannot convert DISU to DISV: cells per layer is not constant. "
            f"Found ncpl values: {ncpl_array}. "
            f"DISV requires all layers have the same horizontal footprint. "
            f"This may occur if layers have different refinement or pinchouts "
            f"are not represented with idomain=-1."
        )

    nlay = len(ncpl_array)
    ncpl = int(ncpl_unique[0])

    # Validate total nodes
    if np.sum(ncpl_array) != nodes:
        raise ValueError(
            f"Sum of ncpl ({np.sum(ncpl_array)}) != nodes ({nodes}). "
            f"Grid structure is inconsistent."
        )

    # Step 3: Deduplicate vertices to 2D using vertical prism assumption
    # Extract (x, y) from vertices, discarding z if present
    verts_2d = []
    for v in vertices:
        if len(v) >= 3:
            # Format: (iv, x, y) or (iv, x, y, z)
            verts_2d.append((v[1], v[2]))  # x, y
        else:
            raise ValueError(
                f"Invalid vertex format: {v}. Expected (iv, x, y) or (iv, x, y, z)."
            )

    # Build deduplication mapping (following LgrToDisv pattern)
    vertex_dict = {}  # maps (x, y) tuple to new vertex index
    old_to_new = {}  # maps old vertex index to new vertex index
    new_verts_list = []
    new_vertex_idx = 0

    for old_idx, (x, y) in enumerate(verts_2d):
        # Round to specified decimals to handle floating point precision
        coord = (round(x, vertex_decimals), round(y, vertex_decimals))

        if coord in vertex_dict:
            # Duplicate vertex found (same x,y but different z)
            old_to_new[old_idx] = vertex_dict[coord]
        else:
            # New unique (x,y) coordinate
            vertex_dict[coord] = new_vertex_idx
            old_to_new[old_idx] = new_vertex_idx
            new_verts_list.append([x, y])
            new_vertex_idx += 1

    verts_dedup = np.array(new_verts_list)
    nvert = len(verts_dedup)

    # Step 4: Build DISV vertices array
    vertices_disv = []
    for i in range(nvert):
        vertices_disv.append((i, verts_dedup[i, 0], verts_dedup[i, 1]))

    # Step 5: Remap cell2d vertex indices for layer 0
    # DISV uses single 2D footprint for all layers
    cell2d_disv = []
    for icell in range(ncpl):
        c2d = cell2d[icell]
        icell_id = int(c2d[0])
        xc = float(c2d[1])
        yc = float(c2d[2])
        nverts = int(c2d[3])
        iverts_old = c2d[4 : 4 + nverts]

        # Remap vertex indices using deduplication mapping
        iverts_new = [old_to_new[int(iv)] for iv in iverts_old]

        # Rebuild cell2d record with remapped indices
        cell2d_disv.append([icell, xc, yc, len(iverts_new)] + iverts_new)

    # Step 6: Reshape top/botm arrays
    # DISV top is 2D array (ncpl,) representing top of uppermost layer
    top_disv = top[:ncpl].copy()

    # DISV botm is 2D array (nlay, ncpl) with bottom elevation for each layer
    botm_disv = np.zeros((nlay, ncpl), dtype=float)
    for ilay in range(nlay):
        istart = ilay * ncpl
        iend = (ilay + 1) * ncpl
        botm_disv[ilay, :] = bot[istart:iend]

    # Step 7: Optional validation of vertical alignment
    if validate_layered and nlay > 1:
        # Check that cells within each layer have consistent structure
        for ilay in range(nlay):
            istart = ilay * ncpl
            iend = (ilay + 1) * ncpl
            layer_tops = top[istart:iend]

            # Warn if top elevation variation within layer is large
            top_range = np.max(layer_tops) - np.min(layer_tops)
            top_mean = np.mean(layer_tops)

            if top_mean != 0 and top_range / abs(top_mean) > 0.1:
                warnings.warn(
                    f"Layer {ilay} has high top elevation variation "
                    f"(range={top_range:.2f}, mean={top_mean:.2f}). "
                    f"This may indicate the grid is not truly layered.",
                    UserWarning,
                )

        # Check that cell centers align horizontally across layers
        for ilay in range(1, nlay):
            for icell in range(ncpl):
                cell_layer0 = cell2d[icell]
                cell_layerN = cell2d[ilay * ncpl + icell]

                # Cell centers should align horizontally
                dx = abs(cell_layer0[1] - cell_layerN[1])
                dy = abs(cell_layer0[2] - cell_layerN[2])

                if dx > 1e-6 or dy > 1e-6:
                    raise ValueError(
                        f"Cell {icell} has different horizontal position in "
                        f"layer {ilay} (dx={dx:.2e}, dy={dy:.2e}). "
                        f"Grid is not vertically aligned. DISV requires "
                        f"vertical prism structure."
                    )

    # Step 8: Return DISV kwargs dict
    return {
        "nlay": nlay,
        "ncpl": ncpl,
        "nvert": nvert,
        "vertices": vertices_disv,
        "cell2d": cell2d_disv,
        "top": top_disv,
        "botm": botm_disv,
    }


def get_disu_kwargs_from_disv(
    nlay,
    ncpl,
    vertices,
    cell2d,
    top,
    botm,
    idomain=None,
):
    """
    Convert DISV grid parameters to DISU grid parameters.

    This function converts a layered vertex (DISV) grid to a fully unstructured
    (DISU) grid format. The resulting DISU grid will have the same layered
    structure as the original DISV grid.

    Parameters
    ----------
    nlay : int
        Number of layers
    ncpl : int
        Number of cells per layer
    vertices : list of tuples
        List of (iv, x, y) vertex tuples.
        From DISV VERTICES block.
    cell2d : list of lists
        List of cell2d records for single layer [icell, xc, yc, nvert, iv1, ...].
        From DISV CELL2D block.
    top : array_like
        Top elevation for cells in top layer (shape: ncpl).
        From DISV GRIDDATA block.
    botm : array_like
        Bottom elevations for all layers (shape: nlay, ncpl).
        From DISV GRIDDATA block.
    idomain : array_like, optional
        Integer array indicating cell status (shape: nlay, ncpl).
        Not directly used but can be included for reference.

    Returns
    -------
    dict
        Dictionary with keys compatible with ModflowGwfdisu:
        nodes, nja, nvert, top, bot, area, iac, ja, ihc, cl12, hwva,
        vertices, cell2d, angldegx

    Notes
    -----
    This function builds connectivity arrays for the DISU grid based on the
    DISV layered structure:

    - Vertical connections: Cells in the same horizontal position across layers
    - Horizontal connections: Cells that share edges in the same layer

    Horizontal connectivity is determined by analyzing which cells share vertices
    in the cell2d arrays. This requires geometric analysis of cell adjacency.

    The ihc array diagonal positions store layer numbers (1-based) to enable
    conversion back to DISV using get_disv_kwargs_from_disu().

    Examples
    --------
    >>> from flopy.utils.gridutil import get_disv_kwargs, get_disu_kwargs_from_disv
    >>> # Create DISV grid from structured grid
    >>> disv_kwargs = get_disv_kwargs(
    ...     nlay=2, nrow=5, ncol=5,
    ...     delr=100.0, delc=100.0,
    ...     tp=10.0, botm=[-10.0, -20.0]
    ... )
    >>> # Convert to DISU
    >>> disu_kwargs = get_disu_kwargs_from_disv(
    ...     nlay=disv_kwargs["nlay"],
    ...     ncpl=disv_kwargs["ncpl"],
    ...     vertices=disv_kwargs["vertices"],
    ...     cell2d=disv_kwargs["cell2d"],
    ...     top=disv_kwargs["top"],
    ...     botm=disv_kwargs["botm"]
    ... )
    >>> print(disu_kwargs["nodes"])
    50
    """
    # Convert to numpy arrays
    top = np.asarray(top, dtype=float)
    botm = np.asarray(botm, dtype=float)

    # Validate shapes
    if top.shape != (ncpl,):
        raise ValueError(f"top must have shape ({ncpl},), got {top.shape}")
    if botm.shape != (nlay, ncpl):
        raise ValueError(f"botm must have shape ({nlay}, {ncpl}), got {botm.shape}")

    # Step 1: Calculate total nodes
    nodes = nlay * ncpl

    # Step 2: Keep vertices as-is (DISU supports 2D vertices)
    nvert = len(vertices)

    # Step 3: Expand cell2d for all layers
    cell2d_disu = []
    for ilay in range(nlay):
        for icell, c2d in enumerate(cell2d):
            node = ilay * ncpl + icell
            xc = c2d[1]
            yc = c2d[2]
            nverts = c2d[3]
            iverts = c2d[4 : 4 + nverts]
            cell2d_disu.append([node, xc, yc, nverts] + list(iverts))

    # Step 4: Build horizontal connectivity by finding cells that share edges
    # A cell shares an edge with another if they share at least 2 vertices
    horizontal_neighbors = {}  # maps cell index to list of neighbor indices

    for icell, c2d in enumerate(cell2d):
        nverts_i = c2d[3]
        iverts_i = set(c2d[4 : 4 + nverts_i])
        neighbors = []

        for jcell, c2d_j in enumerate(cell2d):
            if icell == jcell:
                continue
            nverts_j = c2d_j[3]
            iverts_j = set(c2d_j[4 : 4 + nverts_j])

            # Cells share an edge if they have 2+ common vertices
            shared = iverts_i & iverts_j
            if len(shared) >= 2:
                neighbors.append(jcell)

        horizontal_neighbors[icell] = neighbors

    # Step 5: Build connectivity arrays (iac, ja, ihc, cl12, hwva, angldegx)
    iac = np.zeros(nodes, dtype=int)
    ja = []
    ihc = []
    cl12 = []
    hwva = []
    angldegx = []

    # Calculate cell areas from vertices
    areas = np.zeros(nodes, dtype=float)
    for icell, c2d in enumerate(cell2d):
        nverts = c2d[3]
        iverts = c2d[4 : 4 + nverts]
        # Calculate area using shoelace formula
        vlist = [(vertices[iv][1], vertices[iv][2]) for iv in iverts]
        area = (
            abs(
                sum(
                    vlist[i][0] * vlist[(i + 1) % len(vlist)][1]
                    - vlist[(i + 1) % len(vlist)][0] * vlist[i][1]
                    for i in range(len(vlist))
                )
            )
            / 2.0
        )
        # Replicate for all layers
        for ilay in range(nlay):
            areas[ilay * ncpl + icell] = area

    for ilay in range(nlay):
        for icell in range(ncpl):
            n = ilay * ncpl + icell

            # Diagonal (self) - store layer number (1-based)
            ja.append(n)
            ihc.append(ilay + 1)
            cl12.append(float(n + 1))
            hwva.append(float(n + 1))
            angldegx.append(float(n + 1))
            iac[n] += 1

            # Vertical connections
            # Up connection
            if ilay > 0:
                m = (ilay - 1) * ncpl + icell
                ja.append(m)
                ihc.append(0)  # Vertical connection

                # Connection length (half of vertical distance)
                if ilay == 1:
                    dz = top[icell] - botm[0, icell]
                else:
                    dz = botm[ilay - 2, icell] - botm[ilay - 1, icell]
                cl12.append(0.5 * abs(dz))

                # Flow area
                hwva.append(areas[n])
                angldegx.append(0.0)
                iac[n] += 1

            # Down connection
            if ilay < nlay - 1:
                m = (ilay + 1) * ncpl + icell
                ja.append(m)
                ihc.append(0)  # Vertical connection

                # Connection length
                if ilay == 0:
                    dz = top[icell] - botm[0, icell]
                else:
                    dz = botm[ilay - 1, icell] - botm[ilay, icell]
                cl12.append(0.5 * abs(dz))

                # Flow area
                hwva.append(areas[n])
                angldegx.append(0.0)
                iac[n] += 1

            # Horizontal connections
            for jcell in horizontal_neighbors[icell]:
                m = ilay * ncpl + jcell
                ja.append(m)
                ihc.append(1)  # Horizontal connection

                # Connection length (distance between cell centers)
                xc_i, yc_i = cell2d[icell][1], cell2d[icell][2]
                xc_j, yc_j = cell2d[jcell][1], cell2d[jcell][2]
                dist = np.sqrt((xc_j - xc_i) ** 2 + (yc_j - yc_i) ** 2)
                cl12.append(0.5 * dist)

                # Approx flow width: avg of cell perimeters / number of neighbors
                # This is a simplification - ideally would calculate shared edge length
                perim_i = 4.0 * np.sqrt(areas[n])  # Rough approximation
                hwva.append(perim_i / len(horizontal_neighbors[icell]))

                # Angle (calculate from cell center positions)
                angle = np.degrees(np.arctan2(yc_j - yc_i, xc_j - xc_i))
                if angle < 0:
                    angle += 360
                angldegx.append(angle)
                iac[n] += 1

    ja = np.array(ja, dtype=int)
    nja = len(ja)
    ihc = np.array(ihc, dtype=int)
    cl12 = np.array(cl12, dtype=float)
    hwva = np.array(hwva, dtype=float)
    angldegx = np.array(angldegx, dtype=float)

    # Step 6: Flatten top array
    # DISU top: layer 0 uses top, other layers use botm of layer above
    top_disu = np.zeros(nodes, dtype=float)
    for ilay in range(nlay):
        for icell in range(ncpl):
            n = ilay * ncpl + icell
            if ilay == 0:
                top_disu[n] = top[icell]
            else:
                top_disu[n] = botm[ilay - 1, icell]

    # Step 7: Flatten bot array
    bot_disu = botm.flatten()

    # Step 8: Return DISU kwargs dict
    return {
        "nodes": nodes,
        "nja": nja,
        "nvert": nvert,
        "top": top_disu,
        "bot": bot_disu,
        "area": areas,
        "iac": iac,
        "ja": ja,
        "ihc": ihc,
        "cl12": cl12,
        "hwva": hwva,
        "vertices": vertices,
        "cell2d": cell2d_disu,
        "angldegx": angldegx,
    }


def uniform_flow_field(qx, qy, qz, shape, delr=None, delc=None, delv=None):
    nlay, nrow, ncol = shape

    # create spdis array for the uniform flow field
    dt = np.dtype(
        [
            ("ID1", np.int32),
            ("ID2", np.int32),
            ("FLOW", np.float64),
            ("QX", np.float64),
            ("QY", np.float64),
            ("QZ", np.float64),
        ]
    )
    spdis = np.array(
        [(id1, id1, 0.0, qx, qy, qz) for id1 in range(nlay * nrow * ncol)],
        dtype=dt,
    )

    # create the flowja array for the uniform flow field (assume top-bot = 1)
    flowja = []
    if delr is None:
        delr = 1.0
    if delc is None:
        delc = 1.0
    if delv is None:
        delv = 1.0
    for k in range(nlay):
        for i in range(nrow):
            for j in range(ncol):
                # diagonal
                flowja.append(0.0)
                # up
                if k > 0:
                    flowja.append(-qz * delr * delc)
                # back
                if i > 0:
                    flowja.append(-qy * delr * delv)
                # left
                if j > 0:
                    flowja.append(qx * delc * delv)
                # right
                if j < ncol - 1:
                    flowja.append(-qx * delc * delv)
                # front
                if i < nrow - 1:
                    flowja.append(qy * delr * delv)
                # bottom
                if k < nlay - 1:
                    flowja.append(qz * delr * delc)
    flowja = np.array(flowja, dtype=np.float64)
    return spdis, flowja
