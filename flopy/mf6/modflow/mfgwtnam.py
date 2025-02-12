# DO NOT MODIFY THIS FILE DIRECTLY.  THIS FILE MUST BE CREATED BY
# mf6/utils/createpackages.py
# FILE created on February 11, 2025 01:24:12 UTC
from .. import mfpackage
from ..data.mfdatautil import ListTemplateGenerator


class ModflowGwtnam(mfpackage.MFPackage):
    """
    ModflowGwtnam defines a nam package within a gwt6 model.

    Parameters
    ----------
    model : MFModel
        Model that this package is a part of. Package is automatically
        added to model when it is initialized.
    loading_package : bool
        Do not set this parameter. It is intended for debugging and internal
        processing purposes only.
    list : string
        * list (string) is name of the listing file to create for this GWT
          model. If not specified, then the name of the list file will be the
          basename of the GWT model name file and the '.lst' extension. For
          example, if the GWT name file is called "my.model.nam" then the list
          file will be called "my.model.lst".
    print_input : boolean
        * print_input (boolean) keyword to indicate that the list of all model
          stress package information will be written to the listing file
          immediately after it is read.
    print_flows : boolean
        * print_flows (boolean) keyword to indicate that the list of all model
          package flow rates will be printed to the listing file for every
          stress period time step in which "BUDGET PRINT" is specified in
          Output Control. If there is no Output Control option and
          "PRINT_FLOWS" is specified, then flow rates are printed for the last
          time step of each stress period.
    save_flows : boolean
        * save_flows (boolean) keyword to indicate that all model package flow
          terms will be written to the file specified with "BUDGET FILEOUT" in
          Output Control.
    nc_mesh2d_filerecord : [ncmesh2dfile]
        * ncmesh2dfile (string) name of the netcdf ugrid layered mesh output
          file.
    nc_structured_filerecord : [ncstructfile]
        * ncstructfile (string) name of the netcdf structured output file.
    nc_filerecord : [netcdf_filename]
        * netcdf_filename (string) defines a netcdf input file.
    packages : [ftype, fname, pname]
        * ftype (string) is the file type, which must be one of the following
          character values shown in table ref{table:ftype-gwt}. Ftype may be
          entered in any combination of uppercase and lowercase.
        * fname (string) is the name of the file containing the package input.
          The path to the file should be included if the file is not located in
          the folder where the program was run.
        * pname (string) is the user-defined name for the package. PNAME is
          restricted to 16 characters. No spaces are allowed in PNAME. PNAME
          character values are read and stored by the program for stress
          packages only. These names may be useful for labeling purposes when
          multiple stress packages of the same type are located within a single
          GWT Model. If PNAME is specified for a stress package, then PNAME
          will be used in the flow budget table in the listing file; it will
          also be used for the text entry in the cell-by-cell budget file.
          PNAME is case insensitive and is stored in all upper case letters.
    filename : String
        File name for this package.
    pname : String
        Package name for this package.
    parent_file : MFPackage
        Parent package file that references this package. Only needed for
        utility packages (mfutl*). For example, mfutllaktab package must have
        a mfgwflak package parent_file.

    """

    nc_mesh2d_filerecord = ListTemplateGenerator(
        ("gwt6", "nam", "options", "nc_mesh2d_filerecord")
    )
    nc_structured_filerecord = ListTemplateGenerator(
        ("gwt6", "nam", "options", "nc_structured_filerecord")
    )
    nc_filerecord = ListTemplateGenerator(("gwt6", "nam", "options", "nc_filerecord"))
    packages = ListTemplateGenerator(("gwt6", "nam", "packages", "packages"))
    package_abbr = "gwtnam"
    _package_type = "nam"
    dfn_file_name = "gwt-nam.dfn"

    dfn = [
        [
            "header",
        ],
        [
            "block options",
            "name list",
            "type string",
            "reader urword",
            "optional true",
            "preserve_case true",
        ],
        [
            "block options",
            "name print_input",
            "type keyword",
            "reader urword",
            "optional true",
        ],
        [
            "block options",
            "name print_flows",
            "type keyword",
            "reader urword",
            "optional true",
        ],
        [
            "block options",
            "name save_flows",
            "type keyword",
            "reader urword",
            "optional true",
        ],
        [
            "block options",
            "name nc_mesh2d_filerecord",
            "type record netcdf_mesh2d fileout ncmesh2dfile",
            "shape",
            "reader urword",
            "tagged true",
            "optional true",
            "mf6internal ncmesh2drec",
        ],
        [
            "block options",
            "name netcdf_mesh2d",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
            "extended true",
        ],
        [
            "block options",
            "name nc_structured_filerecord",
            "type record netcdf_structured fileout ncstructfile",
            "shape",
            "reader urword",
            "tagged true",
            "optional true",
            "mf6internal ncstructrec",
        ],
        [
            "block options",
            "name netcdf_structured",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
            "mf6internal netcdf_struct",
            "extended true",
        ],
        [
            "block options",
            "name fileout",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block options",
            "name ncmesh2dfile",
            "type string",
            "preserve_case true",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
            "extended true",
        ],
        [
            "block options",
            "name ncstructfile",
            "type string",
            "preserve_case true",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
            "extended true",
        ],
        [
            "block options",
            "name nc_filerecord",
            "type record netcdf filein netcdf_filename",
            "reader urword",
            "tagged true",
            "optional true",
        ],
        [
            "block options",
            "name netcdf",
            "type keyword",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
            "extended true",
        ],
        [
            "block options",
            "name filein",
            "type keyword",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block options",
            "name netcdf_filename",
            "type string",
            "preserve_case true",
            "in_record true",
            "reader urword",
            "optional false",
            "tagged false",
            "mf6internal netcdf_fname",
            "extended true",
        ],
        [
            "block packages",
            "name packages",
            "type recarray ftype fname pname",
            "reader urword",
            "optional false",
        ],
        [
            "block packages",
            "name ftype",
            "in_record true",
            "type string",
            "tagged false",
            "reader urword",
        ],
        [
            "block packages",
            "name fname",
            "in_record true",
            "type string",
            "preserve_case true",
            "tagged false",
            "reader urword",
        ],
        [
            "block packages",
            "name pname",
            "in_record true",
            "type string",
            "tagged false",
            "reader urword",
            "optional true",
        ],
    ]

    def __init__(
        self,
        model,
        loading_package=False,
        list=None,
        print_input=None,
        print_flows=None,
        save_flows=None,
        nc_mesh2d_filerecord=None,
        nc_structured_filerecord=None,
        nc_filerecord=None,
        packages=None,
        filename=None,
        pname=None,
        **kwargs,
    ):
        super().__init__(model, "nam", filename, pname, loading_package, **kwargs)

        # set up variables
        self.list = self.build_mfdata("list", list)
        self.print_input = self.build_mfdata("print_input", print_input)
        self.print_flows = self.build_mfdata("print_flows", print_flows)
        self.save_flows = self.build_mfdata("save_flows", save_flows)
        self.nc_mesh2d_filerecord = self.build_mfdata(
            "nc_mesh2d_filerecord", nc_mesh2d_filerecord
        )
        self.nc_structured_filerecord = self.build_mfdata(
            "nc_structured_filerecord", nc_structured_filerecord
        )
        self.nc_filerecord = self.build_mfdata("nc_filerecord", nc_filerecord)
        self.packages = self.build_mfdata("packages", packages)
        self._init_complete = True
