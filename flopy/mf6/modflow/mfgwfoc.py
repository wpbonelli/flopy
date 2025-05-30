# autogenerated file, do not modify

from os import PathLike, curdir
from typing import Union

from flopy.mf6.data.mfdatautil import ArrayTemplateGenerator, ListTemplateGenerator
from flopy.mf6.mfpackage import MFChildPackages, MFPackage


class ModflowGwfoc(MFPackage):
    """
    ModflowGwfoc defines a OC package.

    Parameters
    ----------
    budget_filerecord : (budgetfile)
        * budgetfile : string
                name of the output file to write budget information.

    budgetcsv_filerecord : (budgetcsvfile)
        * budgetcsvfile : string
                name of the comma-separated value (CSV) output file to write budget summary
                information.  A budget summary record will be written to this file for each
                time step of the simulation.

    head_filerecord : (headfile)
        * headfile : string
                name of the output file to write head information.

    headprintrecord : (head, print_format)
        * head : keyword
                keyword to specify that record corresponds to head.
        * print_format : keyword
                keyword to specify format for printing to the listing file.

    saverecord : (save, rtype, ocsetting)
        * save : keyword
                keyword to indicate that information will be saved this stress period.
        * rtype : string
                type of information to save or print.  Can be BUDGET or HEAD.
        * ocsetting : keystring all first last frequency steps
                specifies the steps for which the data will be saved.

    printrecord : (print, rtype, ocsetting)
        * print : keyword
                keyword to indicate that information will be printed this stress period.
        * rtype : string
                type of information to save or print.  Can be BUDGET or HEAD.
        * ocsetting : keystring all first last frequency steps
                specifies the steps for which the data will be saved.


    """

    budget_filerecord = ListTemplateGenerator(
        ("gwf6", "oc", "options", "budget_filerecord")
    )
    budgetcsv_filerecord = ListTemplateGenerator(
        ("gwf6", "oc", "options", "budgetcsv_filerecord")
    )
    head_filerecord = ListTemplateGenerator(
        ("gwf6", "oc", "options", "head_filerecord")
    )
    headprintrecord = ListTemplateGenerator(
        ("gwf6", "oc", "options", "headprintrecord")
    )
    saverecord = ListTemplateGenerator(("gwf6", "oc", "period", "saverecord"))
    printrecord = ListTemplateGenerator(("gwf6", "oc", "period", "printrecord"))
    package_abbr = "gwfoc"
    _package_type = "oc"
    dfn_file_name = "gwf-oc.dfn"
    dfn = [
        ["header"],
        [
            "block options",
            "name budget_filerecord",
            "type record budget fileout budgetfile",
            "shape",
            "reader urword",
            "tagged true",
            "optional true",
        ],
        [
            "block options",
            "name budget",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
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
            "name budgetfile",
            "type string",
            "preserve_case true",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
        ],
        [
            "block options",
            "name budgetcsv_filerecord",
            "type record budgetcsv fileout budgetcsvfile",
            "shape",
            "reader urword",
            "tagged true",
            "optional true",
        ],
        [
            "block options",
            "name budgetcsv",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block options",
            "name budgetcsvfile",
            "type string",
            "preserve_case true",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
        ],
        [
            "block options",
            "name head_filerecord",
            "type record head fileout headfile",
            "shape",
            "reader urword",
            "tagged true",
            "optional true",
        ],
        [
            "block options",
            "name head",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block options",
            "name headfile",
            "type string",
            "preserve_case true",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
        ],
        [
            "block options",
            "name headprintrecord",
            "type record head print_format formatrecord",
            "shape",
            "reader urword",
            "optional true",
        ],
        [
            "block options",
            "name print_format",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block options",
            "name formatrecord",
            "type record columns width digits format",
            "shape",
            "in_record true",
            "reader urword",
            "tagged",
            "optional false",
        ],
        [
            "block options",
            "name columns",
            "type integer",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional",
        ],
        [
            "block options",
            "name width",
            "type integer",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional",
        ],
        [
            "block options",
            "name digits",
            "type integer",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional",
        ],
        [
            "block options",
            "name format",
            "type string",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
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
            "name saverecord",
            "type record save rtype ocsetting",
            "shape",
            "reader urword",
            "tagged false",
            "optional true",
        ],
        [
            "block period",
            "name save",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block period",
            "name printrecord",
            "type record print rtype ocsetting",
            "shape",
            "reader urword",
            "tagged false",
            "optional true",
        ],
        [
            "block period",
            "name print",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
            "tagged true",
            "optional false",
        ],
        [
            "block period",
            "name rtype",
            "type string",
            "shape",
            "in_record true",
            "reader urword",
            "tagged false",
            "optional false",
        ],
        [
            "block period",
            "name ocsetting",
            "type keystring all first last frequency steps",
            "shape",
            "tagged false",
            "in_record true",
            "reader urword",
        ],
        [
            "block period",
            "name all",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
        ],
        [
            "block period",
            "name first",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
        ],
        [
            "block period",
            "name last",
            "type keyword",
            "shape",
            "in_record true",
            "reader urword",
        ],
        [
            "block period",
            "name frequency",
            "type integer",
            "shape",
            "tagged true",
            "in_record true",
            "reader urword",
        ],
        [
            "block period",
            "name steps",
            "type integer",
            "shape (<nstp)",
            "tagged true",
            "in_record true",
            "reader urword",
        ],
    ]

    def __init__(
        self,
        model,
        loading_package=False,
        budget_filerecord=None,
        budgetcsv_filerecord=None,
        head_filerecord=None,
        headprintrecord=None,
        saverecord=None,
        printrecord=None,
        filename=None,
        pname=None,
        **kwargs,
    ):
        """
        ModflowGwfoc defines a OC package.

        Parameters
        ----------
        model
            Model that this package is a part of. Package is automatically
            added to model when it is initialized.
        loading_package : bool
            Do not set this parameter. It is intended for debugging and internal
            processing purposes only.
        budget_filerecord : record
        budgetcsv_filerecord : record
        head_filerecord : record
        headprintrecord : (head, print_format)
            * head : keyword
                    keyword to specify that record corresponds to head.
            * print_format : keyword
                    keyword to specify format for printing to the listing file.

        saverecord : (save, rtype, ocsetting)
            * save : keyword
                    keyword to indicate that information will be saved this stress period.
            * rtype : string
                    type of information to save or print.  Can be BUDGET or HEAD.
            * ocsetting : keystring all first last frequency steps
                    specifies the steps for which the data will be saved.

        printrecord : (print, rtype, ocsetting)
            * print : keyword
                    keyword to indicate that information will be printed this stress period.
            * rtype : string
                    type of information to save or print.  Can be BUDGET or HEAD.
            * ocsetting : keystring all first last frequency steps
                    specifies the steps for which the data will be saved.


        filename : str
            File name for this package.
        pname : str
            Package name for this package.
        parent_file : MFPackage
            Parent package file that references this package. Only needed for
            utility packages (mfutl*). For example, mfutllaktab package must have
            a mfgwflak package parent_file.
        """

        super().__init__(model, "oc", filename, pname, loading_package, **kwargs)

        self.budget_filerecord = self.build_mfdata(
            "budget_filerecord", budget_filerecord
        )
        self.budgetcsv_filerecord = self.build_mfdata(
            "budgetcsv_filerecord", budgetcsv_filerecord
        )
        self.head_filerecord = self.build_mfdata("head_filerecord", head_filerecord)
        self.headprintrecord = self.build_mfdata("headprintrecord", headprintrecord)
        self.saverecord = self.build_mfdata("saverecord", saverecord)
        self.printrecord = self.build_mfdata("printrecord", printrecord)

        self._init_complete = True
