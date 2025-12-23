"""
Test script for Phase 1: GSF to DISU connectivity (iac/ja)
Compare computed values from GSF against existing DISU file
"""
import numpy as np
import flopy
from flopy.discretization import UnstructuredGrid

# Paths
gsf_path = "examples/data/freyberg_usg/freyberg.usg.gsf"
disu_path = "examples/data/freyberg_usg/freyberg.usg.disu"

print("=" * 80)
print("Phase 1: Testing iac/ja computation from GSF")
print("=" * 80)

# Load DISU file to get ground truth
print("\n1. Loading DISU file...")
m = flopy.mfusg.MfUsg()
disu = flopy.mfusg.MfUsgDisU.load(disu_path, m)
print(f"   DISU loaded: {disu.nodes} nodes, {len(disu.ja.array)} connections")

# Get ground truth arrays
iac_truth = disu.iac.array
ja_truth = disu.ja.array

# Load GSF and compute connectivity
print("\n2. Loading GSF and computing connectivity...")
grid = UnstructuredGrid.from_gridspec(gsf_path, compute_connections=True)
print(f"   Grid loaded: {grid.nnodes} nodes, {len(grid.ja)} connections")

# Get computed arrays
iac_computed = grid.iac
ja_computed = grid.ja

# Compare
print("\n3. Comparing results...")
print("-" * 80)

# IAC comparison
iac_match = np.array_equal(iac_computed, iac_truth)
print(f"IAC arrays match: {iac_match}")
if not iac_match:
    diff_count = np.sum(iac_computed != iac_truth)
    print(f"  Differences: {diff_count} / {len(iac_computed)} cells")
    max_diff = np.max(np.abs(iac_computed - iac_truth))
    print(f"  Max difference: {max_diff}")

    # Show first few differences
    diff_idx = np.where(iac_computed != iac_truth)[0]
    if len(diff_idx) > 0:
        print(f"  First few differences:")
        for i in diff_idx[:5]:
            print(f"    Cell {i}: computed={iac_computed[i]}, truth={iac_truth[i]}")
else:
    print("  ✓ All IAC values match exactly!")

# JA comparison
print()
ja_match = np.array_equal(ja_computed, ja_truth)
print(f"JA arrays match: {ja_match}")
if not ja_match:
    if len(ja_computed) != len(ja_truth):
        print(f"  Length mismatch: computed={len(ja_computed)}, truth={len(ja_truth)}")
    else:
        diff_count = np.sum(ja_computed != ja_truth)
        print(f"  Differences: {diff_count} / {len(ja_computed)} connections")

        # Show first few differences
        diff_idx = np.where(ja_computed != ja_truth)[0]
        if len(diff_idx) > 0:
            print(f"  First few differences:")
            for i in diff_idx[:10]:
                print(f"    Position {i}: computed={ja_computed[i]}, truth={ja_truth[i]}")
else:
    print("  ✓ All JA values match exactly!")

# Summary statistics
print()
print("-" * 80)
print("Summary:")
print(f"  Nodes: {grid.nnodes}")
print(f"  Layers: {len(grid.ncpl)}")
print(f"  NCPL: {grid.ncpl}")
print(f"  Total connections (nja): {len(ja_computed)}")
print(f"  IAC sum check: {iac_computed.sum()} == {len(ja_computed)} ? {iac_computed.sum() == len(ja_computed)}")

print("\n" + "=" * 80)
if iac_match and ja_match:
    print("SUCCESS: Phase 1 complete! iac and ja arrays match perfectly.")
else:
    print("PARTIAL: Phase 1 implemented but differences found. Investigation needed.")
print("=" * 80)
