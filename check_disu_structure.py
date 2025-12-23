"""Check what the DISU ja array actually contains"""
import numpy as np
import flopy

disu_path = "examples/data/freyberg_usg/freyberg.usg.disu"

# Load DISU
m = flopy.mfusg.MfUsg()
disu = flopy.mfusg.MfUsgDisU.load(disu_path, m)

iac = disu.iac.array
ja = disu.ja.array
ivc = disu.ivc.array if hasattr(disu, 'ivc') and disu.ivc is not None else None

print("DISU file structure:")
print(f"  Nodes: {len(iac)}")
print(f"  Total connections (nja): {len(ja)}")
print(f"  Has IVC: {ivc is not None}")

# Extract neighbors for cell 0
def get_cell_connections(cell_id):
    """Get connections for a cell"""
    pos = sum(iac[:cell_id])
    n_conn = iac[cell_id]
    connections = ja[pos:pos+n_conn]
    if ivc is not None:
        connection_types = ivc[pos:pos+n_conn]
    else:
        connection_types = None
    return connections, connection_types

# Check cell 0
connections, conn_types = get_cell_connections(0)
print(f"\nCell 0 connections:")
print(f"  All connections: {connections}")
print(f"  Connection types (IVC): {conn_types}")
if conn_types is not None:
    print(f"  Horizontal (IVC=0): {connections[conn_types == 0]}")
    print(f"  Vertical (IVC=1): {connections[conn_types == 1]}")

# Check cell 1499 (middle layer)
connections, conn_types = get_cell_connections(1499)
print(f"\nCell 1499 connections:")
print(f"  All connections: {connections}")
print(f"  Connection types (IVC): {conn_types}")
if conn_types is not None:
    print(f"  Horizontal (IVC=0): {connections[conn_types == 0]}")
    print(f"  Vertical (IVC=1): {connections[conn_types == 1]}")

# Overall IVC statistics
if ivc is not None:
    print(f"\nIVC statistics:")
    unique, counts = np.unique(ivc, return_counts=True)
    for val, count in zip(unique, counts):
        print(f"  IVC={val}: {count} connections")
