"""
Tests aiming to reproduce MODPATH (soon, PRT) 2D tracking results
in Python for MODFLOW 2005 and MODFLOW 6 Freyberg example problem

This is mostly a learning aid to make sure I understood Pollock's
method, could maybe convert to a notebook if explicating particle
tracking approaches is appropriate for user-facing documentation?
"""

from math import exp, log, nan
from types import SimpleNamespace
from warnings import warn

import matplotlib.pyplot as plt
import numpy as np
import pytest

import flopy.utils.binaryfile as bf
from flopy.mf6 import MFSimulation
from flopy.mf6.utils import get_structured_faceflows
from flopy.modflow import Modflow
from flopy.plot import PlotMapView
from flopy.utils.postprocessing import get_specific_discharge


@pytest.fixture
def mf2005_model(example_data_path, function_tmpdir):
    # create modflow model
    mdl = Modflow.load(
        "freyberg.nam",
        model_ws=str(example_data_path / "freyberg"),
        version="mf2005",
        exe_name="mf2005",
    )

    # write and run model
    mdl.change_model_ws(str(function_tmpdir))
    mdl.write_input()
    success, buff = mdl.run_model()
    assert success

    return mdl, function_tmpdir


@pytest.fixture
def mf6_model(example_data_path, function_tmpdir):
    # create simulation
    sim = MFSimulation.load(
        "mfsim.nam",
        version="mf6",
        exe_name="mf6",
        sim_ws=str(example_data_path / "mf6-freyberg"),
    )

    # write and run simulation
    sim.set_sim_path(str(function_tmpdir))
    sim.get_model().name_file.save_flows = True
    sim.write_simulation()
    success, buff = sim.run_simulation()
    assert success

    return sim, function_tmpdir


class Particle(SimpleNamespace):
    def __init__(self, position, **kwargs):
        self.position = np.array(position)
        self.terminated = False
        super().__init__(**kwargs)

    def __setitem__(self, key, item):
        self.position[key] = item

    def __getitem__(self, key):
        return self.position[key]

    def __repr__(self):
        return str(np.round(self.position, 2))


def test_particle():
    p = Particle(name="a", position=(0.0, 0.0, 0.0))
    p[0] = 1.0
    p[1] = 2.0
    p[2] = 3.0

    assert np.array_equal(p.position, np.array([1.0, 2.0, 3.0]))
    assert not p.terminated

    p = Particle(name="a", position=(0.0, 0.0, 0.0), cell=(0, 0, 0))
    assert p.cell == (0, 0, 0)


def switch(a, b):
    temp = a
    a = b
    b = temp
    return a, b 


def track(time, grid, fflows, spdis, particle, porosity):
    # face flows and specific discharge
    qx, qy = fflows
    sqx, sqy = spdis

    # particle's current location and cell
    x, y = particle.position
    cell = particle.cell
    l, r, c = cell

    # extract vertices and x/y/z coordinates in
    # increasing order, by distance from origin
    # (modflow considers origin to be top left)
    verts = np.array(grid.get_cell_vertices(r, c))
    x1, x2 = min(verts[:, 0]), max(verts[:, 0])
    y1, y2 = max(verts[:, 1]), min(verts[:, 1])
    z1, z2 = grid.top[r, c], grid.botm[l, r, c]

    # abort if terminated
    if particle.terminated:
        warn(f"particle {particle.name} already terminated!")
        return particle

    # face flows (1 is inner, 2 is outer)
    qx1 = 0 if c == 0 else qx[r, c]
    qy1 = 0 if r == 0 else qy[r, c]
    qx2 = 0 if c == grid.ncol - 1 else qx[r, c + 1]
    qy2 = 0 if r == grid.nrow - 1 else qy[r + 1, c]

    # if all face flows are inwards, particle terminates
    if np.sign(qx1) > 0 > np.sign(qx2) and np.sign(qy1) > 0 > np.sign(qy2):
        print(
            f"particle {particle.name} stops lrc={cell} p={particle} t={round(exit_time, 2)} (sink)"
        )
        particle.terminated = True
        return time, particle
    
    # TODO: handle saddle case (outward face flows)
    
    # reorder coords & face flows s.t. particle moves away
    # from (q)(x/y)1 and towards (q)(x/y)2
    if np.sign(qx1) < 0:
        qx1, qx2 = switch(qx1, qx2)
        x1, x2 = switch(x1, x2)
    if np.sign(qy1) < 0:
        qy1, qy2 = switch(qy1, qy2)
        y1, y2 = switch(y1, y2)
    
    # distance from particle to faces in 
    dx = x - x1
    dy = y - y1

    # face areas
    xarea = grid.delr[c] * abs(z1 - z2)
    yarea = grid.delc[r] * abs(z1 - z2)

    # face-center velocity components w/ same ordering as
    # above, so particle moves away from 1 and towards 2
    # (eqns 1a-1d)
    fvx1 = qx1 / (porosity * xarea)
    fvx2 = qx2 / (porosity * xarea)
    fvy1 = qy1 / (porosity * yarea)
    fvy2 = qy2 / (porosity * yarea)

    # cell velocity gradient components
    # (eqns 3a-3b)
    Ax = (fvx2 - fvx1) / grid.delr[c]
    Ay = (fvy2 - fvy1) / grid.delc[r]

    # interpolate particle's initial velocity components
    # (eqns 2a-2b)
    vx = fvx1 + (Ax * dx)
    vy = fvy1 + (Ay * dy)

    # find exit times in each dimension
    # (rearranged eqns 8a-8b, t on LHS)
    def get_exit_times():
        def get_exit_time(A, d, v, v1, t):
            return (np.log((A * d + v) / v1) / A) + t

        tx = get_exit_time(Ax, x2 - x, vx, fvx1, time)
        ty = get_exit_time(Ay, -(y2 - y), vy, fvy1, time)
        return time + tx, time + ty

    exit_times = get_exit_times()

    # determine exit dimension and exit face
    # 1 is outer (away from origin), 0 inner
    if exit_times[0] < exit_times[1]:
        exit_time = exit_times[0]
        exit_face = 1 if np.sign(vx) > 0 else 0
        exit_dim = "x"
    else:
        exit_time = exit_times[1]
        exit_face = 1 if np.sign(vy) > 0 else 0
        exit_dim = "y"

    # inf exit time means particle terminated in sink
    if exit_time == np.inf:
        print(
            f"particle {particle.name} stops lrc={cell} p={particle} t={round(exit_time, 2)} (sink)"
        )
        particle.terminated = True
        return time, particle

    # determine which cell particle is about to enter
    if exit_dim == "x":
        en_r = r
        en_c = (c + 1) if exit_face == 1 else (c - 1)
    else:
        en_r = (r + 1) if exit_face == 1 else (r - 1)
        en_c = c
    next_cell = (l, en_r, en_c)
    particle.cell = next_cell

    # determine exit location
    # (eqns 8a-8b)
    def get_exit_location(t):
        def get_exit_loc(A, p, v, v1, t1):
            return p + ((1 / A) * ((v * np.exp(A * (t1 - time))) - v1))
        
        if exit_dim == "x":
            lx = x2
            ly = get_exit_loc(Ay, y, vy, fvy1, t)
        else:
            lx = get_exit_loc(Ax, x, vx, fvx1, t)
            ly = y2
        
        return lx, ly

    exit_pos = np.array(get_exit_location(exit_time))
    particle.position = exit_pos

    # terminate if particle is about to exit the grid
    if any(np.isnan(list(next_cell))) or not (
        grid.extent[0] <= exit_pos[0] <= grid.extent[1]
        and grid.extent[2] <= exit_pos[1] <= grid.extent[3]
    ):
        print(
            f"particle {particle.name} stops lrc={cell} p={particle} t={round(exit_time, 2)} (edge)"
        )
        particle.terminated = True
        return time, particle

    print(
        f"particle {particle.name} moves lrc={next_cell} p={particle} t={round(exit_time, 2)}"
    )
    return exit_time, particle


def test_track_mf6_structured(mf6_model):
    sim, function_tmpdir = mf6_model
    gwf = sim.get_model()
    grid = gwf.modelgrid

    # face flows and specific discharge
    cbc = bf.CellBudgetFile(str(function_tmpdir / "freyberg.cbc"))
    spdis = cbc.get_data(text="DATA-SPDIS")[0]
    flowja = cbc.get_data(text="FLOW-JA-FACE")[0]
    qx, qy, _ = get_structured_faceflows(
        flowja,
        grb_file=str(function_tmpdir / "freyberg.dis.grb"),
    )
    sqx, sqy, _ = get_specific_discharge(spdis, gwf)

    # remove vertical dimension
    qx = qx[0]
    qy = qy[0]
    sqx = sqx[0]
    sqy = sqy[0]

    # particles
    particles = [
        # Particle(name="A", position=(865.01, 1950.01)),
        Particle(name="B", position=(715.01, 8395.01)),
        # Particle(name="C", position=(750.01, 8450.01)),
        # Particle(name="D", position=(615.01, 5130.01)),
    ]

    # porosity (uniform)
    n = 0.2

    # termination conditions
    max_iter = 25

    # pathlines
    pathlines = {
        ip: np.array([p[0], p[1], 0]) for ip, p in enumerate(particles)
    }

    # get head data
    hds = bf.HeadFile(str(function_tmpdir / "freyberg.hds"))
    head = hds.get_data()

    with plt.ion():
        # plot grid
        fig = plt.figure(figsize=(8, 8))
        ax = fig.add_subplot(1, 1, 1, aspect="equal")
        mv = PlotMapView(model=gwf)
        mv.plot_grid()
        mv.plot_ibound()
        mv.plot_array(head, alpha=0.5)
        mv.plot_vector(sqx, sqy)
        mv.plot_bc("WEL")
        ax.scatter(particles[0][0], particles[0][1])
        plt.show()
        plt.waitforbuttonpress()

        print(f"tracking {len(particles)} particle(s)")
        for ip, p in enumerate(particles):
            i = 0
            t = 0
            particle = p

            while i < max_iter:
                if i == 0:
                    cell = grid.intersect(p[0], p[1])
                    p.cell = (0, cell[0], cell[1])
                    # p.cell = (
                    #     0,
                    #     grid.nrow - cell[0] - 1,
                    #     cell[1],
                    # )
                    print(
                        f"particle {p.name} drops lrc={p.cell} p={p.position} t={t}"
                    )

                exit_time, particle = track(
                    time=t,
                    grid=grid,
                    fflows=(qx, qy),
                    spdis=(sqx, sqy),
                    # fflows=(qx, np.flipud(qy)),  # correct inverted y axis
                    # spdis=(sqx, np.flipud(sqy)),
                    particle=particle,
                    porosity=n,
                )

                ax.scatter(particles[0][0], particles[0][1])
                plt.show()
                plt.waitforbuttonpress()

                i += 1
                t = exit_time
                pos = particle.position
                pathlines[ip] = np.vstack(
                    (pathlines[ip], np.array([pos[0], pos[1], exit_time]))
                )

                if particle.terminated:
                    break

        # plot pathlines       
        for ipl, pathline in pathlines.items():
            ax.scatter(pathline[:, 0], pathline[:, 1], c=pathline[:, 2])
            # for ip, p in enumerate(pathline):
            #     ax.text(p[0], p[1], round(p[2], 2))
        plt.show()
        plt.waitforbuttonpress()
