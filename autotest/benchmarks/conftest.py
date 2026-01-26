from pathlib import Path

import pytest


def get_examples_path():
    """Get path to examples/data directory."""
    return Path(__file__).parent.parent.parent / "examples" / "data"


@pytest.fixture(scope="session")
def benchmark_config():
    """Configure pytest-benchmark settings."""
    return {
        "warmup": True,
        "warmup_iterations": 5,
        "min_rounds": 5,
        "disable_gc": True,
    }


@pytest.fixture(scope="session")
def models_path(request) -> list[Path]:
    """
    A directories containing model subdirectories. Use
    the --models-path command line option once or more to specify
    model directories. If at least one --models_path is provided,
    external tests (i.e. those using models from an external repo)
    will run against model input files found in the given location
    on the local filesystem rather than model input files from the
    official model registry. This is useful for testing changes to
    test model input files during MF6 development.
    """
    paths = request.config.getoption("--models-path") or []
    return [Path(p).expanduser().resolve().absolute() for p in paths]


def pytest_addoption(parser):
    parser.addoption(
        "--models-path",
        action="append",
        type=str,
        help="directory containing model subdirectories. set this to run external "
        "tests (i.e. those using models from an external repo) against local model "
        "input files rather than input files from the official model registry.",
    )
    parser.addoption(
        "--namefile-pattern",
        action="store",
        type=str,
        default="mfsim.nam",
        help="namefile pattern to use when indexing models when --models-path is set."
        "does nothing otherwise. default is 'mfsim.nam'.",
    )
