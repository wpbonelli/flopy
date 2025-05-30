"""Test flopy.utils.binaryfile module.

See also test_cellbudgetfile.py for similar tests.
"""

from itertools import repeat

import numpy as np
import pandas as pd
import pytest
from matplotlib import pyplot as plt
from matplotlib.axes import Axes
from modflow_devtools.markers import requires_exe

import flopy
from flopy.utils import (
    BinaryHeader,
    CellBudgetFile,
    HeadFile,
    HeadUFile,
    UcnFile,
    Util2d,
)
from flopy.utils.binaryfile import get_headfile_precision


@pytest.fixture
def freyberg_model_path(example_data_path):
    return example_data_path / "freyberg"


@pytest.fixture
def nwt_model_path(example_data_path):
    return example_data_path / "nwt_test"


@pytest.fixture
def zonbud_model_path(example_data_path):
    return example_data_path / "zonbud_examples"


def test_binaryread(example_data_path):
    # test low-level binaryread() method
    pth = example_data_path / "freyberg" / "freyberg.githds"
    with open(pth, "rb") as fp:
        res = flopy.utils.binaryfile.binaryread(fp, np.int32, 2)
        np.testing.assert_array_equal(res, np.array([1, 1], np.int32))
        res = flopy.utils.binaryfile.binaryread(fp, np.float32, 2)
        np.testing.assert_array_equal(res, np.array([10, 10], np.float32))
        res = flopy.utils.binaryfile.binaryread(fp, bytes)
        assert res == b"            HEAD"
        res = flopy.utils.binaryfile.binaryread(fp, np.int32)
        assert res == 20


def test_binaryread_misc(tmp_path):
    # Check deprecated warning
    file = tmp_path / "data.file"
    file.write_bytes(b" data")
    with file.open("rb") as fp:
        with pytest.deprecated_call(match="vartype=str is deprecated"):
            res = flopy.utils.binaryfile.binaryread(fp, str, charlen=5)
        assert res == b" data"
    # Test exceptions with a small file with 1 byte
    file.write_bytes(b"\x00")
    with file.open("rb") as fp:
        with pytest.raises(EOFError):
            flopy.utils.binaryfile.binaryread(fp, bytes, charlen=6)
    with file.open("rb") as fp:
        with pytest.raises(EOFError):
            flopy.utils.binaryfile.binaryread(fp, np.int32)


def test_deprecated_binaryread_struct(example_data_path):
    # similar to test_binaryread(), but check the calls are deprecated
    pth = example_data_path / "freyberg" / "freyberg.githds"
    with open(pth, "rb") as fp:
        with pytest.deprecated_call():
            res = flopy.utils.binaryfile.binaryread_struct(fp, np.int32, 2)
        np.testing.assert_array_equal(res, np.array([1, 1], np.int32))
        with pytest.deprecated_call():
            res = flopy.utils.binaryfile.binaryread_struct(fp, np.float32, 2)
        np.testing.assert_array_equal(res, np.array([10, 10], np.float32))
        with pytest.deprecated_call():
            res = flopy.utils.binaryfile.binaryread_struct(fp, str)
        assert res == b"            HEAD"
        with pytest.deprecated_call():
            res = flopy.utils.binaryfile.binaryread_struct(fp, np.int32)
        assert res == 20


def test_headfile_build_index(example_data_path):
    # test low-level BinaryLayerFile._build_index() method
    pth = example_data_path / "freyberg_multilayer_transient" / "freyberg.hds"
    with HeadFile(pth) as hds:
        pass
    assert hds.nrow == 40
    assert hds.ncol == 20
    assert hds.nlay == 3
    assert not hasattr(hds, "nper")
    assert hds.totalbytes == 10_676_004
    assert len(hds.recordarray) == 3291
    assert type(hds.recordarray) == np.ndarray
    assert hds.recordarray.dtype == np.dtype(
        [
            ("kstp", "i4"),
            ("kper", "i4"),
            ("pertim", "f4"),
            ("totim", "f4"),
            ("text", "S16"),
            ("ncol", "i4"),
            ("nrow", "i4"),
            ("ilay", "i4"),
        ]
    )
    # check first and last recorddict
    list_recordarray = hds.recordarray.tolist()
    assert list_recordarray[0] == ((1, 1, 1.0, 1.0, b"            HEAD", 20, 40, 1))
    assert list_recordarray[-1] == (
        (1, 1097, 1.0, 1097.0, b"            HEAD", 20, 40, 3)
    )
    assert hds.times == list((np.arange(1097) + 1).astype(np.float32))
    assert hds.kstpkper == [(1, kper + 1) for kper in range(1097)]
    np.testing.assert_array_equal(hds.iposarray, np.arange(3291) * 3244 + 44)
    assert hds.iposarray.dtype == np.int64
    with pytest.deprecated_call(match="use headers instead"):
        assert hds.list_records() is None
    # check first and last row of data frame
    pd.testing.assert_frame_equal(
        hds.headers.iloc[[0, -1]],
        pd.DataFrame(
            {
                "kstp": np.array([1, 1], np.int32),
                "kper": np.array([1, 1097], np.int32),
                "pertim": np.array([1.0, 1.0], np.float32),
                "totim": np.array([1.0, 1097.0], np.float32),
                "text": ["HEAD", "HEAD"],
                "ncol": np.array([20, 20], np.int32),
                "nrow": np.array([40, 40], np.int32),
                "ilay": np.array([1, 3], np.int32),
            },
            index=[44, 10672804],
        ),
    )


def test_concentration_build_index(example_data_path):
    # test low-level BinaryLayerFile._build_index() method with UCN file
    pth = example_data_path / "mt3d_test/mf2005mt3d/P07/MT3D001.UCN"
    with UcnFile(pth) as ucn:
        pass
    assert ucn.nrow == 15
    assert ucn.ncol == 21
    assert ucn.nlay == 8
    assert not hasattr(ucn, "nper")
    assert ucn.totalbytes == 10_432
    assert len(ucn.recordarray) == 8
    assert type(ucn.recordarray) == np.ndarray
    assert ucn.recordarray.dtype == np.dtype(
        [
            ("ntrans", "i4"),
            ("kstp", "i4"),
            ("kper", "i4"),
            ("totim", "f4"),
            ("text", "S16"),
            ("ncol", "i4"),
            ("nrow", "i4"),
            ("ilay", "i4"),
        ]
    )
    # check first and last recorddict
    list_recordarray = ucn.recordarray.tolist()
    assert list_recordarray[0] == ((29, 1, 1, 100.0, b"CONCENTRATION   ", 21, 15, 1))
    assert list_recordarray[-1] == ((29, 1, 1, 100.0, b"CONCENTRATION   ", 21, 15, 8))
    assert ucn.times == [np.float32(100.0)]
    assert ucn.kstpkper == [(1, 1)]
    np.testing.assert_array_equal(ucn.iposarray, np.arange(8) * 1304 + 44)
    assert ucn.iposarray.dtype == np.int64
    with pytest.deprecated_call(match="use headers instead"):
        assert ucn.list_records() is None
    # check first and last row of data frame
    pd.testing.assert_frame_equal(
        ucn.headers.iloc[[0, -1]],
        pd.DataFrame(
            {
                "ntrans": np.array([29, 29], np.int32),
                "kstp": np.array([1, 1], np.int32),
                "kper": np.array([1, 1], np.int32),
                "totim": np.array([100.0, 100.0], np.float32),
                "text": ["CONCENTRATION", "CONCENTRATION"],
                "ncol": np.array([21, 21], np.int32),
                "nrow": np.array([15, 15], np.int32),
                "ilay": np.array([1, 8], np.int32),
            },
            index=[44, 9172],
        ),
    )


def test_binaryfile_writeread(function_tmpdir, nwt_model_path):
    model = "Pr3_MFNWT_lower.nam"
    ml = flopy.modflow.Modflow.load(model, version="mfnwt", model_ws=nwt_model_path)
    # change the model work space
    ml.change_model_ws(function_tmpdir)
    #
    ncol = ml.dis.ncol
    nrow = ml.dis.nrow
    text = "head"
    # write a double precision head file
    precision = "double"
    pertim = ml.dis.perlen.array[0].astype(np.float64)
    header = BinaryHeader.create(
        bintype=text,
        precision=precision,
        text=text,
        nrow=nrow,
        ncol=ncol,
        ilay=1,
        pertim=pertim,
        totim=pertim,
        kstp=1,
        kper=1,
    )
    b = ml.dis.botm.array[0, :, :].astype(np.float64)
    pth = function_tmpdir / "bottom.hds"
    Util2d.write_bin(b.shape, pth, b, header_data=header)

    bo = HeadFile(pth, precision=precision)
    times = bo.get_times()
    errmsg = "double precision binary totim read is not equal to totim written"
    assert times[0] == pertim, errmsg
    kstpkper = bo.get_kstpkper()
    errmsg = "kstp, kper read is not equal to kstp, kper written"
    assert kstpkper[0] == (0, 0), errmsg
    br = bo.get_data()
    errmsg = "double precision binary data read is not equal to data written"
    assert np.allclose(b, br), errmsg

    # write a single precision head file
    precision = "single"
    pertim = ml.dis.perlen.array[0].astype(np.float32)
    header = BinaryHeader.create(
        bintype=text,
        precision=precision,
        text=text,
        nrow=nrow,
        ncol=ncol,
        ilay=1,
        pertim=pertim,
        totim=pertim,
        kstp=1,
        kper=1,
    )
    b = ml.dis.botm.array[0, :, :].astype(np.float32)
    pth = function_tmpdir / "bottom_single.hds"
    Util2d.write_bin(b.shape, pth, b, header_data=header)

    bo = HeadFile(pth, precision=precision)
    times = bo.get_times()
    errmsg = "single precision binary totim read is not equal to totim written"
    assert times[0] == pertim, errmsg
    kstpkper = bo.get_kstpkper()
    errmsg = "kstp, kper read is not equal to kstp, kper written"
    assert kstpkper[0] == (0, 0), errmsg
    br = bo.get_data()
    errmsg = "singleprecision binary data read is not equal to data written"
    assert np.allclose(b, br), errmsg


def test_load_binary_head_file(example_data_path):
    mpath = example_data_path / "freyberg"
    hf = HeadFile(mpath / "freyberg.githds")
    assert isinstance(hf, HeadFile)


def test_plot_binary_head_file(example_data_path):
    hf = HeadFile(example_data_path / "freyberg" / "freyberg.githds")
    hf.mg.set_coord_info(xoff=1000.0, yoff=200.0, angrot=15.0)

    assert isinstance(hf.plot(), Axes)
    plt.close()


def test_headu_file_data(function_tmpdir, example_data_path):
    fname = example_data_path / "unstructured" / "headu.githds"
    headobj = HeadUFile(fname)
    assert isinstance(headobj, HeadUFile)
    assert headobj.nlay == 3

    # ensure recordarray is has correct data
    ra = headobj.recordarray
    nnodes = 19479
    assert ra["kstp"].min() == 1
    assert ra["kstp"].max() == 1
    assert ra["kper"].min() == 1
    assert ra["kper"].max() == 5
    assert ra["ncol"].min() == 1
    assert ra["ncol"].max() == 14001
    assert ra["nrow"].min() == 7801
    assert ra["nrow"].max() == nnodes

    # read the heads for the last time and make sure they are correct
    data = headobj.get_data()
    assert len(data) == 3
    minmaxtrue = [
        np.array([-1.4783, -1.0]),
        np.array([-2.0, -1.0]),
        np.array([-2.0, -1.01616]),
    ]
    for i, d in enumerate(data):
        t1 = np.array([d.min(), d.max()])
        assert np.allclose(t1, minmaxtrue[i])


@pytest.mark.slow
def test_headufile_get_ts(example_data_path):
    heads = HeadUFile(example_data_path / "unstructured" / "headu.githds")

    # check number of records (headers)
    assert len(heads) == 15
    with pytest.deprecated_call():
        assert heads.get_nrecords() == 15
    assert not hasattr(heads, "nrecords")

    # make sure timeseries can be retrieved for each node
    nnodes = 19479
    for i in range(0, nnodes, 100):
        heads.get_ts(idx=i)
    with pytest.raises(IndexError):
        heads.get_ts(idx=i + 100)

    # ...and retrieved in groups
    for i in range(10):
        heads.get_ts([i, i + 1, i + 2])

    heads = HeadUFile(
        example_data_path
        / "mfusg_test"
        / "01A_nestedgrid_nognc"
        / "output"
        / "flow.hds"
    )
    assert len(heads) == 1
    nnodes = 121
    for i in range(nnodes):
        heads.get_ts(idx=i)
    with pytest.raises(IndexError):
        heads.get_ts(idx=i + 1)

    # ...and retrieved in groups
    for i in range(10):
        heads.get_ts([i, i + 1, i + 2])


def test_get_headfile_precision(example_data_path):
    precision = get_headfile_precision(
        example_data_path / "freyberg" / "freyberg.githds"
    )
    assert precision == "single"

    precision = get_headfile_precision(
        example_data_path
        / "mf6"
        / "test005_advgw_tidal"
        / "expected_output"
        / "AdvGW_tidal.hds"
    )
    assert precision == "double"


def test_binaryfile_read(function_tmpdir, freyberg_model_path):
    h = HeadFile(freyberg_model_path / "freyberg.githds")
    assert isinstance(h, HeadFile)

    # check number of records (headers)
    assert len(h) == 1
    with pytest.deprecated_call():
        assert h.get_nrecords() == 1
    assert not hasattr(h, "nrecords")

    times = h.get_times()
    assert np.isclose(times[0], 10.0), f"times[0] != {times[0]}"

    kstpkper = h.get_kstpkper()
    assert kstpkper[0] == (0, 0), "kstpkper[0] != (0, 0)"

    h0 = h.get_data(totim=times[0])
    h1 = h.get_data(kstpkper=kstpkper[0])
    h2 = h.get_data(idx=0)
    assert np.array_equal(h0, h1), (
        "binary head read using totim != head read using kstpkper"
    )
    assert np.array_equal(h0, h2), "binary head read using totim != head read using idx"

    ts = h.get_ts((0, 7, 5))
    expected = 26.00697135925293
    assert np.isclose(ts[0, 1], expected), (
        f"time series value ({ts[0, 1]}) != {expected}"
    )
    h.close()

    # Check error when reading empty file
    fname = function_tmpdir / "empty.githds"
    with open(fname, "w"):
        pass
    with pytest.raises(ValueError):
        HeadFile(fname)
    with pytest.raises(ValueError):
        HeadFile(fname, "head", "single")


def test_binaryfile_read_context(freyberg_model_path):
    hds_path = freyberg_model_path / "freyberg.githds"
    with HeadFile(hds_path) as h:
        data = h.get_data()
        assert data.max() > 0, data.max()
        assert not h.file.closed
    assert h.file.closed

    with pytest.raises(ValueError) as e:
        h.get_data()
    assert str(e.value) == "seek of closed file", str(e.value)


@pytest.fixture
@pytest.mark.mf6
@requires_exe("mf6")
def mf6_gwf_2sp_st_tr(function_tmpdir):
    """
    A basic flow model with 2 stress periods,
    first steady-state, the second transient.
    """

    name = "mf6_gwf_2sp"
    sim = flopy.mf6.MFSimulation(
        sim_name=name,
        version="mf6",
        exe_name="mf6",
        sim_ws=function_tmpdir,
    )

    tdis = flopy.mf6.ModflowTdis(
        simulation=sim,
        nper=2,
        perioddata=[(0, 1, 1), (10, 10, 1)],
    )

    ims = flopy.mf6.ModflowIms(
        simulation=sim,
        complexity="SIMPLE",
    )

    gwf = flopy.mf6.ModflowGwf(
        simulation=sim,
        modelname=name,
        save_flows=True,
    )

    dis = flopy.mf6.ModflowGwfdis(
        model=gwf, nlay=1, nrow=1, ncol=10, delr=1, delc=10, top=10, botm=0
    )

    npf = flopy.mf6.ModflowGwfnpf(
        model=gwf,
        icelltype=[0],
        k=10,
    )

    ic = flopy.mf6.ModflowGwfic(
        model=gwf,
        strt=0,
    )

    wel = flopy.mf6.ModflowGwfwel(
        model=gwf,
        stress_period_data={0: None, 1: [[(0, 0, 0), -1]]},
    )

    sto = flopy.mf6.ModflowGwfsto(
        model=gwf,
        ss=1e-4,
        steady_state={0: True},
        transient={1: True},
    )

    chd = flopy.mf6.ModflowGwfchd(
        model=gwf,
        stress_period_data={0: [[(0, 0, 9), 0]]},
    )

    oc = flopy.mf6.ModflowGwfoc(
        model=gwf,
        budget_filerecord=f"{name}.cbc",
        head_filerecord=f"{name}.hds",
        saverecord=[("HEAD", "ALL"), ("BUDGET", "ALL")],
    )

    return sim


def test_read_mf6_2sp(mf6_gwf_2sp_st_tr):
    sim = mf6_gwf_2sp_st_tr
    gwf = sim.get_model()
    sim.write_simulation(silent=False)
    success, _ = sim.run_simulation(silent=False)
    assert success

    # load heads and flows
    hds = gwf.output.head()
    cbb = gwf.output.budget()

    # check times
    exp_times = [float(t) for t in range(11)]
    assert hds.get_times() == exp_times
    assert cbb.get_times() == exp_times

    # check stress periods and time steps
    exp_kstpkper = [(0, 0)] + [(i, 1) for i in range(10)]
    assert hds.get_kstpkper() == exp_kstpkper
    assert cbb.get_kstpkper() == exp_kstpkper

    # check head data access by time
    exp_hds_data = np.array([[list(repeat(0.0, 10))]])
    hds_data = hds.get_data(totim=0)
    assert np.array_equal(hds_data, exp_hds_data)

    # check budget file data by time
    cbb_data = cbb.get_data(totim=0)
    assert len(cbb_data) > 0

    # check head data access by kstp and kper
    hds_data = hds.get_data(kstpkper=(0, 0))
    assert np.array_equal(hds_data, exp_hds_data)

    # check budget file data by kstp and kper
    cbb_data_kstpkper = cbb.get_data(kstpkper=(0, 0))
    assert len(cbb_data) == len(cbb_data_kstpkper)
    for i in range(len(cbb_data)):
        assert np.array_equal(cbb_data[i], cbb_data_kstpkper[i])


@pytest.mark.parametrize("compact", [True, False])
def test_read_mf2005_freyberg(example_data_path, function_tmpdir, compact):
    m = flopy.modflow.Modflow.load(example_data_path / "freyberg" / "freyberg.nam")
    m.change_model_ws(function_tmpdir)
    oc = m.get_package("OC")
    oc.compact = compact

    m.write_input()
    success, buff = m.run_model(silent=False)
    assert success

    # load heads and flows
    hds_file = function_tmpdir / "freyberg.hds"
    cbb_file = function_tmpdir / "freyberg.cbc"
    assert hds_file.is_file()
    assert cbb_file.is_file()
    hds = HeadFile(hds_file)
    cbb = CellBudgetFile(cbb_file, model=m)  # failing to specify a model...

    # check times
    exp_times = [10.0]
    assert hds.get_times() == exp_times
    assert cbb.get_times() == exp_times  # ...causes get_times() to be empty

    # check stress periods and time steps
    exp_kstpkper = [(0, 0)]
    assert hds.get_kstpkper() == exp_kstpkper
    assert cbb.get_kstpkper() == exp_kstpkper

    # check head data access by time
    hds_data_totim = hds.get_data(totim=exp_times[0])
    assert hds_data_totim.shape == (1, 40, 20)

    # check budget file data by time
    cbb_data = cbb.get_data(totim=exp_times[0])
    assert len(cbb_data) > 0

    # check head data access by kstp and kper
    hds_data_kstpkper = hds.get_data(kstpkper=(0, 0))
    assert np.array_equal(hds_data_kstpkper, hds_data_totim)

    # check budget file data by kstp and kper
    cbb_data_kstpkper = cbb.get_data(kstpkper=(0, 0))
    assert len(cbb_data) == len(cbb_data_kstpkper)
    for i in range(len(cbb_data)):
        assert np.array_equal(cbb_data[i], cbb_data_kstpkper[i])
