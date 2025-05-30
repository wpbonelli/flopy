# ---
# jupyter:
#   jupytext:
#     notebook_metadata_filter: all
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
#   metadata:
#     section: mf2005
#     authors:
#       - name: Andrew Leaf
# ---

# ## Postprocessing head results from MODFLOW

# +
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import git
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pooch

import flopy
import flopy.utils.binaryfile as bf
from flopy.utils.postprocessing import (
    get_gradients,
    get_transmissivities,
    get_water_table,
)

print(sys.version)
print(f"numpy version: {np.__version__}")
print(f"matplotlib version: {mpl.__version__}")
print(f"flopy version: {flopy.__version__}")

# +
mfnam = "EXAMPLE.nam"
heads_file = "EXAMPLE.HED"

# temporary directory
temp_dir = TemporaryDirectory()
workspace = temp_dir.name


# Check if we are in the repository and define the data path.

try:
    root = Path(git.Repo(".", search_parent_directories=True).working_dir)
except:
    root = None

data_path = root / "examples" / "data" if root else Path.cwd()
file_names = {
    "EXAMPLE-1.endpoint": None,
    "EXAMPLE-1.mpsim": None,
    "EXAMPLE-2.endpoint": None,
    "EXAMPLE-2.mplist": None,
    "EXAMPLE-2.mpsim": None,
    "EXAMPLE-3.endpoint": None,
    "EXAMPLE-3.mplist": None,
    "EXAMPLE-3.mpsim": None,
    "EXAMPLE-3.pathline": None,
    "EXAMPLE-4.endpoint": None,
    "EXAMPLE-4.mplist": None,
    "EXAMPLE-4.mpsim": None,
    "EXAMPLE-4.timeseries": None,
    "EXAMPLE-5.endpoint": None,
    "EXAMPLE-5.mplist": None,
    "EXAMPLE-5.mpsim": None,
    "EXAMPLE-6.endpoint": None,
    "EXAMPLE-6.mplist": None,
    "EXAMPLE-6.mpsim": None,
    "EXAMPLE-6.timeseries": None,
    "EXAMPLE-7.endpoint": None,
    "EXAMPLE-7.mplist": None,
    "EXAMPLE-7.mpsim": None,
    "EXAMPLE-7.timeseries": None,
    "EXAMPLE-8.endpoint": None,
    "EXAMPLE-8.mplist": None,
    "EXAMPLE-8.mpsim": None,
    "EXAMPLE-8.timeseries": None,
    "EXAMPLE-9.endpoint": None,
    "EXAMPLE-9.mplist": None,
    "EXAMPLE-9.mpsim": None,
    "EXAMPLE.BA6": None,
    "EXAMPLE.BUD": None,
    "EXAMPLE.DIS": None,
    "EXAMPLE.DIS.metadata": None,
    "EXAMPLE.HED": None,
    "EXAMPLE.LPF": None,
    "EXAMPLE.LST": None,
    "EXAMPLE.MPBAS": None,
    "EXAMPLE.OC": None,
    "EXAMPLE.PCG": None,
    "EXAMPLE.RCH": None,
    "EXAMPLE.RIV": None,
    "EXAMPLE.WEL": None,
    "EXAMPLE.mpnam": None,
    "EXAMPLE.nam": None,
    "example-1.mplist": None,
    "example-6.locations": None,
    "example-7.locations": None,
    "example-8.locations": None,
    "example.basemap": None,
}
for fname, fhash in file_names.items():
    pooch.retrieve(
        url=f"https://github.com/modflowpy/flopy/raw/develop/examples/data/mp6/{fname}",
        fname=fname,
        path=data_path / "mp6",
        known_hash=fhash,
    )

# -

# ### Load example model and head results

m = flopy.modflow.Modflow.load(mfnam, model_ws=data_path / "mp6")

hdsobj = bf.HeadFile(data_path / "mp6" / heads_file)
hds = hdsobj.get_data(kstpkper=(0, 2))
hds.shape

# ### Plot heads in each layer; export the heads and head contours for viewing in a GIS
# for more information about GIS export, type `help(export_array)`, for example

# +
fig, axes = plt.subplots(2, 3, figsize=(11, 8.5))
axes = axes.flat
grid = m.modelgrid
for i, hdslayer in enumerate(hds):
    im = axes[i].imshow(hdslayer, vmin=hds.min(), vmax=hds.max())
    axes[i].set_title(f"Layer {i + 1}")
    ctr = axes[i].contour(hdslayer, colors="k", linewidths=0.5)

    # export head rasters
    # (GeoTiff export requires the rasterio package; for ascii grids, just change the extension to *.asc)
    flopy.export.utils.export_array(
        grid, os.path.join(workspace, f"heads{i + 1}.tif"), hdslayer
    )

    # export head contours to a shapefile
    flopy.export.utils.export_array_contours(
        grid, os.path.join(workspace, f"heads{i + 1}.shp"), hdslayer
    )

fig.delaxes(axes[-1])
fig.subplots_adjust(right=0.8)
cbar_ax = fig.add_axes([0.85, 0.15, 0.03, 0.7])
fig.colorbar(im, cax=cbar_ax, label="Head")
# -

# ### Compare rotated arc-ascii and GeoTiff output

# +
grid.set_coord_info(angrot=30.0)
nodata = 0.0
flopy.export.utils.export_array(
    grid, os.path.join(workspace, "heads5_rot.asc"), hdslayer, nodata=nodata
)
flopy.export.utils.export_array(
    grid, os.path.join(workspace, "heads5_rot.tif"), hdslayer, nodata=nodata
)

results = np.loadtxt(os.path.join(workspace, "heads5_rot.asc"), skiprows=6)
results[results == nodata] = np.nan
plt.imshow(results)
plt.colorbar()
# -

try:
    import rasterio
except:
    rasterio = None
    print("install rasterio to create GeoTiff output")
if rasterio is not None:
    with rasterio.open(os.path.join(workspace, "heads5_rot.tif")) as src:
        print(src.meta)
        plt.imshow(src.read(1))

# ### Get the vertical head gradients between layers

# +
grad = get_gradients(hds, m, nodata=-999)

fig, axes = plt.subplots(2, 3, figsize=(11, 8.5))
axes = axes.flat

for i, vertical_gradient in enumerate(grad):
    im = axes[i].imshow(vertical_gradient, vmin=grad.min(), vmax=grad.max())
    axes[i].set_title(f"Vertical gradient\nbetween Layers {i + 1} and {i + 2}")
    ctr = axes[i].contour(
        vertical_gradient,
        levels=[-0.1, -0.05, 0.0, 0.05, 0.1],
        colors="k",
        linewidths=0.5,
    )
    plt.clabel(ctr, fontsize=8, inline=1)

fig.delaxes(axes[-2])
fig.delaxes(axes[-1])
fig.subplots_adjust(right=0.8)
cbar_ax = fig.add_axes([0.85, 0.15, 0.03, 0.7])
fig.colorbar(im, cax=cbar_ax, label="positive downward")
# -

# ### Get the saturated thickness of a layer
# `m.modelgrid.saturated_thickness()` returns an nlay, nrow, ncol array of saturated thicknesses.

# +
st = m.modelgrid.saturated_thickness(hds, mask=-9999.0)

plt.imshow(st[0])
plt.colorbar(label="Saturated thickness")
plt.title("Layer 1")
# -

# ### Get the water table
# `get_water_table()` returns an nrow, ncol array of the water table elevation.
# This method can be useful when HDRY is turned on and the water table is in multiple layers.

# +
wt = get_water_table(heads=hds, hdry=-9999)

plt.imshow(wt)
plt.colorbar(label="Elevation")
# -

# ### Get layer transmissivities at arbitrary locations, accounting for the position of the water table
# * for this method, the heads input is an nlay x nobs array of head results, which could be constructed using the Hydmod package with an observation in each layer at each observation location, for example .
# * x, y values in real-world coordinates can be used in lieu of row, column, provided a correct coordinate information is supplied to the flopy model object's grid.
# * open interval tops and bottoms can be supplied at each location for computing transmissivity-weighted average heads
# * this method can also be used for apportioning boundary fluxes for an inset from a 2-D regional model
# * see `**flopy3_get_transmissivities_example.ipynb**` for more details on how this method works

r = [20, 5]
c = [5, 20]
headresults = hds[:, r, c]
get_transmissivities(headresults, m, r=r, c=c)

r = [20, 5]
c = [5, 20]
sctop = [340, 320]  # top of open interval at each location
scbot = [210, 150]  # top of bottom interval at each location
headresults = hds[:, r, c]
tr = get_transmissivities(headresults, m, r=r, c=c, sctop=sctop, scbot=scbot)
tr

# #### convert to transmissivity fractions

trfrac = tr / tr.sum(axis=0)
trfrac

# #### Layer 3 contributes almost no transmissivity because of its K-value

m.lpf.hk.array[:, r, c]

m.modelgrid.cell_thickness[:, r, c]

try:
    # ignore PermissionError on Windows
    temp_dir.cleanup()
except:
    pass
