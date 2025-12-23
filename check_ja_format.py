"""Check the exact format of the JA array"""
import numpy as np

# Read the DISU file manually to see the exact JA values
with open("examples/data/freyberg_usg/freyberg.usg.disu") as f:
    lines = f.readlines()

# Find IAC and JA lines
for i, line in enumerate(lines):
    if "#iac" in line.lower():
        iac_line_idx = i + 1
    if "#ja" in line.lower() and "ja" not in line.lower().replace("#ja", ""):
        ja_line_idx = i + 1
        break

# Parse IAC (first 10 values)
iac_values = list(map(int, lines[iac_line_idx].split()[:10]))
print("First 10 IAC values:")
print(iac_values)

# Parse JA (first 50 values)
ja_values = list(map(int, lines[ja_line_idx].split()[:50]))
print("\nFirst 50 JA values:")
print(ja_values)

# Decode the connections
print("\nDecoded connections (1-indexed JA):")
pos = 0
for cell_id in range(5):
    n_conn = iac_values[cell_id]
    connections = ja_values[pos:pos+n_conn]
    print(f"Cell {cell_id}: iac={n_conn}, ja={connections}")
    pos += n_conn

# Convert to 0-indexed
print("\nDecoded connections (0-indexed):")
pos = 0
for cell_id in range(5):
    n_conn = iac_values[cell_id]
    connections = [j - 1 for j in ja_values[pos:pos+n_conn]]
    print(f"Cell {cell_id}: connects to {connections}")
    # Check if cell connects to itself
    if cell_id in connections:
        print(f"  ✓ Includes self-connection")
    else:
        print(f"  ✗ NO self-connection")
    pos += n_conn
