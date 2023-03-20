# DO NOT MODIFY THIS FILE DIRECTLY.  THIS FILE MUST BE CREATED BY
# mf6/utils/createpackages.py
# FILE created on March 20, 2023 22:37:08 UTC
from .. import mfpackage
from ..data.mfdatautil import ListTemplateGenerator


class ModflowUtltvs(mfpackage.MFPackage):
    """
    ModflowUtltvs defines a tvs package within a utl model.

    Parameters
    ----------
    model : MFModel
        Model that this package is a part of. Package is automatically
        added to model when it is initialized.
    loading_package : bool
        Do not set this parameter. It is intended for debugging and internal
        processing purposes only.
    disable_storage_change_integration : boolean
        * disable_storage_change_integration (boolean) keyword that deactivates
          inclusion of storage derivative terms in the STO package matrix
          formulation. In the absence of this keyword (the default), the
          groundwater storage formulation will be modified to correctly adjust
          heads based on transient variations in stored water volumes arising
          from changes to SS and SY properties.
    ts_filerecord : [ts6_filename]
        * ts6_filename (string) defines a time-series file defining time series
          that can be used to assign time-varying values. See the "Time-
          Variable Input" section for instructions on using the time-series
          capability.
    perioddata : [cellid, tvssetting]
        * cellid ((integer, ...)) is the cell identifier, and depends on the
          type of grid that is used for the simulation. For a structured grid
          that uses the DIS input file, CELLID is the layer, row, and column.
          For a grid that uses the DISV input file, CELLID is the layer and
          CELL2D number. If the model uses the unstructured discretization
          (DISU) input file, CELLID is the node number for the cell. This
          argument is an index variable, which means that it should be treated
          as zero-based when working with FloPy and Python. Flopy will
          automatically subtract one when loading index variables and add one
          when writing index variables.
        * tvssetting (keystring) line of information that is parsed into a
          property name keyword and values. Property name keywords that can be
          used to start the TVSSETTING string include: SS and SY.
            ss : [double]
                * ss (double) is the new value to be assigned as the cell's
                  specific storage (or storage coefficient if the
                  STORAGECOEFFICIENT STO package option is specified) from the
                  start of the specified stress period, as per SS in the STO
                  package. Specific storage values must be greater than or
                  equal to 0. If the OPTIONS block includes a TS6 entry (see
                  the "Time-Variable Input" section), values can be obtained
                  from a time series by entering the time-series name in place
                  of a numeric value.
            sy : [double]
                * sy (double) is the new value to be assigned as the cell's
                  specific yield from the start of the specified stress period,
                  as per SY in the STO package. Specific yield values must be
                  greater than or equal to 0. If the OPTIONS block includes a
                  TS6 entry (see the "Time-Variable Input" section), values can
                  be obtained from a time series by entering the time-series
                  name in place of a numeric value.
    filename : String
        File name for this package.
    pname : String
        Package name for this package.
    parent_file : MFPackage
        Parent package file that references this package. Only needed for
        utility packages (mfutl*). For example, mfutllaktab package must have 
        a mfgwflak package parent_file.

    """
    ts_filerecord = ListTemplateGenerator(('tvs', 'options',
                                           'ts_filerecord'))
    perioddata = ListTemplateGenerator(('tvs', 'period', 'perioddata'))
    package_abbr = "utltvs"
    _package_type = "tvs"
    dfn_file_name = "utl-tvs.dfn"

    dfn = [
           ["header", ],
           ["block options", "name disable_storage_change_integration",
            "type keyword", "reader urword", "optional true"],
           ["block options", "name ts_filerecord",
            "type record ts6 filein ts6_filename", "shape", "reader urword",
            "tagged true", "optional true"],
           ["block options", "name ts6", "type keyword", "shape",
            "in_record true", "reader urword", "tagged true",
            "optional false"],
           ["block options", "name filein", "type keyword", "shape",
            "in_record true", "reader urword", "tagged true",
            "optional false"],
           ["block options", "name ts6_filename", "type string",
            "preserve_case true", "in_record true", "reader urword",
            "optional false", "tagged false"],
           ["block period", "name iper", "type integer",
            "block_variable True", "in_record true", "tagged false", "shape",
            "valid", "reader urword", "optional false"],
           ["block period", "name perioddata",
            "type recarray cellid tvssetting", "shape", "reader urword"],
           ["block period", "name cellid", "type integer",
            "shape (ncelldim)", "tagged false", "in_record true",
            "reader urword"],
           ["block period", "name tvssetting", "type keystring ss sy",
            "shape", "tagged false", "in_record true", "reader urword"],
           ["block period", "name ss", "type double precision", "shape",
            "tagged true", "in_record true", "reader urword",
            "time_series true"],
           ["block period", "name sy", "type double precision", "shape",
            "tagged true", "in_record true", "reader urword",
            "time_series true"]]

    def __init__(self, model, loading_package=False,
                 disable_storage_change_integration=None, ts_filerecord=None,
                 perioddata=None, filename=None, pname=None, **kwargs):
        super().__init__(model, "tvs", filename, pname,
                         loading_package, **kwargs)

        # set up variables
        self.disable_storage_change_integration = self.build_mfdata(
            "disable_storage_change_integration",
            disable_storage_change_integration)
        self.ts_filerecord = self.build_mfdata("ts_filerecord", ts_filerecord)
        self.perioddata = self.build_mfdata("perioddata", perioddata)
        self._init_complete = True
