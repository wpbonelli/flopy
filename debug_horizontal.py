"""Debug horizontal neighbor computation"""
import numpy as np
from flopy.discretization import UnstructuredGrid
import flopy

gsf_path = "examples/data/freyberg_usg/freyberg.usg.gsf"
disu_path = "examples/data/freyberg_usg/freyberg.usg.disu"

# Load DISU for comparison
m = flopy.mfusg.MfUsg()
disu = flopy.mfusg.MfUsgDisU.load(disu_path, m)
iac_truth = disu.iac.array
ja_truth = disu.ja.array

# Load grid and compute connections
grid = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=True)

# Compute what connections SHOULD be based on iac/ja from DISU
def get_neighbors_from_ja(iac, ja, one_indexed=True):
    """Extract neighbors from iac/ja arrays"""
    neighbors = {}
    pos = 0
    for cell_id in range(len(iac)):
        n_connections = iac[cell_id]
        # Get neighbors (no self-connection in MODFLOW-USG format)
        cell_neighbors = ja[pos:pos+n_connections].tolist()
        # Convert from 1-indexed to 0-indexed if needed
        if one_indexed:
            cell_neighbors = [n - 1 for n in cell_neighbors]
        neighbors[cell_id] = cell_neighbors
        pos += n_connections
    return neighbors

truth_neighbors = get_neighbors_from_ja(iac_truth, ja_truth, one_indexed=True)
computed_neighbors = get_neighbors_from_ja(grid.iac, grid.ja, one_indexed=True)

# Compare a few cells
print("Comparison of neighbors:")
print("=" * 80)
for cell_id in [0, 1, 2, 1499, 1500, 2998]:
    truth = set(truth_neighbors[cell_id])
    computed = set(computed_neighbors[cell_id])
    missing = truth - computed
    extra = computed - truth

    print(f"\nCell {cell_id} (layer {cell_id // 1499}):")
    print(f"  Truth: {len(truth)} neighbors")
    print(f"  Computed: {len(computed)} neighbors")
    if missing:
        print(f"  MISSING: {sorted(missing)}")
    if extra:
        print(f"  EXTRA: {sorted(extra)}")
    if not missing and not extra:
        print(f"  ✓ Perfect match!")

# Overall statistics
all_missing = 0
all_extra = 0
for cell_id in range(grid.nnodes):
    truth = set(truth_neighbors[cell_id])
    computed = set(computed_neighbors[cell_id])
    all_missing += len(truth - computed)
    all_extra += len(computed - truth)

print("\n" + "=" * 80)
print(f"Overall:")
print(f"  Missing connections: {all_missing}")
print(f"  Extra connections: {all_extra}")
print(f"  Total truth connections: {len(ja_truth) - len(iac_truth)}")  # Excluding self-connections
print(f"  Total computed connections: {len(grid.ja) - len(grid.iac)}")
