import copy
import datetime
import errno
import inspect
import os
import sys
import warnings

import numpy as np

from ..mbase import ModelInterface
from ..pakbase import PackageInterface
from ..utils import datautil
from ..utils.check import mf6check
from ..version import __version__
from .coordinates import modeldimensions
from .data import (
    mfdata,
    mfdataarray,
    mfdatalist,
    mfdataplist,
    mfdatascalar,
    mfstructure,
)
from .data.mfdatautil import DataSearchOutput, MFComment, cellids_equal
from .data.mfstructure import DatumType, MFDataItemStructure, MFStructure
from .mfbase import (
    ExtFileAction,
    FlopyException,
    MFDataException,
    MFFileMgmt,
    MFInvalidTransientBlockHeaderException,
    PackageContainer,
    PackageContainerType,
    ReadAsArraysException,
    VerbosityLevel,
)
from .utils.output_util import MF6Output


class MFBlockHeader:
    """
    Represents the header of a block in a MF6 input file.  This class is used
    internally by FloPy and its direct use by a user of this library is not
    recommend.

    Parameters
    ----------
    name : str
        Block name
    variable_strings : list
        List of strings that appear after the block name
    comment : MFComment
        Comment text in the block header

    Attributes
    ----------
    name : str
        Block name
    variable_strings : list
        List of strings that appear after the block name
    comment : MFComment
        Comment text in the block header
    data_items : list
        List of MFVariable of the variables contained in this block

    """

    def __init__(
        self,
        name,
        variable_strings,
        comment,
        simulation_data=None,
        path=None,
        block=None,
    ):
        self.name = name
        self.variable_strings = variable_strings
        self.block = block
        if not (
            (simulation_data is None and path is None)
            or (simulation_data is not None and path is not None)
        ):
            raise FlopyException(
                "Block header must be initialized with both "
                "simulation_data and path or with neither."
            )
        if simulation_data is None:
            self.comment = comment
            self.simulation_data = None
            self.path = path
            self.comment_path = None
        else:
            self.connect_to_dict(simulation_data, path, comment)
        # TODO: Get data_items from dictionary
        self.data_items = []
        # build block comment paths
        self.blk_trailing_comment_path = ("blk_trailing_comment",)
        self.blk_post_comment_path = ("blk_post_comment",)
        if isinstance(path, list):
            path = tuple(path)
        if path is not None:
            self.blk_trailing_comment_path = path + (
                name,
                "blk_trailing_comment",
            )
            self.blk_post_comment_path = path + (
                name,
                "blk_post_comment",
            )
            if self.blk_trailing_comment_path not in simulation_data.mfdata:
                simulation_data.mfdata[self.blk_trailing_comment_path] = (
                    MFComment("", "", simulation_data, 0)
                )
            if self.blk_post_comment_path not in simulation_data.mfdata:
                simulation_data.mfdata[self.blk_post_comment_path] = MFComment(
                    "\n", "", simulation_data, 0
                )
        else:
            self.blk_trailing_comment_path = ("blk_trailing_comment",)
            self.blk_post_comment_path = ("blk_post_comment",)

    def __lt__(self, other):
        transient_key = self.get_transient_key()
        if transient_key is None:
            return True
        else:
            other_key = other.get_transient_key()
            if other_key is None:
                return False
            else:
                return transient_key < other_key

    def build_header_variables(
        self,
        simulation_data,
        block_header_structure,
        block_path,
        data,
        dimensions,
    ):
        """Builds data objects to hold header variables."""
        self.data_items = []
        var_path = block_path + (block_header_structure[0].name,)

        # fix up data
        fixed_data = []
        if (
            block_header_structure[0].data_item_structures[0].type
            == DatumType.keyword
        ):
            data_item = block_header_structure[0].data_item_structures[0]
            fixed_data.append(data_item.name)
        if isinstance(data, tuple):
            data = list(data)
        if isinstance(data, list):
            fixed_data = fixed_data + data
        else:
            fixed_data.append(data)
        if len(fixed_data) > 0:
            fixed_data = [tuple(fixed_data)]
        # create data object
        new_data = self.block.data_factory(
            simulation_data,
            None,
            block_header_structure[0],
            True,
            var_path,
            dimensions,
            fixed_data,
        )

        self.add_data_item(new_data, data)

    def add_data_item(self, new_data, data):
        """Adds data to the block."""
        self.data_items.append(new_data)
        while isinstance(data, list):
            if len(data) > 0:
                data = data[0]
            else:
                data = None
        if not isinstance(data, tuple):
            data = (data,)
        self.blk_trailing_comment_path += data
        self.blk_post_comment_path += data

    def is_same_header(self, block_header):
        """Checks if `block_header` is the same header as this header."""
        if len(self.variable_strings) > 0:
            if len(self.variable_strings) != len(
                block_header.variable_strings
            ):
                return False
            else:
                for sitem, oitem in zip(
                    self.variable_strings, block_header.variable_strings
                ):
                    if sitem != oitem:
                        return False
            return True
        elif (
            len(self.data_items) > 0 and len(block_header.variable_strings) > 0
        ):
            typ_obj = (
                self.data_items[0].structure.data_item_structures[0].type_obj
            )
            if typ_obj == int or typ_obj == float:
                return bool(
                    self.variable_strings[0]
                    == block_header.variable_strings[0]
                )
            else:
                return True
        elif len(self.data_items) == len(block_header.variable_strings):
            return True
        return False

    def get_comment(self):
        """Get block header comment"""
        if self.simulation_data is None:
            return self.comment
        else:
            return self.simulation_data.mfdata[self.comment_path]

    def connect_to_dict(self, simulation_data, path, comment=None):
        """Add comment to the simulation dictionary"""
        self.simulation_data = simulation_data
        self.path = path
        self.comment_path = path + ("blk_hdr_comment",)
        if comment is None:
            simulation_data.mfdata[self.comment_path] = self.comment
        else:
            simulation_data.mfdata[self.comment_path] = comment
        self.comment = None

    def write_header(self, fd):
        """Writes block header to file object `fd`.

        Parameters
        ----------
        fd : file object
            File object to write block header to.

        """
        fd.write(f"BEGIN {self.name}")
        if len(self.data_items) > 0:
            if isinstance(self.data_items[0], mfdatascalar.MFScalar):
                one_based = (
                    self.data_items[0].structure.type == DatumType.integer
                )
                entry = self.data_items[0].get_file_entry(
                    values_only=True, one_based=one_based
                )
            else:
                entry = self.data_items[0].get_file_entry()
            fd.write(str(entry.rstrip()))
            if len(self.data_items) > 1:
                for data_item in self.data_items[1:]:
                    entry = data_item.get_file_entry(values_only=True)
                    fd.write(str(entry).rstrip())
        if self.get_comment().text:
            fd.write(" ")
            self.get_comment().write(fd)
        fd.write("\n")

    def write_footer(self, fd):
        """Writes block footer to file object `fd`.

        Parameters
        ----------
        fd : file object
            File object to write block footer to.

        """
        fd.write(f"END {self.name}")
        if len(self.data_items) > 0:
            one_based = self.data_items[0].structure.type == DatumType.integer
            if isinstance(self.data_items[0], mfdatascalar.MFScalar):
                entry = self.data_items[0].get_file_entry(
                    values_only=True, one_based=one_based
                )
            else:
                entry = self.data_items[0].get_file_entry()
            fd.write(str(entry.rstrip()))
        fd.write("\n")

    def get_transient_key(self, data_path=None):
        """Get transient key associated with this block header."""
        transient_key = None
        for index in range(0, len(self.data_items)):
            if self.data_items[index].structure.type != DatumType.keyword:
                if data_path == self.data_items[index].path:
                    # avoid infinite recursion
                    return True
                transient_key = self.data_items[index].get_data()
                if isinstance(transient_key, np.recarray):
                    item_struct = self.data_items[index].structure
                    key_index = item_struct.first_non_keyword_index()
                    if not (
                        key_index is not None
                        and len(transient_key[0]) > key_index
                    ):
                        if key_index is None:
                            raise FlopyException(
                                "Block header index could "
                                "not be determined."
                            )
                        else:
                            raise FlopyException(
                                'Block header index "{}" '
                                'must be less than "{}"'
                                ".".format(key_index, len(transient_key[0]))
                            )
                    transient_key = transient_key[0][key_index]
                break
        return transient_key


class MFBlock:
    """
    Represents a block in a MF6 input file.  This class is used internally
    by FloPy and use by users of the FloPy library is not recommended.

    Parameters
    ----------
    simulation_data : MFSimulationData
        Data specific to this simulation
    dimensions : MFDimensions
        Describes model dimensions including model grid and simulation time
    structure : MFVariableStructure
        Structure describing block
    path : tuple
        Unique path to block

    Attributes
    ----------
    block_headers : MFBlockHeader
        Block header text (BEGIN/END), header variables, comments in the
        header
    structure : MFBlockStructure
        Structure describing block
    path : tuple
        Unique path to block
    datasets : OrderDict
        Dictionary of dataset objects with keys that are the name of the
        dataset
    datasets_keyword : dict
        Dictionary of dataset objects with keys that are key words to identify
        start of dataset
    enabled : bool
        If block is being used in the simulation

    """

    def __init__(
        self,
        simulation_data,
        dimensions,
        structure,
        path,
        model_or_sim,
        container_package,
    ):
        self._simulation_data = simulation_data
        self._dimensions = dimensions
        self._model_or_sim = model_or_sim
        self._container_package = container_package
        self.block_headers = [
            MFBlockHeader(
                structure.name,
                [],
                MFComment("", path, simulation_data, 0),
                simulation_data,
                path,
                self,
            )
        ]
        self.structure = structure
        self.path = path
        self.datasets = {}
        self.datasets_keyword = {}
        # initially disable if optional
        self.enabled = structure.number_non_optional_data() > 0
        self.loaded = False
        self.external_file_name = None
        self._structure_init()

    def __repr__(self):
        return self._get_data_str(True)

    def __str__(self):
        return self._get_data_str(False)

    def _get_data_str(self, formal):
        data_str = ""
        for dataset in self.datasets.values():
            if formal:
                ds_repr = repr(dataset)
                if len(ds_repr.strip()) > 0:
                    data_str = (
                        f"{data_str}{dataset.structure.name}\n{dataset!r}\n"
                    )
            else:
                ds_str = str(dataset)
                if len(ds_str.strip()) > 0:
                    data_str = (
                        f"{data_str}{dataset.structure.name}\n{dataset!s}\n"
                    )
        return data_str

    # return an MFScalar, MFList, or MFArray
    def data_factory(
        self,
        sim_data,
        model_or_sim,
        structure,
        enable,
        path,
        dimensions,
        data=None,
        package=None,
    ):
        """Creates the appropriate data child object derived from MFData."""
        data_type = structure.get_datatype()
        # examine the data structure and determine the data type
        if (
            data_type == mfstructure.DataType.scalar_keyword
            or data_type == mfstructure.DataType.scalar
        ):
            return mfdatascalar.MFScalar(
                sim_data,
                model_or_sim,
                structure,
                data,
                enable,
                path,
                dimensions,
            )
        elif (
            data_type == mfstructure.DataType.scalar_keyword_transient
            or data_type == mfstructure.DataType.scalar_transient
        ):
            trans_scalar = mfdatascalar.MFScalarTransient(
                sim_data, model_or_sim, structure, enable, path, dimensions
            )
            if data is not None:
                trans_scalar.set_data(data, key=0)
            return trans_scalar
        elif data_type == mfstructure.DataType.array:
            return mfdataarray.MFArray(
                sim_data,
                model_or_sim,
                structure,
                data,
                enable,
                path,
                dimensions,
                self,
            )
        elif data_type == mfstructure.DataType.array_transient:
            trans_array = mfdataarray.MFTransientArray(
                sim_data,
                model_or_sim,
                structure,
                enable,
                path,
                dimensions,
                self,
            )
            if data is not None:
                trans_array.set_data(data, key=0)
            return trans_array
        elif data_type == mfstructure.DataType.list:
            if (
                structure.basic_item
                and self._container_package.package_type.lower() != "nam"
                and self._simulation_data.use_pandas
            ):
                return mfdataplist.MFPandasList(
                    sim_data,
                    model_or_sim,
                    structure,
                    data,
                    enable,
                    path,
                    dimensions,
                    package,
                    self,
                )
            else:
                return mfdatalist.MFList(
                    sim_data,
                    model_or_sim,
                    structure,
                    data,
                    enable,
                    path,
                    dimensions,
                    package,
                    self,
                )
        elif data_type == mfstructure.DataType.list_transient:
            if structure.basic_item and self._simulation_data.use_pandas:
                trans_list = mfdataplist.MFPandasTransientList(
                    sim_data,
                    model_or_sim,
                    structure,
                    enable,
                    path,
                    dimensions,
                    package,
                    self,
                )
            else:
                trans_list = mfdatalist.MFTransientList(
                    sim_data,
                    model_or_sim,
                    structure,
                    enable,
                    path,
                    dimensions,
                    package,
                    self,
                )
            if data is not None:
                trans_list.set_data(data, key=0, autofill=True)
            return trans_list
        elif data_type == mfstructure.DataType.list_multiple:
            mult_list = mfdatalist.MFMultipleList(
                sim_data,
                model_or_sim,
                structure,
                enable,
                path,
                dimensions,
                package,
                self,
            )
            if data is not None:
                mult_list.set_data(data, key=0, autofill=True)
            return mult_list

    def _structure_init(self):
        # load datasets keywords into dictionary
        for dataset_struct in self.structure.data_structures.values():
            for keyword in dataset_struct.get_keywords():
                self.datasets_keyword[keyword] = dataset_struct
        # load block header data items into dictionary
        for dataset in self.structure.block_header_structure:
            self._new_dataset(dataset.name, dataset, True, None)

    def set_model_relative_path(self, model_ws):
        """Sets `model_ws` as the model path relative to the simulation's
        path.

        Parameters
        ----------
            model_ws : str
                Model path relative to the simulation's path.
        """
        # update datasets
        for key, dataset in self.datasets.items():
            if dataset.structure.file_data:
                try:
                    file_data = dataset.get_data()
                except MFDataException as mfde:
                    raise MFDataException(
                        mfdata_except=mfde,
                        model=self._container_package.model_name,
                        package=self._container_package._get_pname(),
                        message="Error occurred while "
                        "getting file data from "
                        '"{}"'.format(dataset.structure.name),
                    )
                if file_data:
                    # update file path location for all file paths
                    for file_line in file_data:
                        old_file_name = os.path.split(file_line[0])[1]
                        file_line[0] = os.path.join(model_ws, old_file_name)
        # update block headers
        for block_header in self.block_headers:
            for dataset in block_header.data_items:
                if dataset.structure.file_data:
                    try:
                        file_data = dataset.get_data()
                    except MFDataException as mfde:
                        raise MFDataException(
                            mfdata_except=mfde,
                            model=self._container_package.model_name,
                            package=self._container_package._get_pname(),
                            message="Error occurred while "
                            "getting file data from "
                            '"{}"'.format(dataset.structure.name),
                        )

                    if file_data:
                        # update file path location for all file paths
                        for file_line in file_data:
                            old_file_path, old_file_name = os.path.split(
                                file_line[1]
                            )
                            new_file_path = os.path.join(
                                model_ws, old_file_name
                            )
                            # update transient keys of datasets within the
                            # block
                            for key, idataset in self.datasets.items():
                                if isinstance(idataset, mfdata.MFTransient):
                                    idataset.update_transient_key(
                                        file_line[1], new_file_path
                                    )
                            file_line[1] = os.path.join(
                                model_ws, old_file_name
                            )

    def add_dataset(self, dataset_struct, data, var_path):
        """Add data to this block."""
        try:
            self.datasets[var_path[-1]] = self.data_factory(
                self._simulation_data,
                self._model_or_sim,
                dataset_struct,
                True,
                var_path,
                self._dimensions,
                data,
                self._container_package,
            )
        except MFDataException as mfde:
            raise MFDataException(
                mfdata_except=mfde,
                model=self._container_package.model_name,
                package=self._container_package._get_pname(),
                message="Error occurred while adding"
                ' dataset "{}" to block '
                '"{}"'.format(dataset_struct.name, self.structure.name),
            )

        self._simulation_data.mfdata[var_path] = self.datasets[var_path[-1]]
        dtype = dataset_struct.get_datatype()
        if (
            dtype == mfstructure.DataType.list_transient
            or dtype == mfstructure.DataType.list_multiple
            or dtype == mfstructure.DataType.array_transient
        ):
            # build repeating block header(s)
            if isinstance(data, dict):
                # Add block headers for each dictionary key
                for index in data:
                    if isinstance(index, tuple):
                        header_list = list(index)
                    else:
                        header_list = [index]
                    self._build_repeating_header(header_list)
            elif isinstance(data, list):
                # Add a single block header of value 0
                self._build_repeating_header([0])
            elif (
                dtype != mfstructure.DataType.list_multiple
                and data is not None
            ):
                self._build_repeating_header([[0]])

        return self.datasets[var_path[-1]]

    def _build_repeating_header(self, header_data):
        if self.header_exists(header_data[0]):
            return
        if (
            len(self.block_headers[-1].data_items) == 1
            and self.block_headers[-1].data_items[0].get_data() is not None
        ):
            block_header_path = self.path + (len(self.block_headers) + 1,)
            block_header = MFBlockHeader(
                self.structure.name,
                [],
                MFComment("", self.path, self._simulation_data, 0),
                self._simulation_data,
                block_header_path,
                self,
            )
            self.block_headers.append(block_header)
        else:
            block_header_path = self.path + (len(self.block_headers),)

        struct = self.structure
        last_header = self.block_headers[-1]
        try:
            last_header.build_header_variables(
                self._simulation_data,
                struct.block_header_structure,
                block_header_path,
                header_data,
                self._dimensions,
            )
        except MFDataException as mfde:
            raise MFDataException(
                mfdata_except=mfde,
                model=self._container_package.model_name,
                package=self._container_package._get_pname(),
                message="Error occurred while building"
                " block header variables for block "
                '"{}"'.format(last_header.name),
            )

    def _new_dataset(
        self, key, dataset_struct, block_header=False, initial_val=None
    ):
        dataset_path = self.path + (key,)
        if block_header:
            if (
                dataset_struct.type == DatumType.integer
                and initial_val is not None
                and len(initial_val) >= 1
                and dataset_struct.get_record_size()[0] == 1
            ):
                # stress periods are stored 0 based
                initial_val = int(initial_val[0]) - 1
            if isinstance(initial_val, list):
                initial_val_path = tuple(initial_val)
                initial_val = [tuple(initial_val)]
            else:
                initial_val_path = initial_val
            try:
                new_data = self.data_factory(
                    self._simulation_data,
                    self._model_or_sim,
                    dataset_struct,
                    True,
                    dataset_path,
                    self._dimensions,
                    initial_val,
                    self._container_package,
                )
            except MFDataException as mfde:
                raise MFDataException(
                    mfdata_except=mfde,
                    model=self._container_package.model_name,
                    package=self._container_package._get_pname(),
                    message="Error occurred while adding"
                    ' dataset "{}" to block '
                    '"{}"'.format(dataset_struct.name, self.structure.name),
                )
            self.block_headers[-1].add_data_item(new_data, initial_val_path)

        else:
            try:
                self.datasets[key] = self.data_factory(
                    self._simulation_data,
                    self._model_or_sim,
                    dataset_struct,
                    True,
                    dataset_path,
                    self._dimensions,
                    initial_val,
                    self._container_package,
                )
            except MFDataException as mfde:
                raise MFDataException(
                    mfdata_except=mfde,
                    model=self._container_package.model_name,
                    package=self._container_package._get_pname(),
                    message="Error occurred while adding"
                    ' dataset "{}" to block '
                    '"{}"'.format(dataset_struct.name, self.structure.name),
                )
        for keyword in dataset_struct.get_keywords():
            self.datasets_keyword[keyword] = dataset_struct

    def is_empty(self):
        """Returns true if this block is empty."""
        for key, dataset in self.datasets.items():
            try:
                has_data = dataset.has_data()
            except MFDataException as mfde:
                raise MFDataException(
                    mfdata_except=mfde,
                    model=self._container_package.model_name,
                    package=self._container_package._get_pname(),
                    message="Error occurred while verifying"
                    ' data of dataset "{}" in block '
                    '"{}"'.format(dataset.structure.name, self.structure.name),
                )

            if has_data is not None and has_data:
                return False
        return True

    def load(self, block_header, fd, strict=True):
        """Loads block from file object.  file object must be advanced to
        beginning of block before calling.

        Parameters
        ----------
            block_header : MFBlockHeader
                Block header for block block being loaded.
            fd : file
                File descriptor of file being loaded
            strict : bool
                Enforce strict MODFLOW 6 file format.
        """
        # verify number of header variables
        if (
            len(block_header.variable_strings)
            < self.structure.number_non_optional_block_header_data()
        ):
            if (
                self._simulation_data.verbosity_level.value
                >= VerbosityLevel.normal.value
            ):
                warning_str = (
                    'WARNING: Block header for block "{}" does not '
                    "contain the correct number of "
                    "variables {}".format(block_header.name, self.path)
                )
                print(warning_str)
            return

        if self.loaded:
            # verify header has not already been loaded
            for bh_current in self.block_headers:
                if bh_current.is_same_header(block_header):
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.normal.value
                    ):
                        warning_str = (
                            'WARNING: Block header for block "{}" is '
                            "not a unique block header "
                            "{}".format(block_header.name, self.path)
                        )
                        print(warning_str)
                    return

        # init
        self.enabled = True
        if not self.loaded:
            self.block_headers = []
        block_header.block = self
        self.block_headers.append(block_header)

        # process any header variable
        if len(self.structure.block_header_structure) > 0:
            dataset = self.structure.block_header_structure[0]
            self._new_dataset(
                dataset.name,
                dataset,
                True,
                self.block_headers[-1].variable_strings,
            )

        # handle special readasarrays case
        if (
            self._container_package.structure.read_as_arrays
            or (
                hasattr(self._container_package, "aux")
                and self._container_package.aux.structure.layered
            )
        ):
            # auxiliary variables may appear with aux variable name as keyword
            aux_vars = self._container_package.auxiliary.get_data()
            if aux_vars is not None:
                for var_name in list(aux_vars[0])[1:]:
                    self.datasets_keyword[(var_name,)] = (
                        self._container_package.aux.structure
                    )

        comments = []

        # capture any initial comments
        initial_comment = MFComment("", "", 0)
        fd_block = fd
        line = fd_block.readline()
        datautil.PyListUtil.reset_delimiter_used()
        arr_line = datautil.PyListUtil.split_data_line(line)
        post_data_comments = MFComment("", "", self._simulation_data, 0)
        while MFComment.is_comment(line, True):
            initial_comment.add_text(line)
            line = fd_block.readline()
            arr_line = datautil.PyListUtil.split_data_line(line)

        # if block not empty
        external_file_info = None
        if not (len(arr_line[0]) > 2 and arr_line[0][:3].upper() == "END"):
            if arr_line[0].lower() == "open/close":
                # open block contents from external file
                fd_block.readline()
                root_path = self._simulation_data.mfpath.get_sim_path()
                try:
                    file_name = os.path.split(arr_line[1])[-1]
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(
                            f'        opening external file "{file_name}"...'
                        )
                    external_file_info = arr_line
                except:
                    type_, value_, traceback_ = sys.exc_info()
                    message = f'Error reading external file specified in line "{line}"'
                    raise MFDataException(
                        self._container_package.model_name,
                        self._container_package._get_pname(),
                        self.path,
                        "reading external file",
                        self.structure.name,
                        inspect.stack()[0][3],
                        type_,
                        value_,
                        traceback_,
                        message,
                        self._simulation_data.debug,
                    )
            if len(self.structure.data_structures) <= 1:
                # load a single data set
                dataset = self.datasets[next(iter(self.datasets))]
                try:
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(
                            f"        loading data {dataset.structure.name}..."
                        )
                    next_line = dataset.load(
                        line,
                        fd_block,
                        self.block_headers[-1],
                        initial_comment,
                        external_file_info,
                    )
                except MFDataException as mfde:
                    raise MFDataException(
                        mfdata_except=mfde,
                        model=self._container_package.model_name,
                        package=self._container_package._get_pname(),
                        message='Error occurred while loading data "{}" in '
                        'block "{}" from file "{}"'
                        ".".format(
                            dataset.structure.name,
                            self.structure.name,
                            fd_block.name,
                        ),
                    )
                package_info_list = self._get_package_info(dataset)
                if package_info_list is not None:
                    for package_info in package_info_list:
                        if (
                            self._simulation_data.verbosity_level.value
                            >= VerbosityLevel.verbose.value
                        ):
                            print(
                                f"        loading child package {package_info[0]}..."
                            )
                        fname = package_info[1]
                        if package_info[2] is not None:
                            fname = os.path.join(package_info[2], fname)
                        filemgr = self._simulation_data.mfpath
                        fname = filemgr.strip_model_relative_path(
                            self._model_or_sim.name, fname
                        )
                        pkg = self._model_or_sim.load_package(
                            package_info[0],
                            fname,
                            package_info[1],
                            True,
                            "",
                            package_info[3],
                            self._container_package,
                        )
                        if hasattr(self._container_package, package_info[0]):
                            package_group = getattr(
                                self._container_package, package_info[0]
                            )
                            package_group._append_package(
                                pkg, pkg.filename, False
                            )

                if next_line[1] is not None:
                    arr_line = datautil.PyListUtil.split_data_line(
                        next_line[1]
                    )
                else:
                    arr_line = ""
                # capture any trailing comments
                dataset.post_data_comments = post_data_comments
                while arr_line and (
                    len(next_line[1]) <= 2 or arr_line[0][:3].upper() != "END"
                ):
                    next_line[1] = fd_block.readline().strip()
                    arr_line = datautil.PyListUtil.split_data_line(
                        next_line[1]
                    )
                    if arr_line and (
                        len(next_line[1]) <= 2
                        or arr_line[0][:3].upper() != "END"
                    ):
                        post_data_comments.add_text(" ".join(arr_line))
            else:
                # look for keyword and store line as data or comment
                try:
                    key, results = self._find_data_by_keyword(
                        line, fd_block, initial_comment
                    )
                except MFInvalidTransientBlockHeaderException as e:
                    warning_str = f"WARNING: {e}"
                    print(warning_str)
                    self.block_headers.pop()
                    return

                self._save_comments(arr_line, line, key, comments)
                if results[1] is None or results[1][:3].upper() != "END":
                    # block consists of unordered datasets
                    # load the data sets out of order based on
                    # initial constants
                    line = " "
                    while line != "":
                        line = fd_block.readline()
                        arr_line = datautil.PyListUtil.split_data_line(line)
                        if arr_line:
                            # determine if at end of block
                            if (
                                len(arr_line[0]) > 2
                                and arr_line[0][:3].upper() == "END"
                            ):
                                break
                            # look for keyword and store line as data o
                            # r comment
                            key, result = self._find_data_by_keyword(
                                line, fd_block, initial_comment
                            )
                            self._save_comments(arr_line, line, key, comments)
                            if (
                                result[1] is not None
                                and result[1][:3].upper() == "END"
                            ):
                                break
        else:
            # block empty, store empty array in block variables
            empty_arr = []
            for ds in self.datasets.values():
                if isinstance(ds, mfdata.MFTransient):
                    transient_key = block_header.get_transient_key()
                    ds.set_data(empty_arr, key=transient_key)
        self.loaded = True
        self.is_valid()

    def _find_data_by_keyword(self, line, fd, initial_comment):
        first_key = None
        nothing_found = False
        next_line = [True, line]
        while next_line[0] and not nothing_found:
            arr_line = datautil.PyListUtil.split_data_line(next_line[1])
            key = datautil.find_keyword(arr_line, self.datasets_keyword)
            if key is not None:
                ds_name = self.datasets_keyword[key].name
                try:
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(f"        loading data {ds_name}...")
                    next_line = self.datasets[ds_name].load(
                        next_line[1],
                        fd,
                        self.block_headers[-1],
                        initial_comment,
                    )
                except MFDataException as mfde:
                    raise MFDataException(
                        mfdata_except=mfde,
                        model=self._container_package.model_name,
                        package=self._container_package._get_pname(),
                        message="Error occurred while "
                        'loading data "{}" in '
                        'block "{}" from file "{}"'
                        ".".format(ds_name, self.structure.name, fd.name),
                    )

                # see if first item's name indicates a reference to
                # another package
                package_info_list = self._get_package_info(
                    self.datasets[ds_name]
                )
                if package_info_list is not None:
                    for package_info in package_info_list:
                        if (
                            self._simulation_data.verbosity_level.value
                            >= VerbosityLevel.verbose.value
                        ):
                            print(
                                f"        loading child package {package_info[1]}..."
                            )
                        fname = package_info[1]
                        if package_info[2] is not None:
                            fname = os.path.join(package_info[2], fname)
                        filemgr = self._simulation_data.mfpath
                        fname = filemgr.strip_model_relative_path(
                            self._model_or_sim.name, fname
                        )
                        pkg = self._model_or_sim.load_package(
                            package_info[0],
                            fname,
                            package_info[1],
                            True,
                            "",
                            package_info[3],
                            self._container_package,
                        )
                        if hasattr(self._container_package, package_info[0]):
                            package_group = getattr(
                                self._container_package, package_info[0]
                            )
                            package_group._append_package(
                                pkg, pkg.filename, False
                            )
                if first_key is None:
                    first_key = key
                nothing_found = False
            elif (
                arr_line[0].lower() == "readasarrays"
                and self.path[-1].lower() == "options"
                and self._container_package.structure.read_as_arrays is False
            ):
                error_msg = (
                    "ERROR: Attempting to read a ReadAsArrays "
                    "package as a non-ReadAsArrays "
                    "package {}".format(self.path)
                )
                raise ReadAsArraysException(error_msg)
            else:
                nothing_found = True

        if first_key is None:
            # look for recarrays.  if there is a lone recarray in this block,
            # use it by default
            recarrays = self.structure.get_all_recarrays()
            if len(recarrays) != 1:
                return key, [None, None]
            dataset = self.datasets[recarrays[0].name]
            ds_result = dataset.load(
                line, fd, self.block_headers[-1], initial_comment
            )

            # see if first item's name indicates a reference to another
            # package
            package_info_list = self._get_package_info(dataset)
            if package_info_list is not None:
                for package_info in package_info_list:
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(
                            f"        loading child package {package_info[0]}..."
                        )
                    fname = package_info[1]
                    if package_info[2] is not None:
                        fname = os.path.join(package_info[2], fname)
                    filemgr = self._simulation_data.mfpath
                    fname = filemgr.strip_model_relative_path(
                        self._model_or_sim.name, fname
                    )
                    pkg = self._model_or_sim.load_package(
                        package_info[0],
                        fname,
                        None,
                        True,
                        "",
                        package_info[3],
                        self._container_package,
                    )
                    if hasattr(self._container_package, package_info[0]):
                        package_group = getattr(
                            self._container_package, package_info[0]
                        )
                        package_group._append_package(pkg, pkg.filename, False)

            return recarrays[0].keyword, ds_result
        else:
            return first_key, next_line

    def _get_package_info(self, dataset):
        if not dataset.structure.file_data:
            return None
        for index in range(0, len(dataset.structure.data_item_structures)):
            data_item = dataset.structure.data_item_structures[index]
            if (
                data_item.type == DatumType.keyword
                or data_item.type == DatumType.string
            ):
                item_name = data_item.name
                package_type = item_name[:-1]
                model_type = self._model_or_sim.structure.model_type
                # not all packages have the same naming convention
                # try different naming conventions to find the appropriate
                # package
                package_types = [
                    package_type,
                    f"{self._container_package.package_type}"
                    f"{package_type}",
                ]
                package_type_found = None
                for ptype in package_types:
                    if (
                        PackageContainer.package_factory(ptype, model_type)
                        is not None
                    ):
                        package_type_found = ptype
                        break
                if package_type_found is not None:
                    try:
                        data = dataset.get_data()
                    except MFDataException as mfde:
                        raise MFDataException(
                            mfdata_except=mfde,
                            model=self._container_package.model_name,
                            package=self._container_package._get_pname(),
                            message="Error occurred while "
                            'getting data from "{}" '
                            'in block "{}".'.format(
                                dataset.structure.name, self.structure.name
                            ),
                        )
                    package_info_list = []
                    if isinstance(data, np.recarray):
                        for row in data:
                            self._add_to_info_list(
                                package_info_list,
                                row[index],
                                package_type_found,
                            )
                    else:
                        self._add_to_info_list(
                            package_info_list, data, package_type_found
                        )

                    return package_info_list
        return None

    def _add_to_info_list(
        self, package_info_list, file_location, package_type_found
    ):
        file_path, file_name = os.path.split(file_location)
        dict_package_name = f"{package_type_found}_{self.path[-2]}"
        package_info_list.append(
            (
                package_type_found,
                file_name,
                file_path,
                dict_package_name,
            )
        )

    def _save_comments(self, arr_line, line, key, comments):
        # FIX: Save these comments somewhere in the data set
        if key not in self.datasets_keyword:
            if MFComment.is_comment(key, True):
                if comments:
                    comments.append("\n")
                comments.append(arr_line)

    def write(self, fd, ext_file_action=ExtFileAction.copy_relative_paths):
        """Writes block to a file object.

        Parameters
        ----------
        fd : file object
            File object to write to.

        """
        # never write an empty block
        is_empty = self.is_empty()
        if (
            is_empty
            and self.structure.name.lower() != "exchanges"
            and self.structure.name.lower() != "options"
            and self.structure.name.lower() != "sources"
            and self.structure.name.lower() != "stressperioddata"
        ):
            return
        if self.structure.repeating():
            repeating_datasets = self._find_repeating_datasets()
            for repeating_dataset in repeating_datasets:
                # resolve any missing block headers
                self._add_missing_block_headers(repeating_dataset)
            for block_header in sorted(self.block_headers):
                # write block
                self._write_block(fd, block_header, ext_file_action)
        else:
            self._write_block(fd, self.block_headers[0], ext_file_action)

    def _add_missing_block_headers(self, repeating_dataset):
        key_data_list = repeating_dataset.get_active_key_list()
        # assemble a dictionary of data keys and empty keys
        key_dict = {}
        for key in key_data_list:
            key_dict[key[0]] = True
        for key, value in repeating_dataset.empty_keys.items():
            if value:
                key_dict[key] = True
        for key in key_dict.keys():
            has_data = repeating_dataset.has_data(key)
            empty_key = (
                key in repeating_dataset.empty_keys
                and repeating_dataset.empty_keys[key]
            )
            if not self.header_exists(key) and (has_data or empty_key):
                self._build_repeating_header([key])

    def header_exists(self, key, data_path=None):
        if not isinstance(key, list):
            if key is None:
                return
            comp_key_list = [key]
        else:
            comp_key_list = key
        for block_header in self.block_headers:
            transient_key = block_header.get_transient_key(data_path)
            if transient_key is True:
                return
            for comp_key in comp_key_list:
                if transient_key is not None and transient_key == comp_key:
                    return True
        return False

    def set_all_data_external(
        self,
        base_name,
        check_data=True,
        external_data_folder=None,
        binary=False,
    ):
        """Sets the block's list and array data to be stored externally,
        base_name is external file name's prefix, check_data determines
        if data error checking is enabled during this process.

        Warning
        -------
        The MF6 check mechanism is deprecated pending reimplementation
        in a future release. While the checks API will remain in place
        through 3.x, it may be unstable, and will likely change in 4.x.

        Parameters
        ----------
            base_name : str
                Base file name of external files where data will be written to.
            check_data : bool
                Whether to do data error checking.
            external_data_folder
                Folder where external data will be stored
            binary: bool
                Whether file will be stored as binary

        """

        for key, dataset in self.datasets.items():
            lst_data = isinstance(dataset, mfdatalist.MFList) or isinstance(
                dataset, mfdataplist.MFPandasList
            )
            if (
                isinstance(dataset, mfdataarray.MFArray)
                or (lst_data and dataset.structure.type == DatumType.recarray)
                and dataset.enabled
            ):
                if not binary or (
                    lst_data
                    and (
                        dataset.data_dimensions.package_dim.boundnames()
                        or not dataset.structure.basic_item
                    )
                ):
                    ext = "txt"
                    binary = False
                else:
                    ext = "bin"
                file_path = f"{base_name}_{dataset.structure.name}.{ext}"
                replace_existing_external = False
                if external_data_folder is not None:
                    # get simulation root path
                    root_path = self._simulation_data.mfpath.get_sim_path()
                    # get model relative path, if it exists
                    if isinstance(self._model_or_sim, ModelInterface):
                        name = self._model_or_sim.name
                        rel_path = (
                            self._simulation_data.mfpath.model_relative_path[
                                name
                            ]
                        )
                        if rel_path is not None:
                            root_path = os.path.join(root_path, rel_path)
                    full_path = os.path.join(root_path, external_data_folder)
                    if not os.path.exists(full_path):
                        # create new external data folder
                        os.makedirs(full_path)
                    file_path = os.path.join(external_data_folder, file_path)
                    replace_existing_external = True
                dataset.store_as_external_file(
                    file_path,
                    replace_existing_external=replace_existing_external,
                    check_data=check_data,
                    binary=binary,
                )

    def set_all_data_internal(self, check_data=True):
        """Sets the block's list and array data to be stored internally,
        check_data determines if data error checking is enabled during this
        process.

        Warning
        -------
        The MF6 check mechanism is deprecated pending reimplementation
        in a future release. While the checks API will remain in place
        through 3.x, it may be unstable, and will likely change in 4.x.

        Parameters
        ----------
            check_data : bool
                Whether to do data error checking.

        """

        for key, dataset in self.datasets.items():
            if (
                isinstance(dataset, mfdataarray.MFArray)
                or (
                    (
                        isinstance(dataset, mfdatalist.MFList)
                        or isinstance(dataset, mfdataplist.MFPandasList)
                    )
                    and dataset.structure.type == DatumType.recarray
                )
                and dataset.enabled
            ):
                dataset.store_internal(check_data=check_data)

    def _find_repeating_datasets(self):
        repeating_datasets = []
        for key, dataset in self.datasets.items():
            if dataset.repeating:
                repeating_datasets.append(dataset)
        return repeating_datasets

    def _prepare_external(self, fd, file_name, binary=False):
        fd_main = fd
        fd_path = self._simulation_data.mfpath.get_model_path(self.path[0])
        # resolve full file and folder path
        fd_file_path = os.path.join(fd_path, file_name)
        fd_folder_path = os.path.split(fd_file_path)[0]
        if fd_folder_path != "":
            if not os.path.exists(fd_folder_path):
                # create new external data folder
                os.makedirs(fd_folder_path)
        return fd_main, fd_file_path

    def _write_block(self, fd, block_header, ext_file_action):
        transient_key = None
        basic_list = False
        dataset_one = list(self.datasets.values())[0]
        if isinstance(
            dataset_one,
            (mfdataplist.MFPandasList, mfdataplist.MFPandasTransientList),
        ):
            basic_list = True
            for dataset in self.datasets.values():
                assert isinstance(
                    dataset,
                    (
                        mfdataplist.MFPandasList,
                        mfdataplist.MFPandasTransientList,
                    ),
                )
            # write block header
            block_header.write_header(fd)
        if len(block_header.data_items) > 0:
            transient_key = block_header.get_transient_key()

        # gather data sets to write
        data_set_output = []
        data_found = False
        for key, dataset in self.datasets.items():
            try:
                if transient_key is None:
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(
                            f"        writing data {dataset.structure.name}..."
                        )
                    if basic_list:
                        ext_fname = dataset.external_file_name()
                        if ext_fname is not None:
                            binary = dataset.binary_ext_data()
                            # write block contents to external file
                            fd_main, fd = self._prepare_external(
                                fd, ext_fname, binary
                            )
                            dataset.write_file_entry(fd, fd_main=fd_main)
                            fd = fd_main
                        else:
                            dataset.write_file_entry(fd)
                    else:
                        data_set_output.append(
                            dataset.get_file_entry(
                                ext_file_action=ext_file_action
                            )
                        )
                    data_found = True
                else:
                    if (
                        self._simulation_data.verbosity_level.value
                        >= VerbosityLevel.verbose.value
                    ):
                        print(
                            "        writing data {} ({}).." ".".format(
                                dataset.structure.name, transient_key
                            )
                        )
                    if basic_list:
                        ext_fname = dataset.external_file_name(transient_key)
                        if ext_fname is not None:
                            binary = dataset.binary_ext_data(transient_key)
                            # write block contents to external file
                            fd_main, fd = self._prepare_external(
                                fd, ext_fname, binary
                            )
                            dataset.write_file_entry(
                                fd,
                                transient_key,
                                ext_file_action=ext_file_action,
                                fd_main=fd_main,
                            )
                            fd = fd_main
                        else:
                            dataset.write_file_entry(
                                fd,
                                transient_key,
                                ext_file_action=ext_file_action,
                            )
                    else:
                        if dataset.repeating:
                            output = dataset.get_file_entry(
                                transient_key, ext_file_action=ext_file_action
                            )
                            if output is not None:
                                data_set_output.append(output)
                                data_found = True
                        else:
                            data_set_output.append(
                                dataset.get_file_entry(
                                    ext_file_action=ext_file_action
                                )
                            )
                    data_found = True
            except MFDataException as mfde:
                raise MFDataException(
                    mfdata_except=mfde,
                    model=self._container_package.model_name,
                    package=self._container_package._get_pname(),
                    message=(
                        "Error occurred while writing data "
                        f'"{dataset.structure.name}" in block '
                        f'"{self.structure.name}" to file "{fd.name}"'
                    ),
                )
        if not data_found:
            return
        if not basic_list:
            # write block header
            block_header.write_header(fd)

            if self.external_file_name is not None:
                indent_string = self._simulation_data.indent_string
                fd.write(
                    f"{indent_string}open/close "
                    f'"{self.external_file_name}"\n'
                )
                # write block contents to external file
                fd_main, fd = self._prepare_external(
                    fd, self.external_file_name
                )
            # write data sets
            for output in data_set_output:
                fd.write(output)

        # write trailing comments
        pth = block_header.blk_trailing_comment_path
        if pth in self._simulation_data.mfdata:
            self._simulation_data.mfdata[pth].write(fd)

        if self.external_file_name is not None and not basic_list:
            # switch back writing to package file
            fd.close()
            fd = fd_main

        # write block footer
        block_header.write_footer(fd)

        # write post block comments
        pth = block_header.blk_post_comment_path
        if pth in self._simulation_data.mfdata:
            self._simulation_data.mfdata[pth].write(fd)

        # write extra line if comments are off
        if not self._simulation_data.comments_on:
            fd.write("\n")

    def is_allowed(self):
        """Determine if block is valid based on the values of dependent
        MODFLOW variables."""
        if self.structure.variable_dependant_path:
            # fill in empty part of the path with the current path
            if len(self.structure.variable_dependant_path) == 3:
                dependant_var_path = (
                    self.path[0],
                ) + self.structure.variable_dependant_path
            elif len(self.structure.variable_dependant_path) == 2:
                dependant_var_path = (
                    self.path[0],
                    self.path[1],
                ) + self.structure.variable_dependant_path
            elif len(self.structure.variable_dependant_path) == 1:
                dependant_var_path = (
                    self.path[0],
                    self.path[1],
                    self.path[2],
                ) + self.structure.variable_dependant_path
            else:
                dependant_var_path = None

            # get dependency
            dependant_var = None
            mf_data = self._simulation_data.mfdata
            if dependant_var_path in mf_data:
                dependant_var = mf_data[dependant_var_path]

            # resolve dependency
            if self.structure.variable_value_when_active[0] == "Exists":
                exists = self.structure.variable_value_when_active[1]
                if dependant_var and exists.lower() == "true":
                    return True
                elif not dependant_var and exists.lower() == "false":
                    return True
                else:
                    return False
            elif not dependant_var:
                return False
            elif self.structure.variable_value_when_active[0] == ">":
                min_val = self.structure.variable_value_when_active[1]
                if dependant_var > float(min_val):
                    return True
                else:
                    return False
            elif self.structure.variable_value_when_active[0] == "<":
                max_val = self.structure.variable_value_when_active[1]
                if dependant_var < float(max_val):
                    return True
                else:
                    return False
        return True

    def is_valid(self):
        """
        Returns true if the block is valid.
        """
        # check data sets
        for dataset in self.datasets.values():
            # Non-optional datasets must be enabled
            if not dataset.structure.optional and not dataset.enabled:
                return False
            # Enabled blocks must be valid
            if dataset.enabled and not dataset.is_valid:
                return False
        # check variables
        for block_header in self.block_headers:
            for dataset in block_header.data_items:
                # Non-optional datasets must be enabled
                if not dataset.structure.optional and not dataset.enabled:
                    return False
                # Enabled blocks must be valid
                if dataset.enabled and not dataset.is_valid():
                    return False


class MFPackage(PackageInterface):
    """
    Provides an interface for the user to specify data to build a package.

    Parameters
    ----------
    parent : MFModel, MFSimulation, or MFPackage
        The parent model, simulation, or package containing this package
    package_type : str
        String defining the package type
    filename : str or PathLike
        Name or path of file where this package is stored
    quoted_filename : str
        Filename with quotes around it when there is a space in the name
    pname : str
        Package name
    loading_package : bool
        Whether or not to add this package to the parent container's package
        list during initialization

    Attributes
    ----------
    blocks : dict
        Dictionary of blocks contained in this package by block name
    path : tuple
        Data dictionary path to this package
    structure : PackageStructure
        Describes the blocks and data contain in this package
    dimensions : PackageDimension
        Resolves data dimensions for data within this package

    """

    def __init__(
        self,
        parent,
        package_type,
        filename=None,
        pname=None,
        loading_package=False,
        **kwargs,
    ):
        parent_file = kwargs.pop("parent_file", None)
        if isinstance(parent, MFPackage):
            self.model_or_sim = parent.model_or_sim
            self.parent_file = parent
        elif parent_file is not None:
            self.model_or_sim = parent
            self.parent_file = parent_file
        else:
            self.model_or_sim = parent
            self.parent_file = None
        _internal_package = kwargs.pop("_internal_package", False)
        if _internal_package:
            self.internal_package = True
        else:
            self.internal_package = False
        self._data_list = []
        self._package_type = package_type
        if self.model_or_sim.type == "Model" and package_type.lower() != "nam":
            self.model_name = self.model_or_sim.name
        else:
            self.model_name = None

        # a package must have a dfn_file_name
        if not hasattr(self, "dfn_file_name"):
            self.dfn_file_name = ""

        if (
            self.model_or_sim.type != "Model"
            and self.model_or_sim.type != "Simulation"
        ):
            message = (
                "Invalid model_or_sim parameter. Expecting either a "
                'model or a simulation. Instead type "{}" was '
                "given.".format(type(self.model_or_sim))
            )
            type_, value_, traceback_ = sys.exc_info()
            raise MFDataException(
                self.model_name,
                pname,
                "",
                "initializing package",
                None,
                inspect.stack()[0][3],
                type_,
                value_,
                traceback_,
                message,
                self.model_or_sim.simulation_data.debug,
            )

        self._package_container = PackageContainer(
            self.model_or_sim.simulation_data
        )
        self.simulation_data = self.model_or_sim.simulation_data

        self.blocks = {}
        self.container_type = []
        self.loading_package = loading_package
        if pname is not None:
            if not isinstance(pname, str):
                message = (
                    "Invalid pname parameter. Expecting type str. "
                    'Instead type "{}" was '
                    "given.".format(type(pname))
                )
                type_, value_, traceback_ = sys.exc_info()
                raise MFDataException(
                    self.model_name,
                    pname,
                    "",
                    "initializing package",
                    None,
                    inspect.stack()[0][3],
                    type_,
                    value_,
                    traceback_,
                    message,
                    self.model_or_sim.simulation_data.debug,
                )

            self.package_name = pname.lower()
        else:
            self.package_name = None

        if filename is None:
            if self.model_or_sim.type == "Simulation":
                # filename uses simulation base name
                base_name = os.path.basename(
                    os.path.normpath(self.model_or_sim.name)
                )
                self._filename = f"{base_name}.{package_type}"
            else:
                # filename uses model base name
                self._filename = f"{self.model_or_sim.name}.{package_type}"
        else:
            if not isinstance(filename, (str, os.PathLike)):
                message = (
                    "Invalid fname parameter. Expecting type str. "
                    'Instead type "{}" was '
                    "given.".format(type(filename))
                )
                type_, value_, traceback_ = sys.exc_info()
                raise MFDataException(
                    self.model_name,
                    pname,
                    "",
                    "initializing package",
                    None,
                    inspect.stack()[0][3],
                    type_,
                    value_,
                    traceback_,
                    message,
                    self.model_or_sim.simulation_data.debug,
                )
            self._filename = datautil.clean_filename(
                str(filename).replace("\\", "/")
            )
        self.path, self.structure = self.model_or_sim.register_package(
            self, not loading_package, pname is None, filename is None
        )
        self.dimensions = self.create_package_dimensions()

        if self.path is None:
            if (
                self.simulation_data.verbosity_level.value
                >= VerbosityLevel.normal.value
            ):
                print(
                    "WARNING: Package type {} failed to register property."
                    " {}".format(self._package_type, self.path)
                )
        if self.parent_file is not None:
            self.container_type.append(PackageContainerType.package)
        # init variables that may be used later
        self.post_block_comments = None
        self.last_error = None
        self.bc_color = "black"
        self.__inattr = False
        self._child_package_groups = {}
        child_builder_call = kwargs.pop("child_builder_call", None)
        if (
            self.parent_file is not None
            and child_builder_call is None
            and package_type in self.parent_file._child_package_groups
        ):
            # initialize as part of the parent's child package group
            chld_pkg_grp = self.parent_file._child_package_groups[package_type]
            chld_pkg_grp.init_package(self, self._filename, False)

        # remove any remaining valid kwargs
        key_list = list(kwargs.keys())
        for key in key_list:
            if "filerecord" in key and hasattr(self, f"{key}"):
                kwargs.pop(f"{key}")
        # check for extraneous kwargs
        if len(kwargs) > 0:
            kwargs_str = ", ".join(kwargs.keys())
            excpt_str = (
                f'Extraneous kwargs "{kwargs_str}" provided to MFPackage.'
            )
            raise FlopyException(excpt_str)

    def __init_subclass__(cls):
        """Register package type"""
        super().__init_subclass__()
        PackageContainer.packages_by_abbr[cls.package_abbr] = cls

    def __setattr__(self, name, value):
        if hasattr(self, name) and getattr(self, name) is not None:
            attribute = object.__getattribute__(self, name)
            if attribute is not None and isinstance(attribute, mfdata.MFData):
                try:
                    if isinstance(attribute, mfdatalist.MFList):
                        attribute.set_data(value, autofill=True)
                    else:
                        attribute.set_data(value)
                except MFDataException as mfde:
                    raise MFDataException(
                        mfdata_except=mfde,
                        model=self.model_name,
                        package=self._get_pname(),
                    )
                return

        if all(
            hasattr(self, attr) for attr in ["model_or_sim", "_package_type"]
        ):
            if hasattr(self.model_or_sim, "_mg_resync"):
                if not self.model_or_sim._mg_resync:
                    self.model_or_sim._mg_resync = self._mg_resync

        super().__setattr__(name, value)

    def __repr__(self):
        return self._get_data_str(True)

    def __str__(self):
        return self._get_data_str(False)

    @property
    def filename(self):
        """Package's file name."""
        return self._filename

    @property
    def quoted_filename(self):
        """Package's file name with quotes if there is a space."""
        if " " in self._filename:
            return f'"{self._filename}"'
        return self._filename

    @filename.setter
    def filename(self, fname):
        """Package's file name."""
        if (
            isinstance(self.parent_file, MFPackage)
            and self.package_type in self.parent_file._child_package_groups
        ):
            fname = datautil.clean_filename(fname)
            try:
                child_pkg_group = self.parent_file._child_package_groups[
                    self.structure.file_type
                ]
                child_pkg_group._update_filename(self._filename, fname)
            except Exception:
                print(
                    "WARNING: Unable to update file name for parent"
                    f"package of {self.package_name}."
                )
        if self.model_or_sim is not None and fname is not None:
            if self._package_type != "nam":
                self.model_or_sim.update_package_filename(self, fname)
        self._filename = fname

    @property
    def package_type(self):
        """String describing type of package"""
        return self._package_type

    @property
    def name(self):
        """Name of package"""
        return [self.package_name]

    @name.setter
    def name(self, name):
        """Name of package"""
        self.package_name = name

    @property
    def parent(self):
        """Parent package"""
        return self.model_or_sim

    @parent.setter
    def parent(self, parent):
        """Parent package"""
        assert False, "Do not use this setter to set the parent"

    @property
    def plottable(self):
        """If package is plottable"""
        if self.model_or_sim.type == "Simulation":
            return False
        else:
            return True

    @property
    def output(self):
        """
        Method to get output associated with a specific package

        Returns
        -------
            MF6Output object
        """
        return MF6Output(self)

    @property
    def data_list(self):
        """List of data in this package."""
        # return [data_object, data_object, ...]
        return self._data_list

    @property
    def package_key_dict(self):
        """
        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_type_dict

    @property
    def package_names(self):
        """Returns a list of package names.

        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_names

    @property
    def package_dict(self):
        """
        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_dict

    @property
    def package_type_dict(self):
        """
        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_type_dict

    @property
    def package_name_dict(self):
        """
        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_name_dict

    @property
    def package_filename_dict(self):
        """
        .. deprecated:: 3.9
            This method is for internal use only and will be deprecated.
        """
        warnings.warn(
            "This method is for internal use only and will be deprecated.",
            category=DeprecationWarning,
        )
        return self._package_container.package_filename_dict

    def get_package(self, name=None, type_only=False, name_only=False):
        """
        Finds a package by package name, package key, package type, or partial
        package name. returns either a single package, a list of packages,
        or None.

        Parameters
        ----------
        name : str
            Name or type of the package, 'my-riv-1, 'RIV', 'LPF', etc.
        type_only : bool
            Search for package by type only
        name_only : bool
            Search for package by name only

        Returns
        -------
        pp : Package object

        """
        return self._package_container.get_package(name, type_only, name_only)

    def add_package(self, package):
        pkg_type = package.package_type.lower()
        if pkg_type in self._package_container.package_type_dict:
            for existing_pkg in self._package_container.package_type_dict[
                pkg_type
            ]:
                if existing_pkg is package:
                    # do not add the same package twice
                    return
        self._package_container.add_package(package)

    def _get_aux_data(self, aux_names):
        if hasattr(self, "stress_period_data"):
            spd = self.stress_period_data.get_data()
            if (
                0 in spd
                and spd[0] is not None
                and aux_names[0][1] in spd[0].dtype.names
            ):
                return spd
        if hasattr(self, "packagedata"):
            pd = self.packagedata.get_data()
            if aux_names[0][1] in pd.dtype.names:
                return pd
        if hasattr(self, "perioddata"):
            spd = self.perioddata.get_data()
            if (
                0 in spd
                and spd[0] is not None
                and aux_names[0][1] in spd[0].dtype.names
            ):
                return spd
        if hasattr(self, "aux"):
            return self.aux.get_data()
        return None

    def _boundnames_active(self):
        if hasattr(self, "boundnames"):
            if self.boundnames.get_data():
                return True
        return False

    def check(self, f=None, verbose=True, level=1, checktype=None):
        """
        Data check, returns True on success.

        Warning
        -------
        The MF6 check mechanism is deprecated pending reimplementation
        in a future release. While the checks API will remain in place
        through 3.x, it may be unstable, and will likely change in 4.x.
        """

        if checktype is None:
            checktype = mf6check
        # do general checks
        chk = super().check(f, verbose, level, checktype)

        # do mf6 specific checks
        if hasattr(self, "auxiliary"):
            # auxiliary variable check
            # check if auxiliary variables are defined
            aux_names = self.auxiliary.get_data()
            if aux_names is not None and len(aux_names[0]) > 1:
                num_aux_names = len(aux_names[0]) - 1
                # check for stress period data
                aux_data = self._get_aux_data(aux_names)
                if aux_data is not None and len(aux_data) > 0:
                    # make sure the check object exists
                    if chk is None:
                        chk = self._get_check(f, verbose, level, checktype)
                    if isinstance(aux_data, dict):
                        aux_datasets = list(aux_data.values())
                    else:
                        aux_datasets = [aux_data]
                    dataset_type = "unknown"
                    for dataset in aux_datasets:
                        if isinstance(dataset, np.recarray):
                            dataset_type = "recarray"
                            break
                        elif isinstance(dataset, np.ndarray):
                            dataset_type = "ndarray"
                            break
                    # if aux data is in a list
                    if dataset_type == "recarray":
                        # check for time series data
                        time_series_name_dict = {}
                        if hasattr(self, "ts") and hasattr(
                            self.ts, "time_series_namerecord"
                        ):
                            # build dictionary of time series data variables
                            ts_nr = self.ts.time_series_namerecord.get_data()
                            if ts_nr is not None:
                                for item in ts_nr:
                                    if len(item) > 0 and item[0] is not None:
                                        time_series_name_dict[item[0]] = True
                        # auxiliary variables are last unless boundnames
                        # defined, then second to last
                        if self._boundnames_active():
                            offset = 1
                        else:
                            offset = 0

                        # loop through stress period datasets with aux data
                        for data in aux_datasets:
                            if isinstance(data, np.recarray):
                                for row in data:
                                    row_size = len(row)
                                    aux_start_loc = (
                                        row_size - num_aux_names - offset - 1
                                    )
                                    # loop through auxiliary variables
                                    for idx, var in enumerate(
                                        list(aux_names[0])[1:]
                                    ):
                                        # get index of current aux variable
                                        data_index = aux_start_loc + idx
                                        # verify auxiliary value is either
                                        # numeric or time series variable
                                        if (
                                            not datautil.DatumUtil.is_float(
                                                row[data_index]
                                            )
                                            and row[data_index]
                                            not in time_series_name_dict
                                        ):
                                            desc = (
                                                f"Invalid non-numeric "
                                                f"value "
                                                f"'{row[data_index]}' "
                                                f"in auxiliary data."
                                            )
                                            chk._add_to_summary(
                                                "Error",
                                                desc=desc,
                                                package=self.package_name,
                                            )
                    # else if stress period data is arrays
                    elif dataset_type == "ndarray":
                        # loop through auxiliary stress period datasets
                        for data in aux_datasets:
                            # verify auxiliary value is either numeric or time
                            # array series variable
                            if isinstance(data, np.ndarray):
                                val = np.isnan(np.sum(data))
                                if val:
                                    desc = (
                                        "One or more nan values were "
                                        "found in auxiliary data."
                                    )
                                    chk._add_to_summary(
                                        "Warning",
                                        desc=desc,
                                        package=self.package_name,
                                    )
        return chk

    def _get_nan_exclusion_list(self):
        excl_list = []
        if hasattr(self, "stress_period_data"):
            spd_struct = self.stress_period_data.structure
            for item_struct in spd_struct.data_item_structures:
                if item_struct.optional or item_struct.keystring_dict:
                    excl_list.append(item_struct.name)
        return excl_list

    def _get_data_str(self, formal, show_data=True):
        data_str = (
            "package_name = {}\nfilename = {}\npackage_type = {}"
            "\nmodel_or_simulation_package = {}"
            "\n{}_name = {}"
            "\n".format(
                self._get_pname(),
                self._filename,
                self.package_type,
                self.model_or_sim.type.lower(),
                self.model_or_sim.type.lower(),
                self.model_or_sim.name,
            )
        )
        if self.parent_file is not None and formal:
            data_str = (
                f"{data_str}parent_file = {self.parent_file._get_pname()}\n\n"
            )
        else:
            data_str = f"{data_str}\n"
        if show_data:
            for block in self.blocks.values():
                if formal:
                    bl_repr = repr(block)
                    if len(bl_repr.strip()) > 0:
                        data_str = (
                            "{}Block {}\n--------------------\n{}" "\n".format(
                                data_str, block.structure.name, repr(block)
                            )
                        )
                else:
                    bl_str = str(block)
                    if len(bl_str.strip()) > 0:
                        data_str = (
                            "{}Block {}\n--------------------\n{}" "\n".format(
                                data_str, block.structure.name, str(block)
                            )
                        )
        return data_str

    def _get_pname(self):
        if self.package_name is not None:
            return str(self.package_name)
        else:
            return str(self._filename)

    def _get_block_header_info(self, line, path):
        # init
        header_variable_strs = []
        arr_clean_line = line.strip().split()
        header_comment = MFComment(
            "", path + (arr_clean_line[1],), self.simulation_data, 0
        )
        # break header into components
        if len(arr_clean_line) < 2:
            message = (
                "Block header does not contain a name. Name "
                'expected in line "{}".'.format(line)
            )
            type_, value_, traceback_ = sys.exc_info()
            raise MFDataException(
                self.model_name,
                self._get_pname(),
                self.path,
                "parsing block header",
                None,
                inspect.stack()[0][3],
                type_,
                value_,
                traceback_,
                message,
                self.simulation_data.debug,
            )
        elif len(arr_clean_line) == 2:
            return MFBlockHeader(
                arr_clean_line[1],
                header_variable_strs,
                header_comment,
                self.simulation_data,
                path,
            )
        else:
            # process text after block name
            comment = False
            for entry in arr_clean_line[2:]:
                # if start of comment
                if MFComment.is_comment(entry.strip()[0]):
                    comment = True
                if comment:
                    header_comment.text = " ".join(
                        [header_comment.text, entry]
                    )
                else:
                    header_variable_strs.append(entry)
            return MFBlockHeader(
                arr_clean_line[1],
                header_variable_strs,
                header_comment,
                self.simulation_data,
                path,
            )

    def _update_size_defs(self):
        # build temporary data lookup by name
        data_lookup = {}
        for block in self.blocks.values():
            for dataset in block.datasets.values():
                data_lookup[dataset.structure.name] = dataset

        # loop through all data
        for block in self.blocks.values():
            for dataset in block.datasets.values():
                # if data shape is 1-D
                if (
                    dataset.structure.shape
                    and len(dataset.structure.shape) == 1
                ):
                    # if shape name is data in this package
                    if dataset.structure.shape[0] in data_lookup:
                        size_def = data_lookup[dataset.structure.shape[0]]
                        size_def_name = size_def.structure.name

                        if isinstance(dataset, mfdata.MFTransient):
                            # for transient data always use the maximum size
                            new_size = -1
                            for key in dataset.get_active_key_list():
                                try:
                                    data = dataset.get_data(key=key[0])
                                except (OSError, MFDataException):
                                    # TODO: Handle case where external file
                                    # path has been moved
                                    data = None
                                if data is not None:
                                    data_len = len(data)
                                    if data_len > new_size:
                                        new_size = data_len
                        else:
                            # for all other data set max to size
                            new_size = -1
                            try:
                                data = dataset.get_data()
                            except (OSError, MFDataException):
                                # TODO: Handle case where external file
                                # path has been moved
                                data = None
                            if data is not None:
                                new_size = len(dataset.get_data())

                        if size_def.get_data() is None:
                            current_size = -1
                        else:
                            current_size = size_def.get_data()

                        if new_size > current_size:
                            # store current size
                            size_def.set_data(new_size)

                            # informational message to the user
                            if (
                                self.simulation_data.verbosity_level.value
                                >= VerbosityLevel.normal.value
                            ):
                                print(
                                    "INFORMATION: {} in {} changed to {} "
                                    "based on size of {}".format(
                                        size_def_name,
                                        size_def.structure.path[:-1],
                                        new_size,
                                        dataset.structure.name,
                                    )
                                )

    def inspect_cells(self, cell_list, stress_period=None):
        """
        Inspect model cells.  Returns package data associated with cells.

        Parameters
        ----------
        cell_list : list of tuples
            List of model cells.  Each model cell is a tuple of integers.
            ex: [(1,1,1), (2,4,3)]
        stress_period : int
            For transient data, only return data from this stress period.  If
            not specified or None, all stress period data will be returned.

        Returns
        -------
        output : array
            Array containing inspection results

        """
        data_found = []

        # loop through blocks
        local_index_names = []
        local_index_blocks = []
        local_index_values = []
        local_index_cellids = []
        # loop through blocks in package
        for block in self.blocks.values():
            # loop through data in block
            for dataset in block.datasets.values():
                if isinstance(dataset, mfdatalist.MFList):
                    # handle list data
                    cellid_column = None
                    local_index_name = None
                    # loop through list data column definitions
                    for index, data_item in enumerate(
                        dataset.structure.data_item_structures
                    ):
                        if index == 0 and data_item.type == DatumType.integer:
                            local_index_name = data_item.name
                        # look for cellid column in list data row
                        if isinstance(data_item, MFDataItemStructure) and (
                            data_item.is_cellid or data_item.possible_cellid
                        ):
                            cellid_column = index
                            break
                    if cellid_column is not None:
                        data_output = DataSearchOutput(dataset.path)
                        local_index_vals = []
                        local_index_cells = []
                        # get data
                        if isinstance(dataset, mfdatalist.MFTransientList):
                            # data may be in multiple transient blocks, get
                            # data from appropriate blocks
                            main_data = dataset.get_data(stress_period)
                            if stress_period is not None:
                                main_data = {stress_period: main_data}
                        else:
                            # data is all in one block, get data
                            main_data = {-1: dataset.get_data()}

                        # loop through each dataset
                        for key, value in main_data.items():
                            if value is None:
                                continue
                            if data_output.data_header is None:
                                data_output.data_header = value.dtype.names
                            # loop through list data rows
                            for line in value:
                                # loop through list of cells we are searching
                                # for
                                for cell in cell_list:
                                    if isinstance(
                                        line[cellid_column], tuple
                                    ) and cellids_equal(
                                        line[cellid_column], cell
                                    ):
                                        # save data found
                                        data_output.data_entries.append(line)
                                        data_output.data_entry_ids.append(cell)
                                        data_output.data_entry_stress_period.append(
                                            key
                                        )
                                        if datautil.DatumUtil.is_int(line[0]):
                                            # save index data for further
                                            # processing.  assuming index is
                                            # always first entry
                                            local_index_vals.append(line[0])
                                            local_index_cells.append(cell)

                        if (
                            local_index_name is not None
                            and len(local_index_vals) > 0
                        ):
                            # capture index lookups for scanning related data
                            local_index_names.append(local_index_name)
                            local_index_blocks.append(block.path[-1])
                            local_index_values.append(local_index_vals)
                            local_index_cellids.append(local_index_cells)
                        if len(data_output.data_entries) > 0:
                            data_found.append(data_output)
                elif isinstance(dataset, mfdataarray.MFArray):
                    # handle array data
                    data_shape = copy.deepcopy(
                        dataset.structure.data_item_structures[0].shape
                    )
                    if dataset.path[-1] == "top":
                        # top is a special case where the two datasets
                        # need to be combined to get the correct layer top
                        model_grid = self.model_or_sim.modelgrid
                        main_data = {-1: model_grid.top_botm}
                        data_shape.append("nlay")
                    else:
                        if isinstance(dataset, mfdataarray.MFTransientArray):
                            # data may be in multiple blocks, get data from
                            # appropriate blocks
                            main_data = dataset.get_data(stress_period)
                            if stress_period is not None:
                                main_data = {stress_period: main_data}
                        else:
                            # data is all in one block, get a process data
                            main_data = {-1: dataset.get_data()}
                    if main_data is None:
                        continue
                    data_output = DataSearchOutput(dataset.path)
                    # loop through datasets
                    for key, array_data in main_data.items():
                        if array_data is None:
                            continue
                        self.model_or_sim.match_array_cells(
                            cell_list, data_shape, array_data, key, data_output
                        )
                    if len(data_output.data_entries) > 0:
                        data_found.append(data_output)

        if len(local_index_names) > 0:
            # look for data that shares the index value with data found
            # for example a shared well or reach number
            for block in self.blocks.values():
                # loop through data
                for dataset in block.datasets.values():
                    if isinstance(dataset, mfdatalist.MFList):
                        data_item = dataset.structure.data_item_structures[0]
                        data_output = DataSearchOutput(dataset.path)
                        # loop through previous data found
                        for (
                            local_index_name,
                            local_index_vals,
                            cell_ids,
                            local_block_name,
                        ) in zip(
                            local_index_names,
                            local_index_values,
                            local_index_cellids,
                            local_index_blocks,
                        ):
                            if local_block_name == block.path[-1]:
                                continue
                            if (
                                isinstance(data_item, MFDataItemStructure)
                                and data_item.name == local_index_name
                                and data_item.type == DatumType.integer
                            ):
                                # matching data index type found, get data
                                if isinstance(
                                    dataset, mfdatalist.MFTransientList
                                ):
                                    # data may be in multiple blocks, get data
                                    # from appropriate blocks
                                    main_data = dataset.get_data(stress_period)
                                    if stress_period is not None:
                                        main_data = {stress_period: main_data}
                                else:
                                    # data is all in one block
                                    main_data = {-1: dataset.get_data()}
                                # loop through the data
                                for key, value in main_data.items():
                                    if value is None:
                                        continue
                                    if data_output.data_header is None:
                                        data_output.data_header = (
                                            value.dtype.names
                                        )
                                    # loop through each row of data
                                    for line in value:
                                        # loop through the index values we are
                                        # looking for
                                        for index_val, cell_id in zip(
                                            local_index_vals, cell_ids
                                        ):
                                            # try to match index values we are
                                            # looking for to the data
                                            if index_val == line[0]:
                                                # save data found
                                                data_output.data_entries.append(
                                                    line
                                                )
                                                data_output.data_entry_ids.append(
                                                    index_val
                                                )
                                                data_output.data_entry_cellids.append(
                                                    cell_id
                                                )
                                                data_output.data_entry_stress_period.append(
                                                    key
                                                )
                        if len(data_output.data_entries) > 0:
                            data_found.append(data_output)
        return data_found

    def remove(self):
        """Removes this package from the simulation/model it is currently a
        part of.
        """
        self.model_or_sim.remove_package(self)

    def build_child_packages_container(self, pkg_type, filerecord):
        """Builds a container object for any child packages.  This method is
        only intended for FloPy internal use."""
        # get package class
        package_obj = PackageContainer.package_factory(
            pkg_type, self.model_or_sim.model_type
        )
        # create child package object
        child_pkgs_name = f"utl{pkg_type}packages"
        child_pkgs_obj = PackageContainer.package_factory(child_pkgs_name, "")
        if child_pkgs_obj is None and self.model_or_sim.model_type is None:
            # simulation level object, try just the package type in the name
            child_pkgs_name = f"{pkg_type}packages"
            child_pkgs_obj = PackageContainer.package_factory(
                child_pkgs_name, ""
            )
        if child_pkgs_obj is None:
            # see if the package is part of one of the supported model types
            for model_type in MFStructure().sim_struct.model_types:
                child_pkgs_name = f"{model_type}{pkg_type}packages"
                child_pkgs_obj = PackageContainer.package_factory(
                    child_pkgs_name, ""
                )
                if child_pkgs_obj is not None:
                    break
        child_pkgs = child_pkgs_obj(
            self.model_or_sim, self, pkg_type, filerecord, None, package_obj
        )
        setattr(self, pkg_type, child_pkgs)
        self._child_package_groups[pkg_type] = child_pkgs

    def _get_dfn_name_dict(self):
        dfn_name_dict = {}
        item_num = 0
        for item in self.structure.dfn_list:
            if len(item) > 1:
                item_name = item[1].split()
                if len(item_name) > 1 and item_name[0] == "name":
                    dfn_name_dict[item_name[1]] = item_num
                    item_num += 1
        return dfn_name_dict

    def build_child_package(self, pkg_type, data, parameter_name, filerecord):
        """Builds a child package.  This method is only intended for FloPy
        internal use."""
        if not hasattr(self, pkg_type):
            self.build_child_packages_container(pkg_type, filerecord)
        if data is not None:
            package_group = getattr(self, pkg_type)
            # build child package file name
            child_path = package_group.next_default_file_path()
            # create new empty child package
            package_obj = PackageContainer.package_factory(
                pkg_type, self.model_or_sim.model_type
            )
            package = package_obj(
                self, filename=child_path, child_builder_call=True
            )
            assert hasattr(package, parameter_name)

            if isinstance(data, dict):
                # order data correctly
                dfn_name_dict = package._get_dfn_name_dict()
                ordered_data_items = []
                for key, value in data.items():
                    if key in dfn_name_dict:
                        ordered_data_items.append(
                            [dfn_name_dict[key], key, value]
                        )
                    else:
                        ordered_data_items.append([999999, key, value])
                ordered_data_items = sorted(
                    ordered_data_items, key=lambda x: x[0]
                )

                # evaluate and add data to package
                unused_data = {}
                for order, key, value in ordered_data_items:
                    # if key is an attribute of the child package
                    if isinstance(key, str) and hasattr(package, key):
                        # set child package attribute
                        child_data_attr = getattr(package, key)
                        if isinstance(child_data_attr, mfdatalist.MFList):
                            child_data_attr.set_data(value, autofill=True)
                        elif isinstance(child_data_attr, mfdata.MFData):
                            child_data_attr.set_data(value)
                        elif key == "fname" or key == "filename":
                            child_path = value
                            package._filename = value
                        else:
                            setattr(package, key, value)
                    else:
                        unused_data[key] = value
                if unused_data:
                    setattr(package, parameter_name, unused_data)
            else:
                setattr(package, parameter_name, data)

            # append package to list
            package_group.init_package(package, child_path)
            return package

    def build_mfdata(self, var_name, data=None):
        """Returns the appropriate data type object (mfdatalist, mfdataarray,
        or mfdatascalar) given that object the appropriate structure (looked
        up based on var_name) and any data supplied.  This method is for
        internal FloPy library use only.

        Parameters
        ----------
        var_name : str
            Variable name

        data : many supported types
            Data contained in this object

        Returns
        -------
        data object : MFData subclass

        """
        if self.loading_package:
            data = None
        for key, block in self.structure.blocks.items():
            if var_name in block.data_structures:
                if block.name not in self.blocks:
                    self.blocks[block.name] = MFBlock(
                        self.simulation_data,
                        self.dimensions,
                        block,
                        self.path + (key,),
                        self.model_or_sim,
                        self,
                    )
                dataset_struct = block.data_structures[var_name]
                var_path = self.path + (key, var_name)
                ds = self.blocks[block.name].add_dataset(
                    dataset_struct, data, var_path
                )
                self._data_list.append(ds)
                return ds

        message = 'Unable to find variable "{}" in package ' '"{}".'.format(
            var_name, self.package_type
        )
        type_, value_, traceback_ = sys.exc_info()
        raise MFDataException(
            self.model_name,
            self._get_pname(),
            self.path,
            "building data objects",
            None,
            inspect.stack()[0][3],
            type_,
            value_,
            traceback_,
            message,
            self.simulation_data.debug,
        )

    def set_model_relative_path(self, model_ws):
        """Sets the model path relative to the simulation's path.

        Parameters
        ----------
        model_ws : str
            Model path relative to the simulation's path.

        """
        # update blocks
        for key, block in self.blocks.items():
            block.set_model_relative_path(model_ws)
        # update sub-packages
        for package in self._package_container.packagelist:
            package.set_model_relative_path(model_ws)

    def set_all_data_external(
        self,
        check_data=True,
        external_data_folder=None,
        base_name=None,
        binary=False,
    ):
        """Sets the package's list and array data to be stored externally.

        Parameters
        ----------
            check_data : bool
                Determine if data error checking is enabled
            external_data_folder
                Folder where external data will be stored
            base_name: str
                Base file name prefix for all files
            binary: bool
                Whether file will be stored as binary
        """
        # set blocks
        for key, block in self.blocks.items():
            file_name = os.path.split(self.filename)[1]
            if base_name is not None:
                file_name = f"{base_name}_{file_name}"
            block.set_all_data_external(
                file_name,
                check_data,
                external_data_folder,
                binary,
            )
        # set sub-packages
        for package in self._package_container.packagelist:
            package.set_all_data_external(
                check_data,
                external_data_folder,
                base_name,
                binary,
            )

    def set_all_data_internal(self, check_data=True):
        """Sets the package's list and array data to be stored internally.

        Parameters
        ----------
            check_data : bool
                Determine if data error checking is enabled

        """
        # set blocks
        for key, block in self.blocks.items():
            block.set_all_data_internal(check_data)
        # set sub-packages
        for package in self._package_container.packagelist:
            package.set_all_data_internal(check_data)

    def load(self, strict=True):
        """Loads the package from file.

        Parameters
        ----------
        strict : bool
            Enforce strict checking of data.

        Returns
        -------
        success : bool

        """
        # open file
        try:
            fd_input_file = open(
                datautil.clean_filename(self.get_file_path()), "r"
            )
        except OSError as e:
            if e.errno == errno.ENOENT:
                message = "File {} of type {} could not be opened.".format(
                    self.get_file_path(), self.package_type
                )
                type_, value_, traceback_ = sys.exc_info()
                raise MFDataException(
                    self.model_name,
                    self.package_name,
                    self.path,
                    "loading package file",
                    None,
                    inspect.stack()[0][3],
                    type_,
                    value_,
                    traceback_,
                    message,
                    self.simulation_data.debug,
                )

        try:
            self._load_blocks(fd_input_file, strict)
        except ReadAsArraysException as err:
            fd_input_file.close()
            raise ReadAsArraysException(err)
        # close file
        fd_input_file.close()

        if self.simulation_data.auto_set_sizes:
            self._update_size_defs()

        # return validity of file
        return self.is_valid()

    def is_valid(self):
        """Returns whether or not this package is valid.

        Returns
        -------
        is valid : bool

        """
        # Check blocks
        for block in self.blocks.values():
            # Non-optional blocks must be enabled
            if (
                block.structure.number_non_optional_data() > 0
                and not block.enabled
                and block.is_allowed()
            ):
                self.last_error = (
                    f'Required block "{block.block_header.name}" not enabled'
                )
                return False
            # Enabled blocks must be valid
            if block.enabled and not block.is_valid:
                self.last_error = f'Invalid block "{block.block_header.name}"'
                return False

        return True

    def _load_blocks(self, fd_input_file, strict=True, max_blocks=sys.maxsize):
        # init
        self.simulation_data.mfdata[self.path + ("pkg_hdr_comments",)] = (
            MFComment("", self.path, self.simulation_data)
        )
        self.post_block_comments = MFComment(
            "", self.path, self.simulation_data
        )

        blocks_read = 0
        found_first_block = False
        line = " "
        while line != "":
            line = fd_input_file.readline()
            clean_line = line.strip()
            # If comment or empty line
            if MFComment.is_comment(clean_line, True):
                self._store_comment(line, found_first_block)
            elif len(clean_line) > 4 and clean_line[:5].upper() == "BEGIN":
                # parse block header
                try:
                    block_header_info = self._get_block_header_info(
                        line, self.path
                    )
                except MFDataException as mfde:
                    message = (
                        "An error occurred while loading block header "
                        'in line "{}".'.format(line)
                    )
                    type_, value_, traceback_ = sys.exc_info()
                    raise MFDataException(
                        self.model_name,
                        self._get_pname(),
                        self.path,
                        "loading block header",
                        None,
                        inspect.stack()[0][3],
                        type_,
                        value_,
                        traceback_,
                        message,
                        self.simulation_data.debug,
                        mfde,
                    )

                # if there is more than one possible block with the same name,
                # resolve the correct block to use
                block_key = block_header_info.name.lower()
                block_num = 1
                possible_key = f"{block_header_info.name.lower()}-{block_num}"
                if possible_key in self.blocks:
                    block_key = possible_key
                    block_header_name = block_header_info.name.lower()
                    while (
                        block_key in self.blocks
                        and not self.blocks[block_key].is_allowed()
                    ):
                        block_key = f"{block_header_name}-{block_num}"
                        block_num += 1

                if block_key not in self.blocks:
                    # block name not recognized, load block as comments and
                    # issue a warning
                    if (
                        self.simulation_data.verbosity_level.value
                        >= VerbosityLevel.normal.value
                    ):
                        warning_str = (
                            'WARNING: Block "{}" is not a valid block '
                            "name for file type "
                            "{}.".format(block_key, self.package_type)
                        )
                        print(warning_str)
                    self._store_comment(line, found_first_block)
                    while line != "":
                        line = fd_input_file.readline()
                        self._store_comment(line, found_first_block)
                        arr_line = datautil.PyListUtil.split_data_line(line)
                        if arr_line and (
                            len(arr_line[0]) <= 2
                            or arr_line[0][:3].upper() == "END"
                        ):
                            break
                else:
                    found_first_block = True
                    skip_block = False
                    cur_block = self.blocks[block_key]
                    if cur_block.loaded:
                        # Only blocks defined as repeating are allowed to have
                        # multiple entries
                        header_name = block_header_info.name
                        if not self.structure.blocks[
                            header_name.lower()
                        ].repeating():
                            # warn and skip block
                            if (
                                self.simulation_data.verbosity_level.value
                                >= VerbosityLevel.normal.value
                            ):
                                warning_str = (
                                    'WARNING: Block "{}" has '
                                    "multiple entries and is not "
                                    "intended to be a repeating "
                                    "block ({} package"
                                    ")".format(header_name, self.package_type)
                                )
                                print(warning_str)
                            skip_block = True
                    bhs = cur_block.structure.block_header_structure
                    bhval = block_header_info.variable_strings
                    if (
                        len(bhs) > 0
                        and len(bhval) > 0
                        and bhs[0].name == "iper"
                    ):
                        nper = self.simulation_data.mfdata[
                            ("tdis", "dimensions", "nper")
                        ].get_data()
                        bhval_int = datautil.DatumUtil.is_int(bhval[0])
                        if not bhval_int or int(bhval[0]) > nper:
                            # skip block when block stress period is greater
                            # than nper
                            skip_block = True

                    if not skip_block:
                        if (
                            self.simulation_data.verbosity_level.value
                            >= VerbosityLevel.verbose.value
                        ):
                            print(
                                f"      loading block {cur_block.structure.name}..."
                            )
                        # reset comments
                        self.post_block_comments = MFComment(
                            "", self.path, self.simulation_data
                        )

                        cur_block.load(
                            block_header_info, fd_input_file, strict
                        )

                        # write post block comment
                        self.simulation_data.mfdata[
                            cur_block.block_headers[-1].blk_post_comment_path
                        ] = self.post_block_comments

                        blocks_read += 1
                        if blocks_read >= max_blocks:
                            break
                    else:
                        # treat skipped block as if it is all comments
                        arr_line = datautil.PyListUtil.split_data_line(
                            clean_line
                        )
                        self.post_block_comments.add_text(str(line), True)
                        while arr_line and (
                            len(line) <= 2 or arr_line[0][:3].upper() != "END"
                        ):
                            line = fd_input_file.readline()
                            arr_line = datautil.PyListUtil.split_data_line(
                                line.strip()
                            )
                            if arr_line:
                                self.post_block_comments.add_text(
                                    str(line), True
                                )
                        self.simulation_data.mfdata[
                            cur_block.block_headers[-1].blk_post_comment_path
                        ] = self.post_block_comments

            else:
                if not (
                    len(clean_line) == 0
                    or (len(line) > 2 and line[:3].upper() == "END")
                ):
                    # Record file location of beginning of unresolved text
                    # treat unresolved text as a comment for now
                    self._store_comment(line, found_first_block)

    def write(self, ext_file_action=ExtFileAction.copy_relative_paths):
        """Writes the package to a file.

        Parameters
        ----------
        ext_file_action : ExtFileAction
            How to handle pathing of external data files.
        """
        if self.simulation_data.auto_set_sizes:
            self._update_size_defs()

        # create any folders in path
        package_file_path = self.get_file_path()
        package_folder = os.path.split(package_file_path)[0]
        if package_folder and not os.path.isdir(package_folder):
            os.makedirs(os.path.split(package_file_path)[0])

        # open file
        fd = open(package_file_path, "w")

        # write flopy header
        if self.simulation_data.write_headers:
            dt = datetime.datetime.now()
            header = (
                "# File generated by Flopy version {} on {} at {}."
                "\n".format(
                    __version__,
                    dt.strftime("%m/%d/%Y"),
                    dt.strftime("%H:%M:%S"),
                )
            )
            fd.write(header)

        # write blocks
        self._write_blocks(fd, ext_file_action)

        fd.close()

    def create_package_dimensions(self):
        """Creates a package dimensions object.  For internal FloPy library
        use.

        Returns
        -------
        package dimensions : PackageDimensions

        """
        model_dims = None
        if self.container_type[0] == PackageContainerType.model:
            model_dims = [
                modeldimensions.ModelDimensions(
                    self.path[0], self.simulation_data
                )
            ]
        else:
            # this is a simulation file that does not correspond to a specific
            # model.  figure out which model to use and return a dimensions
            # object for that model
            if self.dfn_file_name[0:3] == "exg":
                exchange_rec_array = self.simulation_data.mfdata[
                    ("nam", "exchanges", "exchanges")
                ].get_data()
                if exchange_rec_array is None:
                    return None
                for exchange in exchange_rec_array:
                    if exchange[1].lower() == self._filename.lower():
                        model_dims = [
                            modeldimensions.ModelDimensions(
                                exchange[2], self.simulation_data
                            ),
                            modeldimensions.ModelDimensions(
                                exchange[3], self.simulation_data
                            ),
                        ]
                        break
            elif (
                self.dfn_file_name[4:7] == "gnc"
                and self.model_or_sim.type == "Simulation"
            ):
                # get exchange file name associated with gnc package
                if self.parent_file is not None:
                    exg_file_name = self.parent_file.filename
                else:
                    raise Exception(
                        "Can not create a simulation-level "
                        "gnc file without a corresponding "
                        "exchange file. Exchange file must be "
                        "created first."
                    )
                # get models associated with exchange file from sim nam file
                try:
                    exchange_recarray_data = (
                        self.model_or_sim.name_file.exchanges.get_data()
                    )
                except MFDataException as mfde:
                    message = (
                        "An error occurred while retrieving exchange "
                        "data from the simulation name file.  The error "
                        "occurred while processing gnc file "
                        f'"{self.filename}".'
                    )
                    raise MFDataException(
                        mfdata_except=mfde,
                        package=self._get_pname(),
                        message=message,
                    )
                assert exchange_recarray_data is not None
                model_1 = None
                model_2 = None
                for exchange in exchange_recarray_data:
                    if exchange[1] == exg_file_name:
                        model_1 = exchange[2]
                        model_2 = exchange[3]

                # assign models to gnc package
                model_dims = [
                    modeldimensions.ModelDimensions(
                        model_1, self.simulation_data
                    ),
                    modeldimensions.ModelDimensions(
                        model_2, self.simulation_data
                    ),
                ]
            elif self.parent_file is not None:
                model_dims = []
                for md in self.parent_file.dimensions.model_dim:
                    model_name = md.model_name
                    model_dims.append(
                        modeldimensions.ModelDimensions(
                            model_name, self.simulation_data
                        )
                    )
            else:
                model_dims = [
                    modeldimensions.ModelDimensions(None, self.simulation_data)
                ]
        return modeldimensions.PackageDimensions(
            model_dims, self.structure, self.path
        )

    def _store_comment(self, line, found_first_block):
        # Store comment
        if found_first_block:
            self.post_block_comments.text += line
        else:
            self.simulation_data.mfdata[
                self.path + ("pkg_hdr_comments",)
            ].text += line

    def _write_blocks(self, fd, ext_file_action):
        # verify that all blocks are valid
        if not self.is_valid():
            message = (
                'Unable to write out model file "{}" due to the '
                "following error: "
                "{} ({})".format(self._filename, self.last_error, self.path)
            )
            type_, value_, traceback_ = sys.exc_info()
            raise MFDataException(
                self.model_name,
                self._get_pname(),
                self.path,
                "writing package blocks",
                None,
                inspect.stack()[0][3],
                type_,
                value_,
                traceback_,
                message,
                self.simulation_data.debug,
            )

        # write initial comments
        pkg_hdr_comments_path = self.path + ("pkg_hdr_comments",)
        if pkg_hdr_comments_path in self.simulation_data.mfdata:
            self.simulation_data.mfdata[
                self.path + ("pkg_hdr_comments",)
            ].write(fd, False)

        # loop through blocks
        block_num = 1
        for block in self.blocks.values():
            if (
                self.simulation_data.verbosity_level.value
                >= VerbosityLevel.verbose.value
            ):
                print(f"      writing block {block.structure.name}...")
            # write block
            block.write(fd, ext_file_action=ext_file_action)
            block_num += 1

    def get_file_path(self):
        """Returns the package file's path.

        Returns
        -------
        file path : str
        """
        if self.path[0] in self.simulation_data.mfpath.model_relative_path:
            return os.path.join(
                self.simulation_data.mfpath.get_model_path(self.path[0]),
                self._filename,
            )
        else:
            return os.path.join(
                self.simulation_data.mfpath.get_sim_path(), self._filename
            )

    def export(self, f, **kwargs):
        """
        Method to export a package to netcdf or shapefile based on the
        extension of the file name (.shp for shapefile, .nc for netcdf)

        Parameters
        ----------
        f : str
            Filename
        kwargs : keyword arguments
            modelgrid : flopy.discretization.Grid instance
                User supplied modelgrid which can be used for exporting
                in lieu of the modelgrid associated with the model object

        Returns
        -------
            None or Netcdf object

        """
        from .. import export

        return export.utils.package_export(f, self, **kwargs)

    def plot(self, **kwargs):
        """
        Plot 2-D, 3-D, transient 2-D, and stress period list (MfList)
        package input data

        Parameters
        ----------
        **kwargs : dict
            filename_base : str
                Base file name that will be used to automatically generate
                file names for output image files. Plots will be exported as
                image files if file_name_base is not None. (default is None)
            file_extension : str
                Valid matplotlib.pyplot file extension for savefig(). Only
                used if filename_base is not None. (default is 'png')
            mflay : int
                MODFLOW zero-based layer number to return.  If None, then all
                all layers will be included. (default is None)
            kper : int
                MODFLOW zero-based stress period number to return. (default is
                zero)
            key : str
                MfList dictionary key. (default is None)

        Returns
        -------
        axes : list
            Empty list is returned if filename_base is not None. Otherwise
            a list of matplotlib.pyplot.axis are returned.

        """
        from ..plot.plotutil import PlotUtilities

        if not self.plottable:
            raise TypeError("Simulation level packages are not plottable")

        axes = PlotUtilities._plot_package_helper(self, **kwargs)
        return axes


class MFChildPackages:
    """
    Behind the scenes code for creating an interface to access child packages
    from a parent package.  This class is automatically constructed by the
    FloPy library and is for internal library use only.

    Parameters
    ----------
    """

    def __init__(
        self,
        model_or_sim,
        parent,
        pkg_type,
        filerecord,
        package=None,
        package_class=None,
    ):
        self._packages = []
        self._filerecord = filerecord
        if package is not None:
            self._packages.append(package)
        self._model_or_sim = model_or_sim
        self._cpparent = parent
        self._pkg_type = pkg_type
        self._package_class = package_class

    def __init_subclass__(cls):
        """Register package"""
        super().__init_subclass__()
        PackageContainer.packages_by_abbr[cls.package_abbr] = cls

    def __getattr__(self, attr):
        if (
            "_packages" in self.__dict__
            and len(self._packages) > 0
            and hasattr(self._packages[0], attr)
        ):
            item = getattr(self._packages[0], attr)
            return item
        raise AttributeError(attr)

    def __getitem__(self, k):
        if isinstance(k, int):
            if k < len(self._packages):
                return self._packages[k]
        raise ValueError(f"Package index {k} does not exist.")

    def __setattr__(self, key, value):
        if (
            key != "_packages"
            and key != "_model_or_sim"
            and key != "_cpparent"
            and key != "_inattr"
            and key != "_filerecord"
            and key != "_package_class"
            and key != "_pkg_type"
        ):
            if len(self._packages) == 0:
                raise Exception(
                    "No {} package is currently attached to package"
                    " {}. Use the initialize method to create a(n) "
                    "{} package before attempting to access its "
                    "properties.".format(
                        self._pkg_type, self._cpparent.filename, self._pkg_type
                    )
                )
            package = self._packages[0]
            setattr(package, key, value)
            return
        super().__setattr__(key, value)

    def __default_file_path_base(self, file_path, suffix=""):
        stem = os.path.split(file_path)[1]
        stem_lst = stem.split(".")
        file_name = ".".join(stem_lst[:-1])
        if len(stem_lst) > 1:
            file_ext = stem_lst[-1]
            return f"{file_name}.{file_ext}{suffix}.{self._pkg_type}"
        elif suffix != "":
            return f"{stem}.{self._pkg_type}"
        else:
            return f"{stem}.{suffix}.{self._pkg_type}"

    def __file_path_taken(self, possible_path):
        for package in self._packages:
            # Do case insensitive compare
            if package.filename.lower() == possible_path.lower():
                return True
        return False

    def next_default_file_path(self):
        possible_path = self.__default_file_path_base(self._cpparent.filename)
        suffix = 0
        while self.__file_path_taken(possible_path):
            possible_path = self.__default_file_path_base(
                self._cpparent.filename, suffix
            )
            suffix += 1
        return possible_path

    def init_package(self, package, fname, remove_packages=True):
        if remove_packages:
            # clear out existing packages
            self._remove_packages()
        elif fname is not None:
            self._remove_packages(fname)
        if fname is None:
            # build a file name
            fname = self.next_default_file_path()
            package._filename = fname
        # check file record variable
        found = False
        fr_data = self._filerecord.get_data()
        if fr_data is not None:
            for line in fr_data:
                if line[0] == fname:
                    found = True
        if not found:
            # append file record variable
            self._filerecord.append_data([(fname,)])
        # add the package to the list
        self._packages.append(package)

    def _update_filename(self, old_fname, new_fname):
        file_record = self._filerecord.get_data()
        new_file_record_data = []
        if file_record is not None:
            file_record_data = file_record[0]
            for item in file_record_data:
                base, fname = os.path.split(item)
                if fname.lower() == old_fname.lower():
                    if base:
                        new_file_record_data.append(
                            (os.path.join(base, new_fname),)
                        )
                    else:
                        new_file_record_data.append((new_fname,))
                else:
                    new_file_record_data.append((item,))
        else:
            new_file_record_data.append((new_fname,))
        self._filerecord.set_data(new_file_record_data)

    def _append_package(self, package, fname, update_frecord=True):
        if fname is None:
            # build a file name
            fname = self.next_default_file_path()
            package._filename = fname

        if update_frecord:
            # set file record variable
            file_record = self._filerecord.get_data()
            file_record_data = file_record
            new_file_record_data = []
            for item in file_record_data:
                new_file_record_data.append((item[0],))
            new_file_record_data.append((fname,))
            self._filerecord.set_data(new_file_record_data)

        for existing_pkg in self._packages:
            if existing_pkg is package:
                # do not add the same package twice
                return
        # add the package to the list
        self._packages.append(package)

    def _remove_packages(self, fname=None, only_pop_from_list=False):
        rp_list = []
        for idx, package in enumerate(self._packages):
            if fname is None or package.filename == fname:
                if not only_pop_from_list:
                    self._model_or_sim.remove_package(package)
                rp_list.append(idx)
        for idx in reversed(rp_list):
            self._packages.pop(idx)
