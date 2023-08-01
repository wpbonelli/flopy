import pytest

from flopy.mf6 import MFSimulation


@pytest.mark.slow
def test_load_simulation(project_root_path, example_data_path, benchmark):
    # ws = project_root_path.parent / "prt-examples-temp" / "examples" / "ex-prt-tetratech" / "mf6"
    ws = example_data_path / "mf6" / "test006_gwf3"
    benchmark(lambda: MFSimulation.load(sim_ws=ws))


@pytest.mark.slow
def test_write_simulation(example_data_path, function_tmpdir, benchmark):
    ws = example_data_path / "mf6" / "test006_gwf3"
    sim = MFSimulation.load(sim_ws=ws)
    sim.set_sim_path(function_tmpdir)
    benchmark(sim.write_simulation)


@pytest.mark.slow
def test_read_big_file(function_tmpdir, benchmark):
    nlines = 16000000
    fpath = function_tmpdir / "bigfile.txt"
    with open(fpath, "w") as f:
        lines = ["llllllllllllllllllllllllllllllll" for _ in range(nlines)]
        f.writelines(lines)

    def read_all_lines():
        with open(fpath, "r") as f:
            chars = 0
            for line in f:
                chars += len(line)
            print(chars)

    benchmark(read_all_lines)


@pytest.mark.slow
def test_find_anchors(project_root_path, benchmark):
    fpath = project_root_path.parent / "prt-examples-temp" / "examples" / "ex-prt-tetratech" / "mf6" / "Carrier_FFinit_5TS_OC_top700.rch"

    def find_indices():
        with open(fpath, "r") as f:
            indices = {}
            for i, line in enumerate(f):
                line = line.lower()
                if "begin" in line or "end" in line:
                    indices[i + 1] = line
        return indices
    
    indices = benchmark(find_indices)
    # indices = find_indices()
    from pprint import pprint
    pprint(indices)
    print(len(indices), "anchors")


def test_plot():
    # processing files line by line scales (in runtime) by the number of chars per line

    import matplotlib.pyplot as plt

    x = [1, 16, 32]
    y = [45.7082, 669.4476, 1434.1]

    plt.plot(x, y, ".-")
    plt.show()
