import platform
from os import getcwd
from os.path import splitdrive
from pathlib import Path

from flopy.utils.flopy_io import line_parse, relpath_safe


def test_line_parse():
    """t027 test line_parse method in MNW2 Package class"""
    # ensure that line_parse is working correctly
    # comment handling
    line = line_parse("Well-A  -1                   ; 2a. WELLID,NNODES")
    assert line == ["Well-A", "-1"]


def test_relpath_safe(function_tmpdir):
    if (
        platform.system() == "Windows"
        and splitdrive(function_tmpdir)[0] != splitdrive(getcwd())[0]
    ):
        assert (
            Path(relpath_safe(function_tmpdir))
            == Path(getcwd()).absolute()
        )
    else:
        assert Path(
            relpath_safe(function_tmpdir, function_tmpdir.parent)
        ) == Path(function_tmpdir.name)
        assert (
            Path(relpath_safe(function_tmpdir, function_tmpdir.parent.parent))
            == Path(function_tmpdir.parent.name) / function_tmpdir.name
        )
