"""Debug script to identify which attribute fails the copy test with numpy 2.4.0"""

import copy
from pathlib import Path
import numpy as np

from flopy.modflow import Modflow


def debug_model_is_copy(m1, m2):
    """Enhanced version that prints what fails."""
    print(f"NumPy version: {np.__version__}")
    print(f"\nChecking if models are different objects...")

    if m1 is m2:
        print("❌ FAIL: Models are the same object!")
        return False
    print("✓ Models are different objects")

    print("\nChecking model attributes...")
    for k, v in m1.__dict__.items():
        if k not in m2.__dict__:
            print(f"❌ FAIL: Attribute '{k}' not in m2")
            return False

        v2 = m2.__dict__[k]

        # Check identity (should be different for non-primitives)
        if v2 is v and type(v) not in [bool, str, type(None), float, int]:
            # Skip known exceptions
            if k in {"_packagelist", "_package_paths", "_ftype_num_dict"}:
                continue

            # Check for special cases
            from flopy.mf6.mfsimbase import MFSimulationData
            if isinstance(v, MFSimulationData):
                continue
            elif isinstance(v, list):
                # Check list items
                list_copy_ok = True
                for i, item in enumerate(v):
                    item2 = v2[i]
                    if item is item2 and type(item) not in [bool, str, type(None), float, int]:
                        print(f"❌ FAIL: Attribute '{k}[{i}]' shares identity (type: {type(item).__name__})")
                        list_copy_ok = False
                        break
                if not list_copy_ok:
                    return False
            else:
                print(f"❌ FAIL: Attribute '{k}' shares identity (type: {type(v).__name__})")
                print(f"  v is v2: {v is v2}")
                print(f"  id(v): {id(v)}, id(v2): {id(v2)}")
                return False

        # Check equality for certain types
        if isinstance(v, np.ndarray):
            try:
                if not np.allclose(v, v2, equal_nan=True):
                    print(f"❌ FAIL: Attribute '{k}' arrays not equal")
                    return False
            except Exception as e:
                print(f"❌ FAIL: Attribute '{k}' comparison error: {e}")
                return False
        elif isinstance(v, (str, int, float, bool)):
            if v != v2:
                print(f"❌ FAIL: Attribute '{k}' values not equal: {v} != {v2}")
                return False

    print("✓ All attribute checks passed")
    return True


if __name__ == "__main__":
    # Load the Freyberg model
    example_data_path = Path("examples/data")
    print(f"Loading Freyberg model...")

    m = Modflow.load(
        "freyberg.nam",
        model_ws=example_data_path / "freyberg_multilayer_transient",
    )

    print(f"Creating deep copy...")
    m_dc = copy.deepcopy(m)

    print(f"\nRunning diagnostic checks...\n")
    print("=" * 60)
    result = debug_model_is_copy(m, m_dc)
    print("=" * 60)
    print(f"\nResult: {'✓ PASS' if result else '❌ FAIL'}")
