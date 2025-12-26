# Implementation Plan: Extend FloPy `UnstructuredGrid.from_gridspec()` for Complete DISU Support

## Executive Summary

Extend FloPy's `UnstructuredGrid.from_gridspec()` method to compute all MODFLOW 6 DISU connection properties (iac, ja, ihc, cl12, hwva) from grid specification file (GSF) geometry alone, eliminating the dependency on auxiliary gridgen output files.

**Repository:** FloPy (https://github.com/modflowpy/flopy)
**Target File:** `flopy/discretization/unstructuredgrid.py`

## Background

**Current State:**
- `from_gridspec()` reads vertices, cell centers, and geometry from GSF files
- Does NOT compute connectivity arrays (iac, ja, ihc, cl12, hwva)
- Limits use case to visualization only, not full DISU model creation

**Goal:**
- Enable reliable GSF → complete DISU conversion
- Maintain compatibility with existing gridgen-generated values
- Provide validation/comparison tools for debugging

**Implementation Strategy:** Minimal viable implementation, then iterate based on testing and feedback.

## Key Design Decisions

### Vertical Connectivity Strategy

**Challenge:** Find all cells in layer L+1 whose 2D footprint overlaps with cell C in layer L.

**Solution:** Hybrid approach based on grid structure:

1. **Uniform layering (ncpl constant):** Direct indexing - O(ncpl)
   - Cell at position i in layer L connects to cell at position i in layer L+1
   - Fast path for structured vertical stacking

2. **Variable/unstructured layering:** GeoPandas spatial join - O(N log N)
   - Create 2D polygon geometries for cells in adjacent layers
   - Use R-tree spatial index to find overlapping polygons
   - Handles DISV (varying cell sizes) and DISU (fully unstructured)

**Implementation:**
```python
def _find_vertical_neighbors(grid):
    """Find vertical connections using 2D spatial overlap."""
    import geopandas as gpd
    from shapely.geometry import Polygon

    vertical_neighbors = {i: [] for i in range(grid.nnodes)}

    # Single-layer grid - no vertical connections
    if len(grid.ncpl) == 1:
        return vertical_neighbors

    # Fast path for uniform layering
    if np.all(np.diff(grid.ncpl) == 0):
        ncpl = grid.ncpl[0]
        for layer in range(len(grid.ncpl) - 1):
            for i in range(ncpl):
                cell_top = layer * ncpl + i
                cell_bot = (layer + 1) * ncpl + i
                vertical_neighbors[cell_top].append(cell_bot)
                vertical_neighbors[cell_bot].append(top_cell)
        return vertical_neighbors

    # General case: spatial join
    for layer_idx in range(len(grid.ncpl) - 1):
        cells_top = grid.get_layer_cell_ids(layer_idx)
        cells_bot = grid.get_layer_cell_ids(layer_idx + 1)

        polys_top = [Polygon(grid.get_cell_verts_2d(c)) for c in cells_top]
        polys_bot = [Polygon(grid.get_cell_verts_2d(c)) for c in cells_bot]

        gdf_top = gpd.GeoDataFrame({'cell': cells_top}, geometry=polys_top)
        gdf_bot = gpd.GeoDataFrame({'cell': cells_bot}, geometry=polys_bot)

        # Spatial join uses R-tree index automatically
        overlaps = gpd.sjoin(gdf_top, gdf_bot, predicate='intersects')

        for _, row in overlaps.iterrows():
            top_cell = row['cell_left']
            bot_cell = row['cell_right']
            vertical_neighbors[top_cell].append(bot_cell)
            vertical_neighbors[bot_cell].append(top_cell)

    return vertical_neighbors
```

**Why GeoPandas:**
- Properly handles polygon-polygon overlap (the actual requirement)
- R-tree spatial index provides O(log N) candidate search
- Already a FloPy dependency
- Works for all DISV/DISU cases (irregular, varying ncpl, pinched layers)

**See:** `vert_connections.txt` for detailed analysis of alternatives (KDTree, CellTree2D, naive loops).

### hwva Calculation Method

**Challenge:** Horizontal flow width depends on cell thickness, but cells may have different thicknesses.

**Solution:** Allow user to choose calculation method via parameter:

1. **'average'** (default): `hwva = edge_length × (dz_n + dz_m) / 2`
   - Matches gridgen behavior
   - Simple, fast, good for most cases

2. **'geometric'**: Compute true 3D face area using vertex z-coordinates
   - More accurate for extreme thickness variations
   - Uses available `zverts` data from GSF file
   - Computationally more expensive

**Implementation:** Add `hwva_method` parameter to `from_gridspec()`

## Implementation Phases

### Phase 1: Core Connectivity (iac, ja)

**Objective:** Compute cell connectivity from shared vertex/edge geometry

#### 1.1: Create Helper Function `_neighbors_to_iac_ja()`

**Location:** `flopy/discretization/unstructuredgrid.py`

**Signature:**
```python
@staticmethod
def _neighbors_to_iac_ja(neighbors_dict, nnodes):
    """
    Convert neighbor dictionary to iac and ja arrays for DISU.

    Parameters
    ----------
    neighbors_dict : dict
        Dictionary mapping {cell_id: [neighbor_cell_ids]}
    nnodes : int
        Total number of nodes

    Returns
    -------
    iac : ndarray of int, shape (nnodes,)
        Number of connections (+1 for self) for each cell
    ja : ndarray of int, shape (nja,)
        Flattened connectivity list in MODFLOW 6 format
    """
```

**Algorithm:**
1. For each cell n:
   - `iac[n] = 1 + len(neighbors_dict[n])` (self + neighbors)
2. Build ja array:
   - For each cell n:
     - Append n (self-connection)
     - Append sorted list of neighbors
3. Return iac, ja

**Validation:**
- Sum of iac should equal len(ja) (= nja)
- Each cell should appear first in its own ja entry
- Neighbors should be sorted

#### 1.2: Add Vertical Connectivity Helper

**Location:** `flopy/discretization/unstructuredgrid.py`

See "Key Design Decisions > Vertical Connectivity Strategy" above for full implementation.

**Key points:**
- Use direct indexing for uniform ncpl (fast path)
- Use GeoPandas spatial join for variable/unstructured grids
- Return dict: `{cell_id: [vertically_connected_cells]}`

#### 1.3: Modify `from_gridspec()` to Compute Connectivity

**Changes:**
```python
@classmethod
def from_gridspec(cls, file_path, compute_connections=True,
                  top=None, bot=None, top_bot_method='minmax'):
    # ... existing code to read GSF ...

    # Derive or use provided top/bot
    if top is None or bot is None:
        # Derive from vertex z-coordinates
        if top_bot_method == 'minmax':
            top_derived = [max(cell_vertex_z) for cell in cells]
            bot_derived = [min(cell_vertex_z) for cell in cells]
        else:
            raise ValueError(f"Unknown top_bot_method: {top_bot_method}")

        if top is None:
            top = np.array(top_derived)
        if bot is None:
            bot = np.array(bot_derived)

    if compute_connections:
        # Create temporary grid instance
        temp_grid = cls(
            vertices=vertices,
            iverts=iverts,
            xcenters=np.array(xcenters),
            ycenters=np.array(ycenters),
            ncpl=ncpl,
            top=np.array(top),
            botm=np.array(bot),
        )

        # Compute HORIZONTAL neighbors using existing Grid method
        temp_grid._set_neighbors(method="rook")
        horizontal_neighbors = temp_grid._neighbors

        # Compute VERTICAL neighbors using spatial overlap
        vertical_neighbors = cls._find_vertical_neighbors(temp_grid)

        # Merge horizontal and vertical neighbors
        all_neighbors = {i: [] for i in range(nnodes)}
        for cell_id in range(nnodes):
            all_neighbors[cell_id] = (
                horizontal_neighbors.get(cell_id, []) +
                vertical_neighbors.get(cell_id, [])
            )

        # Convert to iac/ja format
        iac, ja = cls._neighbors_to_iac_ja(all_neighbors, nnodes)
    else:
        iac = None
        ja = None

    return cls(
        vertices=vertices,
        iverts=iverts,
        xcenters=np.array(xcenters),
        ycenters=np.array(ycenters),
        ncpl=ncpl,
        top=np.array(top),
        botm=np.array(bot),
        iac=iac,
        ja=ja,
    )
```

**Testing:**
- Load a GSF with known connectivity
- Verify horizontal connections (shared edges within layer)
- Verify vertical connections (overlapping cells between layers)
- Compare computed iac/ja against gridgen output
- Verify symmetry: if n connects to m, then m connects to n

---

### Phase 2: Connection Type Indicator (ihc)

**Objective:** Determine horizontal (1), vertical (0), or staggered (2) connections

#### 2.1: Create Helper Function `_compute_ihc()`

**Location:** `flopy/discretization/unstructuredgrid.py`

**Signature:**
```python
@staticmethod
def _compute_ihc(iac, ja, layers, iverts, vertices):
    """
    Compute connection type indicator array.

    Parameters
    ----------
    iac : ndarray of int
        Connections per cell
    ja : ndarray of int
        Connectivity array
    layers : list or ndarray
        Layer number for each cell
    iverts : list of lists
        Vertex indices for each cell
    vertices : ndarray
        Vertex coordinates (iv, x, y)

    Returns
    -------
    ihc : ndarray of int, shape (nja,)
        Connection type:
        - 0: vertical
        - 1: horizontal (regular)
        - 2: horizontal (vertically staggered)
        - Diagonal entries: layer number
    """
```

**Algorithm:**
1. Initialize ihc array (size = nja)
2. Set up ia array: `ia = get_ia_from_iac(iac)`
3. For each cell n and connection to cell m:
   - **Diagonal entry (n == m):** `ihc[ipos] = layers[n]`
   - **Different layers:** `ihc[ipos] = 0` (vertical)
   - **Same layer:**
     - Check if cells share an edge (consecutive vertices in both iverts)
     - If share edge: `ihc[ipos] = 1` (horizontal)
     - If share only vertices: `ihc[ipos] = 2` (staggered)

**Helper needed:**
```python
def _cells_share_edge(iverts_n, iverts_m):
    """
    Check if two cells share an edge (pair of consecutive vertices).
    Returns True if they share an edge, False if only vertices.
    """
    # Check all consecutive vertex pairs in cell n
    for i in range(len(iverts_n)):
        v1 = iverts_n[i]
        v2 = iverts_n[(i + 1) % len(iverts_n)]
        edge = {v1, v2}

        # Check if this edge exists in cell m
        for j in range(len(iverts_m)):
            vm1 = iverts_m[j]
            vm2 = iverts_m[(j + 1) % len(iverts_m)]
            edge_m = {vm1, vm2}

            if edge == edge_m:
                return True
    return False
```

**Testing:**
- Vertical connections between layers should have ihc=0
- Horizontal connections in same layer should have ihc=1
- Diagonal entries should match layer numbers
- Compare against gridgen output

---

### Phase 3: Connection Lengths (cl12)

**Objective:** Compute distance from cell center to shared face center

#### 3.1: Create Helper Function `_compute_cl12()`

**Location:** `flopy/discretization/unstructuredgrid.py`

**Signature:**
```python
@staticmethod
def _compute_cl12(iac, ja, xcenters, ycenters, iverts, vertices):
    """
    Compute connection lengths (cell center to shared face center).

    Parameters
    ----------
    iac : ndarray of int
        Connections per cell
    ja : ndarray of int
        Connectivity array
    xcenters, ycenters : ndarray
        Cell center coordinates
    iverts : list of lists
        Vertex indices for each cell
    vertices : ndarray
        Vertex coordinates (iv, x, y)

    Returns
    -------
    cl12 : ndarray of float, shape (nja,)
        Distance from cell center to shared face center
        Diagonal entries are typically set to 0
    """
```

**Algorithm:**
1. Initialize cl12 array (size = nja)
2. Set up ia array: `ia = get_ia_from_iac(iac)`
3. For each cell n and connection to cell m:
   - **Diagonal entry (n == m):** `cl12[ipos] = 0.0`
   - **Off-diagonal:**
     1. Find shared vertices between cells n and m
     2. Compute shared face center:
        - **Vertical connection:** Average of shared polygon vertices
        - **Horizontal connection:** Midpoint of shared edge
     3. Compute distance: `cl12[ipos] = distance(cell_center_n, face_center)`

**Helper functions:**
```python
def _find_shared_vertices(iverts_n, iverts_m):
    """Return set of vertex indices shared by both cells."""
    return set(iverts_n) & set(iverts_m)

def _compute_face_center(shared_verts, vertices):
    """
    Compute center of shared face.

    Parameters
    ----------
    shared_verts : set or list
        Indices of vertices forming the shared face
    vertices : ndarray
        Vertex coordinates

    Returns
    -------
    xf, yf, zf : float
        Face center coordinates (use zverts if available)
    """
    xs = [vertices[v, 1] for v in shared_verts]  # x coords
    ys = [vertices[v, 2] for v in shared_verts]  # y coords
    return np.mean(xs), np.mean(ys)
```

**Testing:**
- cl12 should be symmetric: cl12[n→m] should roughly equal cl12[m→n]
- Values should be positive (except diagonal)
- Sum cl12[n→m] + cl12[m→n] should approximately equal distance between cell centers
- Compare against gridgen output

---

### Phase 4: Flow Widths/Areas (hwva)

**Objective:** Compute horizontal flow widths and vertical flow areas

#### 4.1: Create Helper Function `_compute_hwva()` (Simple Version)

**Location:** `flopy/discretization/unstructuredgrid.py`

**Signature:**
```python
@staticmethod
def _compute_hwva(iac, ja, ihc, iverts, vertices, top, bot, method='average'):
    """
    Compute horizontal flow widths and vertical flow areas.

    Parameters
    ----------
    iac : ndarray of int
        Connections per cell
    ja : ndarray of int
        Connectivity array
    ihc : ndarray of int
        Connection type indicator
    iverts : list of lists
        Vertex indices for each cell
    vertices : ndarray
        Vertex coordinates (iv, x, y)
    top, bot : ndarray
        Cell top and bottom elevations
    method : str, optional
        'average' (default): use average thickness (matches gridgen)
        'geometric': compute true 3D face areas (future enhancement)

    Returns
    -------
    hwva : ndarray of float, shape (nja,)
        For horizontal connections: flow width (length dimension)
        For vertical connections: flow area (area dimension)
        Diagonal entries are typically set to 0
    """
```

**Algorithm (Optimized - Compute Once Per Connection):**

1. Initialize hwva array (size = nja) and processed connections set
2. Set up ia array: `ia = get_ia_from_iac(iac)`
3. Iterate through ja array:
   - Get connection n→m at position ipos
   - **If n == m (diagonal):** `hwva[ipos] = 0.0`, continue
   - **If connection already processed:** Skip (symmetry already handled)
   - **Else (first time seeing n↔m):**
     - Compute hwva value once:
       - **Vertical (ihc == 0):** `value = polygon_area(shared_vertices)`
       - **Horizontal (ihc == 1 or 2):** `value = edge_length × avg_thickness`
     - Find position of reverse connection (m→n)
     - Set both directions: `hwva[pos_n_to_m] = hwva[pos_m_to_n] = value`
     - Mark connection as processed: `processed.add(frozenset([n, m]))`

**Benefits:**
- Perfect symmetry guaranteed (same value for both directions)
- ~2x faster (each connection computed only once)
- No post-processing symmetry repair needed

**Helper functions:**
```python
def _find_shared_edge(iverts_n, iverts_m):
    """
    Find the shared edge between two horizontally adjacent cells.

    Returns
    -------
    v1, v2 : int
        Vertex indices forming the shared edge (or None if no edge shared)
    """
    for i in range(len(iverts_n)):
        edge_n = {iverts_n[i], iverts_n[(i + 1) % len(iverts_n)]}
        for j in range(len(iverts_m)):
            edge_m = {iverts_m[j], iverts_m[(j + 1) % len(iverts_m)]}
            if edge_n == edge_m:
                return tuple(edge_n)
    return None, None

def _compute_polygon_area(vert_indices, vertices):
    """
    Compute area of polygon defined by vertex indices.
    Uses Shapely for robustness.
    """
    from shapely.geometry import Polygon
    coords = [(vertices[v, 1], vertices[v, 2]) for v in vert_indices]
    poly = Polygon(coords)
    return poly.area
```

**Finding Reverse Connection Position:**

Helper function to find the position of the reverse connection (m→n) given (n→m):

```python
def _find_reverse_connection(n, m, ja, ia):
    """
    Find position in ja array where cell m connects to cell n.

    Parameters
    ----------
    n, m : int
        Cell indices
    ja : ndarray
        Connectivity array
    ia : ndarray
        Index array from iac

    Returns
    -------
    int
        Position in ja array where m→n connection is stored
    """
    # Search m's connections for n
    for ipos in range(ia[m], ia[m + 1]):
        if ja[ipos] == n:
            return ipos
    raise ValueError(f"Reverse connection {m}→{n} not found")
```

**Testing:**
- hwva should be perfectly symmetric (guaranteed by algorithm)
- Horizontal connection values should have length dimension
- Vertical connection values should have area dimension
- Compare against gridgen output

#### 4.2: Enhanced Version (True 3D Face Areas) - Future Work

**Objective:** Compute actual 3D face areas using vertex z-coordinates

**Algorithm:**
1. For vertical connections:
   - Same as simple version (2D polygon area is correct)
2. For horizontal connections:
   - Get shared edge vertices with their z-coordinates
   - Construct 3D quadrilateral:
     - Top corners: `(x1, y1, top[n])`, `(x2, y2, top[n])`
     - Bottom corners: `(x1, y1, bot[n])`, `(x2, y2, bot[n])`
   - Compute 3D face area
   - This accounts for non-uniform thickness

**Note:** This requires storing z-coordinates for vertices, which may not always be available in GSF files.

---

### Phase 5: Integration and Testing

#### 5.1: Integrate All Components

**Modify `from_gridspec()` final version:**

```python
@classmethod
def from_gridspec(cls, file_path, compute_connections=True,
                  top=None, bot=None, top_bot_method='minmax',
                  hwva_method='average'):
    """
    Create an UnstructuredGrid from a grid specification file.

    Parameters
    ----------
    file_path : str or PathLike
        Path to the grid specification file
    compute_connections : bool, optional
        If True, compute DISU connection properties (iac, ja, ihc, cl12, hwva)
        If False, only read geometry (vertices, iverts, centers, top, bot)
        Default is True.
    top : array-like, optional
        Cell top elevations. If None, derived from vertex z-coordinates
        using top_bot_method.
    bot : array-like, optional
        Cell bottom elevations. If None, derived from vertex z-coordinates
        using top_bot_method.
    top_bot_method : str, optional
        Method for deriving top/bot from vertex z-coordinates if not provided:
        - 'minmax' (default): top=max(vertex_z), bot=min(vertex_z)
        Ignored if top and bot are both provided.
    hwva_method : str, optional
        Method for computing hwva (horizontal flow widths/vertical flow areas):
        - 'average': Use average cell thickness (matches gridgen, default)
        - 'geometric': Compute true 3D face areas using vertex z-coordinates
        Only used if compute_connections is True.

    Returns
    -------
    UnstructuredGrid
        Grid with full DISU connection properties (if compute_connections=True)

    Notes
    -----
    **Limitations:**
    - Connectivity assumes cells sharing vertices/edges are connected
      (works for gridgen, quadtree, Voronoi; may not work for arbitrary DISU)
    - Cell top/bot cannot be deterministically inferred from vertices alone
      (provide explicit arrays if default derivation is incorrect)
    """

    # ... existing GSF reading code ...

    # Derive or use provided top/bot
    if top is None or bot is None:
        # Derive from vertex z-coordinates
        if top_bot_method == 'minmax':
            top_derived = [max(cell_zverts) for cell_zverts in zverts_per_cell]
            bot_derived = [min(cell_zverts) for cell_zverts in zverts_per_cell]
        else:
            raise ValueError(f"Unknown top_bot_method: {top_bot_method}")

        if top is None:
            top = np.array(top_derived)
        if bot is None:
            bot = np.array(bot_derived)

    if compute_connections:
        # Create temporary grid to compute neighbors
        temp_grid = cls(
            vertices=vertices,
            iverts=iverts,
            xcenters=np.array(xcenters),
            ycenters=np.array(ycenters),
            ncpl=ncpl,
            top=np.array(top),
            botm=np.array(bot),
        )

        # Phase 1: Compute connectivity (horizontal + vertical)
        # Horizontal neighbors from shared edges within layer
        temp_grid._set_neighbors(method="rook")
        horizontal_neighbors = temp_grid._neighbors

        # Vertical neighbors from 2D footprint overlap between layers
        vertical_neighbors = cls._find_vertical_neighbors(temp_grid)

        # Merge horizontal and vertical neighbors
        all_neighbors = {i: [] for i in range(nnodes)}
        for cell_id in range(nnodes):
            all_neighbors[cell_id] = (
                horizontal_neighbors.get(cell_id, []) +
                vertical_neighbors.get(cell_id, [])
            )

        # Convert to iac/ja format
        iac, ja = cls._neighbors_to_iac_ja(all_neighbors, nnodes)

        # Phase 2: Compute connection type indicator
        ihc = cls._compute_ihc(iac, ja, layers, iverts, vertices)

        # Phase 3: Compute connection lengths
        cl12 = cls._compute_cl12(iac, ja, xcenters, ycenters, iverts, vertices)

        # Phase 4: Compute flow widths/areas (symmetry guaranteed by algorithm)
        hwva = cls._compute_hwva(
            iac, ja, ihc, iverts, vertices, top, bot,
            method=hwva_method
        )
    else:
        iac = None
        ja = None

    return cls(
        vertices=vertices,
        iverts=iverts,
        xcenters=np.array(xcenters),
        ycenters=np.array(ycenters),
        ncpl=ncpl,
        top=np.array(top),
        botm=np.array(bot),
        iac=iac,
        ja=ja,
    )
```

#### 5.2: Create Comparison/Validation Utility

**New function:** `compare_with_gridgen_output()`

```python
def compare_connection_arrays(gsf_path, gridgen_ws, tolerance=1e-6):
    """
    Compare connection arrays computed from GSF against gridgen output.

    Parameters
    ----------
    gsf_path : str or PathLike
        Path to grid specification file
    gridgen_ws : str or PathLike
        Directory containing gridgen output files (qtg.*.dat)
    tolerance : float
        Tolerance for floating-point comparisons

    Returns
    -------
    comparison_report : dict
        Dictionary with comparison results for each array
    """
    # Load from GSF
    grid_gsf = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=True)

    # Load from gridgen
    from ..utils.gridgen import Gridgen
    g = Gridgen(...)  # Load gridgen instance
    iac_gridgen = g.get_iac()
    ja_gridgen = g.get_ja()
    ihc_gridgen = g.get_ihc()
    cl12_gridgen = g.get_cl12()
    hwva_gridgen = g.get_hwva()

    # Compare
    report = {
        'iac': {
            'match': np.allclose(grid_gsf.iac, iac_gridgen),
            'max_diff': np.max(np.abs(grid_gsf.iac - iac_gridgen)),
        },
        'ja': {
            'match': np.allclose(grid_gsf.ja, ja_gridgen),
            'max_diff': np.max(np.abs(grid_gsf.ja - ja_gridgen)),
        },
        'ihc': {
            'match': np.allclose(grid_gsf.ihc, ihc_gridgen),
            'differences': np.sum(grid_gsf.ihc != ihc_gridgen),
        },
        'cl12': {
            'match': np.allclose(grid_gsf.cl12, cl12_gridgen, rtol=tolerance),
            'max_diff': np.max(np.abs(grid_gsf.cl12 - cl12_gridgen)),
            'mean_diff': np.mean(np.abs(grid_gsf.cl12 - cl12_gridgen)),
        },
        'hwva': {
            'match': np.allclose(grid_gsf.hwva, hwva_gridgen, rtol=tolerance),
            'max_diff': np.max(np.abs(grid_gsf.hwva - hwva_gridgen)),
            'mean_diff': np.mean(np.abs(grid_gsf.hwva - hwva_gridgen)),
        },
    }

    return report
```

#### 5.3: Test Suite

**Test files needed:**

1. **`test_gsf_to_disu.py`** - Unit tests for each helper function
   - Test `_neighbors_to_iac_ja()` with simple grids
   - Test `_compute_ihc()` for horizontal/vertical/staggered connections
   - Test `_compute_cl12()` for known geometries
   - Test `_compute_hwva()` against analytical solutions

2. **`test_gsf_gridgen_comparison.py`** - Integration tests
   - Load existing GSF files from examples
   - Compare computed values against gridgen output
   - Tolerance tests for floating-point differences

3. **`test_gsf_to_mf6.py`** - End-to-end tests
   - Create MODFLOW 6 DISU model from GSF
   - Run simulation
   - Verify model runs successfully
   - Compare results with gridgen-based model

**Test data needed:**
- Simple rectangular grid (2×2 cells, 2 layers)
- Voronoi grid (irregular polygons)
- Quadtree grid (varying cell sizes)
- Complex grid with pinched layers

---

### Phase 6: Documentation and Examples

#### 6.1: Update Docstrings

- Add detailed parameter descriptions
- Include usage examples
- Document limitations and assumptions
- Add references to MODFLOW 6 documentation

#### 6.2: Create Tutorial Notebook

**`notebooks/gsf_to_disu_example.ipynb`**

Content:
1. Introduction to GSF files
2. Loading a GSF with `from_gridspec()`
3. Inspecting computed connection arrays
4. Creating a MODFLOW 6 DISU model
5. Comparison with gridgen workflow
6. Troubleshooting common issues

#### 6.3: Update FloPy Documentation

Add section to "Working with Unstructured Grids" covering:
- When to use `from_gridspec()`
- Advantages over gridgen workflow
- Validation recommendations
- Known limitations

---

## Implementation Priorities

### High Priority (Must Have)
1. ✅ Phase 1: iac, ja computation
2. ✅ Phase 2: ihc computation
3. ✅ Phase 3: cl12 computation
4. ✅ Phase 4.1: hwva computation (simple version)
5. ✅ Phase 5.1: Integration
6. ✅ Phase 5.3: Basic test suite

### Medium Priority (Should Have)
7. Phase 5.2: Comparison utility
8. Phase 6.1: Documentation
9. Phase 6.2: Tutorial notebook

### Low Priority (Nice to Have)
10. Phase 4.2: Enhanced hwva with 3D faces
11. Performance optimization for large grids
12. Support for other GSF variants

---

## Technical Considerations

### Dependencies
- **Required:** numpy, shapely (already in FloPy)
- **Optional:** scipy (for advanced geometry calculations)

### Performance
- **Target:** Handle grids with 100,000+ cells
- **Strategy:**
  - Vectorize where possible
  - Use spatial indexing for neighbor searches (if needed)
  - Profile and optimize bottlenecks

### Geometric Assumptions
- **Planar faces:** All cell faces assumed planar (consistent with MODFLOW-USG/MODFLOW 6 design)
- **2D operations:** Use Shapely for polygon areas, edge lengths, centroids
- **No curved boundaries:** Cell boundaries defined by straight edges between vertices

### Error Handling
- Validate GSF format
- Check for degenerate cells (zero area/volume)
- Provide helpful error messages
- Warn if single-layer grid detected (info only, not an error)

### Backwards Compatibility
- `compute_connections` parameter defaults to True
- Old behavior: `from_gridspec(path, compute_connections=False)`
- New behavior: `from_gridspec(path)` gives full DISU support

---

## Success Criteria

1. **Correctness:** Connection arrays match gridgen output within tolerance (< 0.1% difference)
2. **Completeness:** All DISU arrays (iac, ja, ihc, cl12, hwva) computed
3. **Robustness:** Handles various grid types (Voronoi, quadtree, triangular)
4. **Performance:** Processes 10,000-cell grid in < 5 seconds
5. **Usability:** Clear documentation and examples
6. **Testing:** >90% code coverage for new functions

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| hwva values don't match gridgen exactly | Medium | Accept small differences; document approach; provide comparison tool |
| Complex geometries cause edge cases | Medium | Extensive testing; robust error handling; fallback to gridgen |
| Performance issues with large grids | Low | Profile and optimize; consider Cython for hotspots |
| Breaking changes to existing code | High | Use optional parameter; maintain backwards compatibility |
| GSF format variations not handled | Medium | Document supported formats; provide validation |

---

## Timeline Estimate

**Minimal Viable Implementation (Iterative Approach):**

- **Sprint 1** (1-2 weeks): Core connectivity (iac, ja with horizontal + vertical)
  - Implement `_neighbors_to_iac_ja()`
  - Implement `_find_vertical_neighbors()` with both fast and general paths
  - Basic testing with simple GSF file

- **Sprint 2** (1 week): Connection properties (ihc, cl12)
  - Implement `_compute_ihc()`
  - Implement `_compute_cl12()`
  - Test against gridgen output

- **Sprint 3** (1-2 weeks): Flow widths/areas (hwva)
  - Implement `_compute_hwva()` with 'average' method
  - Implement symmetry enforcement
  - Validation tests

- **Sprint 4** (1 week): Integration and refinement
  - End-to-end testing with MODFLOW 6
  - Bug fixes and edge case handling
  - Basic documentation

**Total for MVP:** 4-6 weeks

**Future iterations:**
- Enhanced hwva with 'geometric' method
- Performance optimization
- Comprehensive documentation and examples
- Additional grid type testing
- **GSF export capability** (see Phase 7 below)

---

## Phase 7: GSF Export Capability (Future Enhancement)

**Objective:** Add ability to export FloPy grids to GSF format for round-trip testing and MODFLOW-USG compatibility

### 7.1: Add `to_gridspec()` Method

**Target classes:**
- `UnstructuredGrid` (DISU-like)
- `VertexGrid` (DISV)
- `VoronoiGrid`
- (Optional) `StructuredGrid` (DIS) - requires conversion to unstructured

**Signature:**
```python
def to_gridspec(self, filename, vertex_z=None, vertex_z_method='top'):
    """
    Export grid to GSF (Grid Specification File) format.

    Parameters
    ----------
    filename : str or PathLike
        Output GSF file path
    vertex_z : array-like, optional
        Z-coordinates for vertices. If None, derived from cell top/bot
        using vertex_z_method. Shape: (nvert,)
    vertex_z_method : str, optional
        Method for deriving vertex z-coordinates if not provided:
        - 'top': Use cell top elevations for vertices (default)
        - 'bot': Use cell bottom elevations for vertices
        - 'interp': Interpolate from surrounding cell top/bot
        Ignored if vertex_z is provided.

    Notes
    -----
    MODFLOW 6 DISU grids don't store vertex z-coordinates, so they
    must be inferred or provided explicitly for GSF export.
    """
```

**Algorithm:**
```python
def to_gridspec(self, filename, vertex_z=None, vertex_z_method='top'):
    # Derive vertex z if not provided
    if vertex_z is None:
        if vertex_z_method == 'top':
            vertex_z = self._derive_vertex_z_from_top()
        elif vertex_z_method == 'bot':
            vertex_z = self._derive_vertex_z_from_bot()
        elif vertex_z_method == 'interp':
            vertex_z = self._interpolate_vertex_z()
        else:
            raise ValueError(f"Unknown vertex_z_method: {vertex_z_method}")

    with open(filename, 'w') as f:
        # Write header
        f.write("UNSTRUCTURED\n")

        # Write dimensions
        f.write(f"{self.nnodes}\n")
        f.write(f"{len(self.vertices)}\n")

        # Write vertices with z-coordinates
        for iv, (idx, x, y) in enumerate(self.vertices):
            f.write(f"{x:.10f} {y:.10f} {vertex_z[iv]:.10f}\n")

        # Write cell definitions
        for icell in range(self.nnodes):
            xc = self.xcellcenters[icell]
            yc = self.ycellcenters[icell]
            layer = self._get_cell_layer(icell)
            iverts = self.iverts[icell]

            # GSF uses 1-based indexing
            f.write(f"{icell+1} {xc:.10f} {yc:.10f} {layer} {len(iverts)}")
            for iv in iverts:
                f.write(f" {iv+1}")
            f.write("\n")
```

**Helper methods:**
```python
def _derive_vertex_z_from_top(self):
    """Assign each vertex the top elevation of its containing cell(s)."""
    vertex_z = np.zeros(len(self.vertices))
    vertex_cell_map = self._build_vertex_to_cells_map()

    for iv in range(len(self.vertices)):
        cells = vertex_cell_map[iv]
        # Use average top of all cells sharing this vertex
        vertex_z[iv] = np.mean([self.top[cell] for cell in cells])

    return vertex_z

def _derive_vertex_z_from_bot(self):
    """Assign each vertex the bottom elevation of its containing cell(s)."""
    vertex_z = np.zeros(len(self.vertices))
    vertex_cell_map = self._build_vertex_to_cells_map()

    for iv in range(len(self.vertices)):
        cells = vertex_cell_map[iv]
        vertex_z[iv] = np.mean([self.botm[cell] for cell in cells])

    return vertex_z

def _interpolate_vertex_z(self):
    """
    Interpolate vertex z from surrounding cells.
    For vertices on layer interfaces, use interpolation.
    """
    # More complex: consider layer structure, interpolate between top/bot
    # This could use geometric interpolation based on vertex position
    pass

def _build_vertex_to_cells_map(self):
    """Build mapping of vertex index to cells that use it."""
    vertex_to_cells = {i: [] for i in range(len(self.vertices))}
    for icell, cell_verts in enumerate(self.iverts):
        for iv in cell_verts:
            vertex_to_cells[iv].append(icell)
    return vertex_to_cells
```

### 7.2: Round-Trip Testing

**Benefits:**
```python
# Create test data by exporting then re-importing
def test_round_trip():
    # Start with a Voronoi grid
    vg = VoronoiGrid(points)

    # Export to GSF
    vg.to_gridspec("test.gsf", vertex_z_method='top')

    # Re-import using from_gridspec
    imported = UnstructuredGrid.from_gridspec("test.gsf")

    # Verify geometry preserved
    assert np.allclose(vg.xcellcenters, imported.xcellcenters)
    assert np.allclose(vg.ycellcenters, imported.ycellcenters)
    assert len(vg.iverts) == len(imported.iverts)
```

### 7.3: Test Data Generation

**Use for testing `from_gridspec()`:**
```python
# Generate various test grids
def generate_test_gsf_files():
    # Test 1: Simple Voronoi
    vg = create_simple_voronoi(npoints=20)
    vg.to_gridspec("test_voronoi_simple.gsf")

    # Test 2: Complex Voronoi with varying sizes
    vg2 = create_complex_voronoi(npoints=100)
    vg2.to_gridspec("test_voronoi_complex.gsf")

    # Test 3: DISV-style layered grid
    disv = create_disv_grid()
    disv.to_gridspec("test_disv.gsf")
```

### 7.4: Documentation

**Example usage:**
```python
from flopy.utils.voronoi import VoronoiGrid
import numpy as np

# Create Voronoi grid
points = np.random.random((50, 2)) * 1000
vg = VoronoiGrid(points, ncpl=50, nlay=3)

# Export to GSF (automatic vertex z from top)
vg.to_gridspec("my_grid.gsf")

# Or with explicit vertex z
vertex_z = np.linspace(100, 0, len(vg.vertices))
vg.to_gridspec("my_grid.gsf", vertex_z=vertex_z)

# Or from bottom elevations
vg.to_gridspec("my_grid.gsf", vertex_z_method='bot')
```

### 7.5: Integration with Gridgen Testing

**Use both Gridgen and to_gridspec() for comprehensive testing:**
```python
# Gridgen-generated grids (known-good connectivity)
gridgen_files = [
    "test_uniform.gsf",
    "test_quadtree.gsf",
    "test_octree.gsf"
]

# FloPy-generated grids (known geometry)
flopy_files = [
    "test_voronoi.gsf",
    "test_disv.gsf"
]

# Test from_gridspec() on both sets
for gsf_file in gridgen_files + flopy_files:
    grid = UnstructuredGrid.from_gridspec(gsf_file)
    validate_grid(grid)
```

---

## Decisions Made

✅ **Connectivity approach:** Geometric (shared vertices/edges) for compatible grids
   - **Limitation:** Only works for grids where connected cells share vertices
   - **Rationale:** Supports common gridgen/quadtree/Voronoi workflows
   - **Future:** Allow explicit iac/ja input for grids with non-geometric connectivity
   - Hybrid approach: uniform layering fast path + GeoPandas spatial join

✅ **Cell top/bottom derivation:** User-selectable via parameters
   - **Limitation:** No deterministic way to infer from vertex z-coordinates
   - **Options:**
     1. `top_bot_method='minmax'` (default): top=max(vertex_z), bot=min(vertex_z)
     2. `top=array, bot=array`: Pass explicit arrays (recommended when known)
   - **Rationale:** Cell top/bot are model properties, not purely geometric

✅ **hwva calculation:** User-selectable via `hwva_method` parameter ('average' default, 'geometric' future)

✅ **hwva symmetry:** Compute once per connection pair, set both directions to same value
   - Guarantees perfect symmetry (no floating-point drift)
   - ~2x faster (eliminates redundant calculations)
   - No need for post-processing symmetry repair

✅ **Single-layer support:** Yes - simply skip vertical connectivity step when `len(ncpl) == 1`

✅ **Face geometry:** Assume planar faces (consistent with MODFLOW-USG/MODFLOW 6 design)
   - Use 2D Shapely operations for face areas
   - Simpler, well-tested approach

✅ **Default behavior:** `compute_connections=True` by default (opt-out available)
   - Most users want full DISU capability
   - Can disable for visualization-only use cases

✅ **Implementation strategy:** Minimal viable, then iterate

✅ **Repository:** FloPy (https://github.com/modflowpy/flopy)

✅ **Test data:**
   - Primary: Use Gridgen to create quadtree/octree test grids
   - Future: Add `to_gridspec()` export for Voronoi/DISV grids (Phase 7)
   - Enables round-trip testing and comprehensive test suite

✅ **GSF export (Phase 7):** Mirror approach to import
   - `vertex_z` parameter: explicit array or inferred from top/bot
   - `vertex_z_method='top'/'bot'`: Choose derivation method
   - Same flexibility philosophy as `from_gridspec()`

## Important Limitations

⚠️ **Geometric connectivity assumption:**
   - This implementation assumes connected cells share vertices or edges
   - **Works for:** gridgen quadtree, Voronoi, DISV-style layered grids
   - **May not work for:** arbitrary DISU grids with non-geometric connectivity
   - Users with non-geometric connectivity should use gridgen output files or provide iac/ja explicitly

⚠️ **Cell top/bottom inference:**
   - Vertex z-coordinates don't uniquely determine cell top/bottom
   - Default (min/max) is reasonable for many cases but not guaranteed correct
   - Users should verify top/bot values or provide them explicitly
   - MODFLOW 6 DISU uses 2D vertices (x,y only) + separate top/bot arrays

---

## References

- MODFLOW 6 DISU Package documentation (see `doc/mf6io/mf6ivar/dfn/gwf-disu.dfn` in modflow6 repo)
- FloPy gridgen module implementation (`flopy/utils/gridgen.py`)
- Existing `_set_neighbors()` method in Grid class (`flopy/discretization/grid.py:643-700`)
- MODFLOW-USG GSF file format specification
- Vertical connectivity detailed analysis (`vert_connections.txt`)
- GitHub Discussion: [Building and using fully unstructured (disu) grids #1232](https://github.com/MODFLOW-ORG/modflow6/discussions/1232)
