# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.14.5
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
#   metadata:
#     section: mf6
# ---

# # SFR2 package loading and querying

import os
from pathlib import Path

# +
import sys

import pooch
import flopy

proj_root = Path.cwd().parents[1]

print(sys.version)
print(f"flopy version: {flopy.__version__}")
# -

# Create a model instance

m = flopy.modflow.Modflow()

# Read the SFR2 file

loadpth = proj_root / "examples" / "data" / "mf2005_test"
fname = "testsfr2_tab_ICALC2.sfr"
fpth = pooch.retrieve(
    url=f"https://github.com/modflowpy/flopy/raw/develop/examples/data/mf2005_test/{fname}",
    fname=fname,
    path=loadpth,
    known_hash=None,
)
stuff = open(fpth).readlines()
stuff

# Load the SFR2 file

sfr = flopy.modflow.ModflowSfr2.load(fpth, m, nper=50)

sfr.segment_data.keys()

# Query the reach data in the SFR2 file

sfr.reach_data

# Query the channel flow data in the SFR2 file

sfr.channel_flow_data

# Query the channel geometry data in the SFR2 file

sfr.channel_geometry_data

# Query dataset 5 data in the SFR2 file

sfr.dataset_5

# Query the TABFILES dictionary in the SFR2 object to determine the TABFILES data in the SFR2 file

sfr.tabfiles_dict

# + pycharm={"name": "#%%\n"}
sfr.tabfiles
