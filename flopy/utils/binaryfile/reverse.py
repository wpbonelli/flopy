import argparse
from pathlib import Path

from flopy.utils.binaryfile import CellBudgetFile, HeadFile

if __name__ == "__main__":
    """Reverse a TDIS input file or a head or budget output file."""

    parser = argparse.ArgumentParser(description="Reverse head, budget, or TDIS files.")
    parser.add_argument(
        "--head",
        "-h",
        type=str,
        help="Head file",
    )
    parser.add_argument(
        "--budget",
        "-b",
        type=str,
        help="Budget file",
    )
    parser.add_argument(
        "--tdis",
        "-t",
        type=str,
        help="TDIS file",
    )
    parser.add_argument(
        "--head-output",
        type=str,
        help="Reversed head file",
    )
    parser.add_argument(
        "--budget-output",
        type=str,
        help="Reversed budget file",
    )
    parser.add_argument(
        "--tdis-output",
        type=str,
        help="Reversed TDIS file",
    )

    args = parser.parse_args()
    head_input = Path(args.head)
    budget_input = Path(args.budget)
    tdis_input = Path(args.tdis)
    head_output = Path(args.head_output)
    budget_output = Path(args.budget_output)
    tdis_output = Path(args.tdis_output)
    HeadFile(head_input).reverse(head_output)
    CellBudgetFile(budget_input).reverse(budget_output)
    # TODO load TDIS alone (how?) and reverse it
