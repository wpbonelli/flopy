"""Debug vertical neighbor computation"""
import numpy as np
from flopy.discretization import UnstructuredGrid

gsf_path = "examples/data/freyberg_usg/freyberg.usg.gsf"

# Load grid
grid = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=False)

print(f"Grid info:")
print(f"  Nodes: {grid.nnodes}")
print(f"  NCPL: {grid.ncpl}")
print(f"  Layers: {len(grid.ncpl)}")

# Compute vertical neighbors
vertical_neighbors = UnstructuredGrid._find_vertical_neighbors(grid)

# Count vertical connections
total_vertical = sum(len(v) for v in vertical_neighbors.values())
print(f"\nVertical connections:")
print(f"  Total entries: {total_vertical}")
print(f"  Expected (uniform grid): {1499 * 2 * 2} (each cell connects up/down, 2 layers of connections)")

# Check some cells
for cell_id in [0, 1, 1499, 3000]:
    vn = vertical_neighbors.get(cell_id, [])
    layer = cell_id // 1499
    print(f"\nCell {cell_id} (layer {layer}):")
    print(f"  Vertical neighbors: {vn}")
    if vn:
        neighbor_layers = [n // 1499 for n in vn]
        print(f"  Neighbor layers: {neighbor_layers}")
