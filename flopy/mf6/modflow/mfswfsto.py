# DO NOT MODIFY THIS FILE DIRECTLY.  THIS FILE MUST BE CREATED BY
# mf6/utils/createpackages.py
# FILE created on February 18, 2024 14:36:23 UTC
from .. import mfpackage


class ModflowSwfsto(mfpackage.MFPackage):
    """
    ModflowSwfsto defines a sto package within a swf6 model.

    Parameters
    ----------
    model : MFModel
        Model that this package is a part of. Package is automatically
        added to model when it is initialized.
    loading_package : bool
        Do not set this parameter. It is intended for debugging and internal
        processing purposes only.
    save_flows : boolean
        * save_flows (boolean) keyword to indicate that cell-by-cell flow terms
          will be written to the file specified with "BUDGET SAVE FILE" in
          Output Control.
    steady_state : boolean
        * steady-state (boolean) keyword to indicate that stress period IPER is
          steady-state. Steady-state conditions will apply until the TRANSIENT
          keyword is specified in a subsequent BEGIN PERIOD block.
    transient : boolean
        * transient (boolean) keyword to indicate that stress period IPER is
          transient. Transient conditions will apply until the STEADY-STATE
          keyword is specified in a subsequent BEGIN PERIOD block.
    filename : String
        File name for this package.
    pname : String
        Package name for this package.
    parent_file : MFPackage
        Parent package file that references this package. Only needed for
        utility packages (mfutl*). For example, mfutllaktab package must have
        a mfgwflak package parent_file.

    """

    package_abbr = "swfsto"
    _package_type = "sto"
    dfn_file_name = "swf-sto.dfn"

    dfn = [
        [
            "header",
        ],
        [
            "block options",
            "name save_flows",
            "type keyword",
            "reader urword",
            "optional true",
        ],
        [
            "block period",
            "name iper",
            "type integer",
            "block_variable True",
            "in_record true",
            "tagged false",
            "shape",
            "valid",
            "reader urword",
            "optional false",
        ],
        [
            "block period",
            "name steady-state",
            "type keyword",
            "shape",
            "valid",
            "reader urword",
            "optional true",
        ],
        [
            "block period",
            "name transient",
            "type keyword",
            "shape",
            "valid",
            "reader urword",
            "optional true",
        ],
    ]

    def __init__(
        self,
        model,
        loading_package=False,
        save_flows=None,
        steady_state=None,
        transient=None,
        filename=None,
        pname=None,
        **kwargs,
    ):
        super().__init__(
            model, "sto", filename, pname, loading_package, **kwargs
        )

        # set up variables
        self.save_flows = self.build_mfdata("save_flows", save_flows)
        self.steady_state = self.build_mfdata("steady-state", steady_state)
        self.transient = self.build_mfdata("transient", transient)
        self._init_complete = True