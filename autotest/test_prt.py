import functools
import sys
from copy import deepcopy
from itertools import chain
from typing import List

import numpy as np
import flopy
import os
import matplotlib.pyplot as plt
import pytest
from flopy.discretization import StructuredGrid
from flopy.discretization.grid import Grid
from flopy.mf6 import MFSimulation
from flopy.modpath import NodeParticleData, CellDataType, ParticleGroup, ParticleData
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from modflow_devtools.executables import Executables


class Particle:
    """
    Class to hold particle information for a single particle.
    The current "array of objects" approach should be changed
    to "object of arrays" if many particles must be tracked.
    Parameters
    ----------
    pid : str, int
        particle id
    position : tuple
        (x, y, z) initial particle position
    """

    def __init__(self, pid, position, cell=None):
        self._pid = pid
        self._position = [position,]
        self.terminated = False
        self._cell = []
        if cell:
            self._cell.append(cell)
        self._pathline = [list(position) + [0.]]

    def update_position(self, new_position, time=None):
        self._position.append(new_position)
        self._pathline.append(list(new_position) + [time,])

    def update_cell(self, new_cell):
        self._cell.append(new_cell)

    @property
    def pid(self):
        return self._pid

    @pid.setter
    def pid(self, value):
        self._pid = value

    @property
    def position(self):
        return self._position[-1]

    @property
    def cell(self):
        return self._cell[-1]

    @property
    def pathline(self):
        return self._pathline


def track(
    time,
    modelgrid,
    qxf,
    qyf,
    particle,
    porosity
):
    qyf = np.copy(qyf)
    x, y, _ = particle.position
    k, i, j = particle.cell

    verts = np.array(modelgrid.get_cell_vertices(i, j))
    x1, x2 = min(verts[:, 0]), max(verts[:, 0])
    y1, y2 = min(verts[:, 1]), max(verts[:, 1])
    z1, z2 = modelgrid.top[i, j], modelgrid.botm[k, i, j]
    thickness = z1 - z2

    if particle.terminated:
        return particle

    qx1 = 0 if j == 0 else qxf[i, j]
    qx2 = 0 if j == modelgrid.ncol - 1 else qxf[i, j + 1]
    qy2 = 0 if i == 0 else qyf[i, j]
    qy1 = 0 if i == modelgrid.nrow - 1 else qyf[i + 1, j]

    # termination of particles: let's worry about this later and
    # get streaming dialed


    # equation 1a - 1d in MP7 documentation
    vx1 = qx1 / (porosity * modelgrid.delc[i] * thickness)
    vx2 = qx2 / (porosity * modelgrid.delc[i] * thickness)
    vy1 = qy1 / (porosity * modelgrid.delr[j] * thickness)
    vy2 = qy2 / (porosity * modelgrid.delr[j] * thickness)

    # stream steps, determine exit face
    if qx1 > 0 and qx2 > 0:
        xf = x2
        vxf = vx2
        xadj = 1
    else:
        xf = x1
        vxf = vx1
        xadj = -1

    if qy1 > 0 and qy2 > 0:
        yf = y2
        vyf = vy2
        yadj = -1
    else:
        yf = y1
        vyf = vy1
        yadj = 1

    #velocity gradient components in cell via eq. 3a and 3b
    Ax = (vx2 - vx1) / modelgrid.delr[j]
    Ay = (vy2 - vy1) / modelgrid.delc[i]

    # calculate instantaneous velocity at partilce point using eq. 2a and 2b
    vx = Ax * (x - x1) + vx1
    vy = Ay * (y - y1) + vy1

    # calculate travel times
    tx = calculate_travel_time(Ax, vx, vxf)
    ty = calculate_travel_time(Ay, vy, vyf)

    cell = list(particle.cell)
    if tx < ty:
        cell[2] += xadj
        etime = tx
    else:
        cell[1] += yadj
        etime = ty

    etime += time
    # answer should be 750 for xnew on the first solution.
    xnew = calculate_position(x1, Ax, vx, time, etime, vx1)
    ynew = calculate_position(y1, Ay, vy, time, etime, vy1)

    # particle termination due to other boundary conditions?
    if 0 <= cell[0] < modelgrid.nlay and 0 <= cell[1] < modelgrid.nrow and 0 <= cell[2] < modelgrid.ncol:
        # update position and cell
        particle.update_position((xnew, ynew, 25), etime)
        particle.update_cell(cell)
    else:
        particle.terminated = True
        return time, particle

    return etime, particle


def calculate_travel_time(A, vp, vf):
    """
    Method to calculate travel time
    for a particle to exit a cell in a coordinate
    direction
    Parameters
    ----------
    A : float
        linear interpolation factor for particle velocity
    vp : float
        velocity of particle
    vf : float
        velocity at exit face
    Returns
    -------
        float: exit time
    """
    return (1 / A) * np.log(vf / vp)


def calculate_position(f1, A, v, t0, t1, vf1):
    """
    Method to calculate the position of a particle
    at a given simulation time
    Parameters
    ----------
    f1 : float
        cell face 1 position
    A : float
        linear particle velocity interpolation factor
    v : float
        particle velocity
    t0 : float
        start time
    t1 : float
        exit time
    vf1 : float
        fluid velocity at cell face 1
    Returns
    -------
        pos : float
    """
    pos1 = f1 + (1 / A) * (v * np.exp(A * (t1 - t0)) - vf1)
    return pos1


def to_particle_data(particles: List[Particle], grid: StructuredGrid) -> ParticleData:
    """Convert a list of particles to a `flopy.modpath.ParticleData` object."""

    # compute cell IDs (node numbers) and vertex positions
    nns = [grid.intersect(p.position[0], p.position[1], p.position[2]) for p in particles]
    xyverts = [np.array(grid.get_cell_vertices(nn[1], nn[2])) for nn in nns]
    zverts = [(grid.botm[nn[0], nn[1], nn[2]], grid.top[nn[1], nn[2]] if nn[0] == 0 else grid.botm[nn[0] -1, nn[1], nn[2]]) for nn in nns]
    
    # functions to compute local coordinates
    def get_localx():
        ps = [p.position[0] for p in particles]  # particle x coord
        xmins = [min(v[:, 0]) for v in xyverts]  # cell min x coord
        xmaxs = [max(v[:, 0]) for v in xyverts]  # cell max x coord
        xdifs = [xmax - xmin for (xmin, xmax) in zip(xmins, xmaxs)]  # cell width in x dimension
        return [(x - xmin) / dx for (xmin, x, dx) in zip(xmins, ps, xdifs)]  # normalize to cell width

    def get_localy():
        ps = [p.position[1] for p in particles]
        ymins = [min(v[:, 1]) for v in xyverts]
        ymaxs = [max(v[:, 1]) for v in xyverts]
        ydifs = [ymax - ymin for (ymin, ymax) in zip(ymins, ymaxs)]
        return [(y - ymin) / dy for (ymin, y, dy) in zip(ymins, ps, ydifs)]

    def get_localz():
        ps = [p.position[2] for p in particles]
        zdifs = [zmax - zmin for (zmin, zmax) in zverts]
        return [(z - zvs[0]) / dz for (zvs, z, dz) in zip(zverts, ps, zdifs)]

    localx = get_localx()
    localy = get_localy()
    localz = get_localz()

    return flopy.modpath.ParticleData(
        structured=True,
        partlocs=[(nn[0], nn[1], nn[2]) for nn in nns],
        localx=localx,
        localy=localy,
        localz=localz,
        timeoffset=0,
        drape=0
    )

def test_to_particle_data(example_data_path):
    ws = example_data_path / "mf6-freyberg"
    sim = flopy.mf6.MFSimulation.load(sim_name="freyberg", sim_ws=ws, exe_name="mf6")
    grid = sim.get_model().modelgrid

    def get_particle():
        verts = np.array(grid.get_cell_vertices(0, 0))
        xverts = verts[:, 0]
        yverts = verts[:, 1]
        zverts = [grid.botm[0, 0, 0], grid.top[0, 0]]
        return Particle(
            pid=0,
            position=(
                (min(xverts) + max(xverts)) / 2,
                (min(yverts) + max(yverts)) / 2,
                (min(zverts) + max(zverts)) / 2)
        )

    p = get_particle()
    pd = to_particle_data([p], grid)

    expected = np.core.records.fromrecords(
        [[0, 0, 0, 0.5, 0.5, 0.5, 0., 0]],
        names=["k", "i", "j", "localx", "localy", "localz", "timeoffset", "drape"]
    )

    assert np.array_equal(pd.particledata, expected)
    assert pd.particlecount == 1

def compute_pathlines_ref(simulation: MFSimulation, particles: List[Particle], porosity: float, fflows):
    gwf = simulation.get_model()

    modelgrid = gwf.modelgrid

    qxf, qyf = fflows
    qxf = qxf[0]
    qyf = -1 * qyf[0]

    for ip, particle in enumerate(particles):
        i = 0
        time = 0
        max_iter = 100
        while i < max_iter:
            if i == 0:
                px, py = particle.position[0:2]
                cell = modelgrid.intersect(px, py, z=25)
                particle.update_cell(cell)

            exit_time, particle = track(
                time=time,
                modelgrid=modelgrid,
                qxf=qxf,
                qyf=qyf,
                particle=particle,
                porosity=porosity
            )

            xp, yp, _ = particle.position
            i += 1
            time = exit_time

            if particle.terminated:
                print(f"Particle {particle.pid} terminated")
                break

    pls = list(chain(*[[pp + [0, p.pid] for pp in p.pathline] for p in particles]))
    return np.core.records.fromrecords(pls, names='x,y,time,k,particleid')

def compute_pathlines_mp7(
        simulation: MFSimulation,
        particle_groups: List[ParticleGroup],
        porosity: float
):
    ws = simulation.simulation_data.mfpath.get_sim_path()
    gwf = simulation.get_model()

    mp = flopy.modpath.Modpath7(
        modelname=f"{simulation.name}_mp",
        flowmodel=gwf,
        exe_name="mp7",
        model_ws=ws
    )
    mpbas = flopy.modpath.Modpath7Bas(
        mp,
        porosity=porosity,
    )
    mpsim = flopy.modpath.Modpath7Sim(
        mp,
        simulationtype="combined",
        trackingdirection="forward",
        budgetoutputoption="summary",
        particlegroups=particle_groups,
    )

    mp.write_input()
    success, buff = mp.run_model(silent=True, report=True)
    assert success, "Failed to run particle-tracking model"
    for line in buff:
        print(line)

    p = flopy.utils.PathlineFile(ws / f"{simulation.name}_mp.mppth")
    return p.get_destination_pathline_data(range(gwf.modelgrid.nnodes), to_recarray=True)

def test_pathlines_2d_pollocks(function_tmpdir, example_data_path):
    ws = example_data_path / "mf6-freyberg"
    sim = flopy.mf6.MFSimulation.load(sim_name="freyberg", sim_ws=ws, exe_name="mf6")
    sim.set_sim_path(function_tmpdir)
    gwf = sim.get_model()
    gwf_name = gwf.name
    prt_name = f"{sim.name}_prt"
    gwf.name_file.save_flows = True
    grid = gwf.modelgrid

    # porosity
    porosity = 0.2

    # particle release locations
    positions = [
        (715.01, 8395.01, 25),
        (515.01, 4195.01, 10),
        (310, 2495.01, 10)
    ]
    particles = [Particle(pid=i, position=p, cell=grid.intersect(p[0], p[1])) for i, p in enumerate(positions)]

    # Instantiate the MODFLOW 6 prt model
    prt = flopy.mf6.ModflowPrt(
        sim, modelname=prt_name, model_nam_file="{}.nam".format(prt_name)
    )

    # Instantiate the MODFLOW 6 prt discretization package
    flopy.mf6.modflow.mfgwfdis.ModflowGwfdis(
        prt, pname="dis",
        nlay=grid.nlay, nrow=grid.nrow, ncol=grid.ncol,
        length_units="FEET",
        delr=grid.delr, delc=grid.delc,
        top=grid.top, botm=grid.botm,
        idomain=grid.idomain
    )

    # Instantiate the MODFLOW 6 prt model input package
    porosity = 0.1
    flopy.mf6.ModflowPrtmip(prt, pname="mip", porosity=porosity)

    # Instantiate the MODFLOW 6 prt particle release point (prp) package
    pd = {0: ["FIRST"],}
    flopy.mf6.ModflowPrtprp(
        prt, pname="prp", filename="{}.prp".format(prt_name),
        nreleasepts=len(particles), packagedata=[(p.pid, 0, p.cell[0], p.cell[1], p.position[0], p.position[1], p.position[2]) for p in particles],
        perioddata=pd,
    )

    # Instantiate the MODFLOW 6 prt output control package
    budgetfile_prt = "{}.cbb".format(prt_name)
    budget_record = [budgetfile_prt]
    flopy.mf6.ModflowPrtoc(
        prt,
        pname="oc",
        budget_filerecord=budget_record,
        saverecord=[("BUDGET", "ALL")],
    )

    headfile = "{}.hds".format(sim.name)
    budgetfile = "{}.cbb".format(sim.name)
    # Instantiate the MODFLOW 6 prt flow model interface
    pd = [
        ("GWFHEAD", headfile),
        ("GWFBUDGET", budgetfile)
    ]
    flopy.mf6.ModflowPrtfmi(prt, packagedata=pd)

    # Create the MODFLOW 6 gwf-prt model exchange
    flopy.mf6.ModflowGwfprt(
        sim, exgtype="GWF6-PRT6",
        exgmnamea=gwf_name, exgmnameb=prt_name,
        filename="{}.gwfprt".format(sim.name),
    )

    # Create an explicit model solution (EMS) for the MODFLOW 6 prt model
    # issue(flopy): using IMS until mfsimulation.py is updated for EMS by Scott
    # issue(mf6): code is kluged to create EMS if first model in IMS is a PRT
    ems = flopy.mf6.ModflowIms(
        sim, pname="ems",
        outer_maximum=100,
        filename="{}.ems".format(prt_name),
    )
    sim.register_ims_package(ems, [prt.name])

    # write input files and run GWF+PRT simulation
    sim.write_simulation()
    sim.run_simulation()

    # load heads
    hf = flopy.utils.HeadFile(ws / f"{sim.name}.hds")
    hd = hf.get_data()

    # load budgets
    cbc = gwf.output.budget()
    spdis = cbc.get_data(text="DATA-SPDIS")[0]
    flowja = cbc.get_data(text="FLOW-JA-FACE")[0]

    # compute face flows
    grb_name = ws / f"{gwf.name}.dis.grb"
    qxf, qyf, _ = flopy.mf6.utils.get_structured_faceflows(
        flowja,
        grb_file=grb_name
    )

    # compute specific discharge
    qx, qy, _ = flopy.utils.postprocessing.get_specific_discharge(spdis, gwf)

    # plot flow model grid, boundary conditions, head data and specific discharge
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(1, 1, 1, aspect="equal")
    mv = flopy.plot.PlotMapView(model=gwf)
    mv.plot_grid()
    mv.plot_ibound()
    mv.plot_array(hd, alpha=0.2)
    mv.plot_vector(qx, qy)
    mv.plot_bc("WEL")

    # plot particle initial positions
    for p in particles:
        px, py, _ = tuple(p.position)
        ax.scatter(px, py, color="orange", s=100)

    # get python reference solution
    pls_ref = compute_pathlines_ref(
        simulation=sim,
        particles=deepcopy(particles),
        porosity=porosity,
        fflows=(qxf, qyf),
    )[["x", "y", "particleid"]]

    # get modpath 7 solution
    pd = to_particle_data(particles, gwf.modelgrid)
    pg = ParticleGroup(
        particlegroupname="G1",
        particledata=pd,
        filename=f"{sim.name}.sloc"
    )
    pls_mp7 = compute_pathlines_mp7(
        simulation=sim,
        particle_groups=[pg],
        porosity=porosity
    )[["x", "y", "particleid"]]

        # plot pathlines
    for pid in [p.pid for p in particles]:
        pls_ref_sub = pls_ref[pls_ref["particleid"] == pid]
        pls_mp7_sub = pls_mp7[pls_mp7["particleid"] == pid]
        # pls_prt_sub = pls_prt[pls_prt["particleid"] == pid]
        ax.plot(pls_ref_sub["x"], pls_ref_sub["y"], color="green")
        ax.plot(pls_mp7_sub["x"], pls_mp7_sub["y"], color="blue", alpha=0.5)
        # ax.plot(pls_prt_sub["x"], pls_prt_sub["y"], color="purple")
    
    ax.legend(handles=[
        Patch(color="orange", label="start"),
        Patch(color="red", label="well"),
        Line2D([], [], color="green", label="ref"),
        Line2D([], [], color="blue", label="mp7"),
        Line2D([], [], color="purple", label="prt"),
    ])
    plt.show()

    # todo compare results
    # assert np.array_equal(pls_ref, pls_mp7)