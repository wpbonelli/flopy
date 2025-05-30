# autogenerated file, do not modify

from os import PathLike, curdir
from typing import Union

from flopy.mf6.data.mfdatautil import ArrayTemplateGenerator, ListTemplateGenerator
from flopy.mf6.mfpackage import MFChildPackages, MFPackage


class ModflowUtlsfrtab(MFPackage):
    """
    ModflowUtlsfrtab defines a SFRTAB package.

    Parameters
    ----------
    nrow : integer
        integer value specifying the number of rows in the reach cross-section table.
        there must be nrow rows of data in the table block.
    ncol : integer
        integer value specifying the number of columns in the reach cross-section
        table. there must be ncol columns of data in the table block. ncol must be
        equal to 2 if manfraction is not specified or 3 otherwise.
    table : [list]

    """

    table = ListTemplateGenerator(("sfrtab", "table", "table"))
    package_abbr = "utlsfrtab"
    _package_type = "sfrtab"
    dfn_file_name = "utl-sfrtab.dfn"
    dfn = [
        ["header", "multi-package"],
        [
            "block dimensions",
            "name nrow",
            "type integer",
            "reader urword",
            "optional false",
        ],
        [
            "block dimensions",
            "name ncol",
            "type integer",
            "reader urword",
            "optional false",
        ],
        [
            "block table",
            "name table",
            "type recarray xfraction height manfraction",
            "shape (nrow)",
            "reader urword",
        ],
        [
            "block table",
            "name xfraction",
            "type double precision",
            "shape",
            "tagged false",
            "in_record true",
            "reader urword",
        ],
        [
            "block table",
            "name height",
            "type double precision",
            "shape",
            "tagged false",
            "in_record true",
            "reader urword",
        ],
        [
            "block table",
            "name manfraction",
            "type double precision",
            "shape",
            "tagged false",
            "in_record true",
            "reader urword",
            "optional true",
        ],
    ]

    def __init__(
        self,
        model,
        loading_package=False,
        nrow=None,
        ncol=None,
        table=None,
        filename=None,
        pname=None,
        **kwargs,
    ):
        """
        ModflowUtlsfrtab defines a SFRTAB package.

        Parameters
        ----------
        model
            Model that this package is a part of. Package is automatically
            added to model when it is initialized.
        loading_package : bool
            Do not set this parameter. It is intended for debugging and internal
            processing purposes only.
        nrow : integer
            integer value specifying the number of rows in the reach cross-section table.
            there must be nrow rows of data in the table block.
        ncol : integer
            integer value specifying the number of columns in the reach cross-section
            table. there must be ncol columns of data in the table block. ncol must be
            equal to 2 if manfraction is not specified or 3 otherwise.
        table : [list]

        filename : str
            File name for this package.
        pname : str
            Package name for this package.
        parent_file : MFPackage
            Parent package file that references this package. Only needed for
            utility packages (mfutl*). For example, mfutllaktab package must have
            a mfgwflak package parent_file.
        """

        super().__init__(model, "sfrtab", filename, pname, loading_package, **kwargs)

        self.nrow = self.build_mfdata("nrow", nrow)
        self.ncol = self.build_mfdata("ncol", ncol)
        self.table = self.build_mfdata("table", table)

        self._init_complete = True
