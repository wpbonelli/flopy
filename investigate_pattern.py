"""Investigate the missing neighbor pattern (cell + 32)"""
import numpy as np
from flopy.discretization import UnstructuredGrid
import flopy

gsf_path = "examples/data/freyberg_usg/freyberg.usg.gsf"

# Load grid
grid = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=False)

# Check a few cells and their +32 neighbors
for cell_id in [0, 1, 2, 100]:
    neighbor_id = cell_id + 32

    print(f"\nCell {cell_id} and its +32 neighbor {neighbor_id}:")

    # Get cell vertices
    verts_0 = grid.iverts[cell_id]
    verts_32 = grid.iverts[neighbor_id]

    print(f"  Cell {cell_id} vertices: {verts_0}")
    print(f"  Cell {neighbor_id} vertices: {verts_32}")

    # Check if they share vertices
    shared = set(verts_0) & set(verts_32)
    print(f"  Shared vertices: {shared} ({len(shared)} vertices)")

    # Check if they share an edge (2 consecutive vertices)
    shares_edge = False
    for i in range(len(verts_0)):
        v1 = verts_0[i]
        v2 = verts_0[(i + 1) % len(verts_0)]
        edge = {v1, v2}

        for j in range(len(verts_32)):
            vm1 = verts_32[j]
            vm2 = verts_32[(j + 1) % len(verts_32)]
            edge_m = {vm1, vm2}

            if edge == edge_m:
                shares_edge = True
                print(f"  Shares edge: {edge}")
                break
        if shares_edge:
            break

    if shared and not shares_edge:
        print(f"  → Shares vertices but NOT edges (diagonal/queen neighbor)")
    elif shares_edge:
        print(f"  → Shares edge (rook neighbor) ← Should be found!")

# Also check the grid dimensions
print(f"\nGrid dimensions:")
print(f"  Nodes per layer: {grid.ncpl[0]}")
print(f"  Layers: {len(grid.ncpl)}")

# Try to understand the grid layout
# If cells are arranged in rows, what's the row width?
print(f"\nTrying to determine grid structure:")
print(f"  If cell +1 is to the right, and cell +32 is...")

# Check relative positions
cell0_x, cell0_y = grid._xc[0], grid._yc[0]
cell1_x, cell1_y = grid._xc[1], grid._yc[1]
cell32_x, cell32_y = grid._xc[32], grid._yc[32]

print(f"\n  Cell 0: ({cell0_x:.1f}, {cell0_y:.1f})")
print(f"  Cell 1: ({cell1_x:.1f}, {cell1_y:.1f}) - dx={cell1_x-cell0_x:.1f}, dy={cell1_y-cell0_y:.1f}")
print(f"  Cell 32: ({cell32_x:.1f}, {cell32_y:.1f}) - dx={cell32_x-cell0_x:.1f}, dy={cell32_y-cell0_y:.1f}")
