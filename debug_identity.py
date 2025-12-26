"""Debug which attribute shares identity between original and deepcopy"""

import copy
from pathlib import Path
import numpy as np

from flopy.modflow import Modflow


def debug_identity_sharing(m1, m2):
    """Find which attributes share identity."""
    print(f"NumPy version: {np.__version__}")
    print("\nChecking attribute identities...\n")

    from flopy.mf6.mfsimbase import MFSimulationData

    for k, v in m1.__dict__.items():
        if k not in m2.__dict__:
            continue

        v2 = m2.__dict__[k]

        # Check if they share identity
        if v2 is v and type(v) not in [bool, str, type(None), float, int]:
            # Check if it's an exception
            if isinstance(v, MFSimulationData):
                print(f"  {k:30s}: SHARES IDENTITY (MFSimulationData - OK)")
                continue
            elif isinstance(v, list):
                print(f"  {k:30s}: list - checking items...")
                for i, item in enumerate(v):
                    item2 = v2[i]
                    if item is item2 and type(item) not in [bool, str, type(None), float, int]:
                        print(f"    [{i}] SHARES IDENTITY: {type(item).__name__}")
                        print(f"        id(item): {id(item)}")
                        print(f"        id(item2): {id(item2)}")
                        if hasattr(item, '__dict__'):
                            print(f"        item attrs: {list(item.__dict__.keys())[:5]}")
                continue
            else:
                print(f"❌ {k:30s}: SHARES IDENTITY (type: {type(v).__name__})")
                print(f"   id(v):  {id(v)}")
                print(f"   id(v2): {id(v2)}")
                print(f"   This would cause line 52 to return False!")

                # Try to understand the object better
                if hasattr(v, '__dict__'):
                    print(f"   Object has {len(v.__dict__)} attributes")
                if hasattr(v, '__name__'):
                    print(f"   Object name: {v.__name__}")
                print()
        else:
            if type(v) not in [bool, str, type(None), float, int]:
                print(f"  {k:30s}: different identity ✓ (type: {type(v).__name__})")


def debug_packages(m1, m2):
    """Check packages for identity sharing."""
    print("\n" + "=" * 70)
    print("CHECKING PACKAGES")
    print("=" * 70)

    packages = m1.get_package_list()
    print(f"Found {len(packages)} packages: {packages}\n")

    from flopy.mf6.mfsimbase import MFSimulationData

    for pk_name in packages:
        pk1 = getattr(m1, pk_name)
        pk2 = getattr(m2, pk_name)

        print(f"\nPackage: {pk_name} (type: {type(pk1).__name__})")
        print("-" * 70)

        if not hasattr(pk1, '__dict__'):
            print(f"  No __dict__, skipping")
            continue

        found_shared = False
        for k, v in pk1.__dict__.items():
            if k not in pk2.__dict__:
                continue

            v2 = pk2.__dict__[k]

            # Check if they share identity
            if v2 is v and type(v) not in [bool, str, type(None), float, int, tuple]:
                # Skip known exceptions
                if k in {"_child_package_groups", "_data_list", "blocks", "dimensions",
                        "post_block_comments", "simulation_data", "structure", "_package_container"}:
                    continue

                if isinstance(v, MFSimulationData):
                    continue

                print(f"  ❌ {k:30s}: SHARES IDENTITY (type: {type(v).__name__})")
                print(f"     id(v):  {id(v)}")
                print(f"     id(v2): {id(v2)}")
                found_shared = True

                # Additional info
                if hasattr(v, '__dict__') and v.__dict__:
                    print(f"     Object has {len(v.__dict__)} attributes")
                if hasattr(v, '__name__'):
                    print(f"     Object name: {v.__name__}")

        if not found_shared:
            print(f"  ✓ All attributes have different identities")


if __name__ == "__main__":
    example_data_path = Path("examples/data")
    print(f"Loading Freyberg model...")

    m = Modflow.load(
        "freyberg.nam",
        model_ws=example_data_path / "freyberg_multilayer_transient",
    )

    print(f"Creating deep copy...\n")
    m_dc = copy.deepcopy(m)

    print("=" * 70)
    print("CHECKING MODEL ATTRIBUTES")
    print("=" * 70)
    debug_identity_sharing(m, m_dc)

    debug_packages(m, m_dc)
    print("\n" + "=" * 70)
