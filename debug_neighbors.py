"""Debug script to understand the neighbor computation"""
import numpy as np
from flopy.discretization import UnstructuredGrid

gsf_path = "examples/data/freyberg_usg/freyberg.usg.gsf"

# Load grid
grid = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=False)

print(f"Grid info:")
print(f"  Nodes: {grid.nnodes}")
print(f"  NCPL: {grid.ncpl}")
print(f"  Layers: {len(grid.ncpl)}")
print(f"  iverts length: {len(grid.iverts)}")

# Compute horizontal neighbors
grid._set_neighbors(method="rook")
horizontal_neighbors = grid._neighbors

# Check a few cells in different layers
for cell_id in [0, 1499, 2998]:  # First cell in each layer
    neighbors = horizontal_neighbors.get(cell_id, [])
    print(f"\nCell {cell_id}:")
    print(f"  Horizontal neighbors: {len(neighbors)} -> {neighbors[:10]}")
    # Check if any neighbors are in different layers
    cell_layer = cell_id // 1499
    neighbor_layers = [n // 1499 for n in neighbors]
    cross_layer = [n for n, nl in zip(neighbors, neighbor_layers) if nl != cell_layer]
    if cross_layer:
        print(f"  WARNING: Cross-layer neighbors found: {cross_layer[:5]}")
