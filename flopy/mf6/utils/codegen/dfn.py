from ast import literal_eval
from collections import UserDict
from enum import Enum
from os import curdir
from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    NamedTuple,
    Optional,
    Tuple,
    TypedDict,
)
from warnings import warn

import tomlkit
from boltons.dictutils import OMD
from boltons.iterutils import remap

from flopy.mf6.utils.codegen.utils import try_literal_eval, try_parse_bool

Vars = Dict[str, "Var"]
Dfns = Dict[str, "Dfn"]
Refs = Dict[str, "Ref"]


def _sub_common(common, descr) -> Optional[str]:
    if not descr:
        return None
    descr = descr.replace("\\", "")
    _, replace, tail = descr.strip().partition("REPLACE")
    if replace:
        key, _, subs = tail.strip().partition(" ")
        subs = literal_eval(subs)
        cvar = common.get(key, None)
        if cvar is None:
            warn(
                "Can't substitute description text, "
                f"common variable not found: {key}"
            )
        else:
            descr = cvar.get("description", "")
            if any(subs):
                descr = descr.replace("\\", "").replace("{#1}", subs["{#1}"])
    return descr


class Var(TypedDict):
    """A MODFLOW 6 input variable."""

    class Kind(Enum):
        Keyword = "keyword"
        Integer = "integer"
        Double = "double"
        String = "string"
        Array = "array"
        Record = "record"
        Union = "union"
        List = "list"
        Path = "path"

    name: str
    block: str
    kind: Kind
    default: Optional[Any]
    description: Optional[str]
    children: Optional[Vars]
    ref: Optional["Ref"]


class Ref(TypedDict):
    """
    A foreign-key-like reference between a file input variable
    and another input definition. This allows an input context
    to refer to another input context, by including a filepath
    variable whose name acts as a foreign key.

    This mechanism is used to represent subpackages.

    The referring context's `__init__` method is modified such
    that the variable named `val` replaces the `key` variable.
    """

    key: str
    val: str
    abbr: str
    param: str
    parent: str
    description: Optional[str]

    @classmethod
    def from_comments(cls, comments: List[str]) -> Optional["Ref"]:
        lines = {
            "subpkg": next(
                iter(
                    c
                    for c in comments
                    if isinstance(c, str) and c.startswith("# flopy subpac")
                ),
                None,
            ),
            "parent": next(
                iter(
                    c
                    for c in comments
                    if isinstance(c, str) and c.startswith("# flopy parent")
                ),
                None,
            ),
        }

        def _subpkg():
            line = lines["subpkg"]
            _, key, abbr, param, val = line.split()
            matches = [v for v in lines.values() if v["name"] == val]
            if not any(matches):
                descr = None
            else:
                if len(matches) > 1:
                    warn(f"Multiple matches for referenced variable {val}")
                match = matches[0]
                descr = match.get("description", None)

            return {
                "key": key,
                "val": val,
                "abbr": abbr,
                "param": param,
                "description": descr,
            }

        def _parent():
            line = lines["parent"]
            split = line.split()
            return split[1]

        return (
            cls(**_subpkg(), parent=_parent())
            if all(v for v in lines.values())
            else None
        )

    @classmethod
    def load(cls, f) -> Optional["Ref"]:
        lines = f.readlines()
        comments = [l for l in lines if l.startswith("#")]
        return cls.from_comments(comments)


class Dfn(UserDict):
    """
    MODFLOW 6 input definition. An input definition
    file specifies a component of an MF6 simulation,
    e.g. a model or package.
    """

    class Name(NamedTuple):
        component: str
        subcomponent: str

        @classmethod
        def parse(cls, v: str) -> "Dfn.Name":
            try:
                return cls(*v.split("-"))
            except:
                raise ValueError(f"Bad DFN name format: {v}")

    name: Optional[Name]
    subpkg: Optional[Ref]

    def __init__(
        self,
        data: Optional[Vars] = None,
        name: Optional[Name] = None,
        subpkg: Optional[Ref] = None,
    ):
        self.data = OMD(data)
        self.name = name
        self.subpkg = subpkg

    @staticmethod
    def _load_v1_internal(
        f, common: Optional[dict] = None
    ) -> Tuple[OMD, Optional[Ref]]:
        """
        Internal use only. Loads the DFN as an ordered multi-dictionary* and
        a list of string metadata. This is later parsed into more structured
        form. We also store the original representation for now so it can be
        used by the shim.

        *The point of the OMD is to handle duplicate variable names; the only
        case of this right now is 'auxiliary' which can appear in the options
        block and again as a keyword in a record in a package data variable.

        """
        var = dict()
        flat = list()
        common = common or dict()

        for line in f:
            # remove whitespace/etc from the line
            line = line.strip()

            # record context name and flopy metadata
            # attributes, skip all other comment lines
            if line.startswith("#"):
                continue

            # if we hit a newline and the parameter dict
            # is nonempty, we've reached the end of its
            # block of attributes
            if not any(line):
                if any(var):
                    flat.append((var["name"], var))
                    var = dict()
                continue

            # split the attribute's key and value and
            # store it in the parameter dictionary
            key, _, value = line.partition(" ")
            if key == "default_value":
                key = "default"
            var[key] = value

            # make substitutions from common variable definitions,
            # remove backslashes, TODO: generate/insert citations.
            descr = var.get("description", None)
            if descr:
                var["description"] = _sub_common(common, descr)

        # add the final parameter
        if any(var):
            flat.append((var["name"], var))

        # load subpkg ref if any
        f.seek(0)
        ref = Ref.load(f)

        return OMD(flat), ref

    @classmethod
    def _load_v1(
        cls,
        f,
        name: Optional[Name] = None,
        refs: Optional[Dfns] = None,
        **kwargs,
    ) -> "Dfn":
        """Load an input definition."""

        refs = refs or dict()
        flat, subpkg = Dfn._load_v1_internal(f, **kwargs)

        def _map(var: Dict[str, Any]) -> Tuple[str, Var]:
            var = {k: try_parse_bool(v) for k, v in var.items()}

            _name = var["name"]
            _type = var.get("type", None)
            block = var.get("block", None)
            shape = var.get("shape", None)
            shape = None if shape == "" else shape
            default = var.get("default", None)
            default if _type == "string" else try_literal_eval(default)
            description = var.get("description", "")
            children = dict()
            ref = refs.get(_name, None)

            def _fields(record_name: str) -> Vars:
                """Recursively load/convert a record's fields."""
                record = next(iter(flat.getlist(record_name)), None)
                names = _type.split()[1:]
                fields = dict(
                    [
                        _map(v)
                        for v in flat.values(multi=True)
                        if v["name"] in names
                        and not v["type"].startswith("record")
                        and v.get("in_record", False)
                    ]
                )

                # if the record represents a file...
                if "file" in _name:
                    # set the variable's kind
                    n = list(fields.keys())[0]
                    path_field = fields[n]
                    path_field["kind"] = Var.Kind.Path
                    fields[n] = path_field

                # if tagged, remove the leading keyword
                elif record.get("tagged", False):
                    keyword = next(iter(fields), None)
                    if keyword:
                        fields.pop(keyword)

                return fields

            # list, child is the item type
            if _type.startswith("recarray"):
                # make sure columns are defined
                names = _type.split()[1:]
                n_names = len(names)
                if n_names < 1:
                    raise ValueError(f"Missing recarray definition: {_type}")

                # list input can have records or unions as rows.
                # lists which have a consistent record type are
                # regular, inconsistent record types irregular.

                # regular tabular/columnar data (1 record type) can be
                # defined with a nested record (i.e. explicit) or with
                # fields directly inside the recarray (implicit). list
                # data for unions/keystrings necessarily comes nested.

                is_explicit_record = n_names == 1 and flat[names[0]][
                    "type"
                ].startswith("record")

                def _is_implicit_scalar_record():
                    # if the record is defined implicitly and it has
                    # only scalar fields
                    types = [
                        v["type"]
                        for v in flat.values(multi=True)
                        if v["name"] in names and v.get("in_record", False)
                    ]
                    return all(
                        t
                        in ["keyword", "integer", "double precision", "string"]
                        for t in types
                    )

                if is_explicit_record:
                    record = next(iter(flat.getlist(names[0])), None)
                    children = dict([_map(record)])
                    kind = Var.Kind.Record
                elif _is_implicit_scalar_record():
                    fields = _fields(_name)
                    children = {
                        _name: Var(
                            name=_name,
                            block=block,
                            kind=Var.Kind.Record,
                            children=fields,
                            description=description,
                        )
                    }
                    kind = Var.Kind.Record
                else:
                    # implicit complex record (i.e. some fields are records or unions)
                    fields = dict(
                        [
                            _map(v)
                            for v in flat.values(multi=True)
                            if v["name"] in names and v.get("in_record", False)
                        ]
                    )
                    first = list(fields.values())[0]
                    single = len(fields) == 1
                    name_ = first["name"] if single else _name
                    children = {
                        name_: Var(
                            name=name_,
                            block=block,
                            kind=Var.Kind.Record,
                            children=first["children"] if single else fields,
                            description=description,
                        )
                    }
                    kind = Var.Kind.Record

            # union (product), children are choices
            elif _type.startswith("keystring"):
                names = _type.split()[1:]
                children = dict(
                    [
                        _map(v)
                        for v in flat.values(multi=True)
                        if v["name"] in names and v.get("in_record", False)
                    ]
                )
                kind = Var.Kind.Union

            # record (sum), children are fields
            elif _type.startswith("record"):
                children = _fields(_name)
                kind = Var.Kind.Record

            # at this point, if it has a shape, it's an array
            elif shape is not None:
                if _type not in [
                    "keyword",
                    "integer",
                    "double precision",
                    "string",
                ]:
                    raise TypeError(f"Unsupported array type: {_type}")
                kind = Var.Kind.Array

            # finally scalars
            else:
                kind = Var.Kind[_type.split()[0].title()]

            return _name, Var(
                name=_name,
                block=block,
                kind=kind.value,
                default=default,
                description=description,
                children=children,
                ref=ref,
            )

        vars_ = dict(
            [
                _map(var)
                for var in flat.values(multi=True)
                if not var.get("in_record", False)
            ]
        )

        return cls(vars_, name, subpkg)

    @classmethod
    def _load_v2(
        cls,
        f,
        name: Optional[Name] = None,
        refs: Optional[Dfns] = None,
        **kwargs,
    ) -> "Dfn":
        def _load_vars(data):
            vars_ = data["vars"]
            common = kwargs.get("common", None)
            if common:
                vars_ = {
                    name: {
                        "description": _sub_common(
                            common, var.get("description", None)
                        )
                        ** var
                    }
                    for name, var in vars_.items()
                }

        def _load_refs(vars_):
            return filter(None, [refs.get(k, None) for k in vars_.keys()])

        data = tomlkit.load(f)
        vars_ = _load_vars(data)
        refs_ = _load_refs(vars_)
        subpkg = data["subpkg"]
        return cls(vars_, name, refs_, subpkg)

    @classmethod
    def load(
        cls,
        f,
        name: Optional[Name] = None,
        refs: Optional[Dfns] = None,
        version: int = 1,
        **kwargs,
    ) -> "Dfn":
        if version == 1:
            return cls._load_v1(f, name, refs, **kwargs)
        elif version == 2:
            return cls._load_v2(f, name, refs, **kwargs)
        else:
            raise ValueError(f"Unsupported DFN file version {version}")

    @classmethod
    def _load_all_v1(cls, dfndir: Path) -> Dict[str, "Dfn"]:
        # find definition files
        paths = [
            p
            for p in dfndir.glob("*.dfn")
            if p.stem not in ["common", "flopy"]
        ]

        # try to load common variables
        common_path = dfndir / "common.dfn"
        if not common_path.is_file:
            common = None
        else:
            with open(common_path, "r") as f:
                common, _ = Dfn._load_v1_internal(f)

        # load subpackage references first
        refs: Refs = {}
        for path in paths:
            name = Dfn.Name(*path.stem.split("-"))
            with open(path) as f:
                dfn = Dfn.load(f, name=name, common=common)
                ref = Ref.load(f)
                if ref:
                    refs[ref["key"]] = ref

        # load all the input definitions
        dfns: Dfns = {}
        for path in paths:
            name = Dfn.Name(*path.stem.split("-"))
            with open(path) as f:
                dfn = Dfn.load(f, name=name, refs=refs, common=common)
                dfns[name] = dfn

        return dfns

    @classmethod
    def _load_all_v2(cls, dfndir: Path) -> Dict[str, "Dfn"]:
        # find definition files
        paths = [
            p
            for p in dfndir.glob("*.toml")
            if p.stem not in ["common", "flopy"]
        ]

        # try to load common variables
        common_path = dfndir / "common.toml"
        if not common_path.is_file:
            common = None
        else:
            with open(common_path, "r") as f:
                common = Dfn._load_v2(f)

        # load all the input definitions
        dfns: Dfns = {}
        for path in paths:
            name = Dfn.Name(*path.stem.split("-"))
            with open(path) as f:
                dfn = Dfn.load(f, name=name, version=2, common=common)
                dfns[name] = dfn

        return dfns

    @classmethod
    def load_all(cls, dfndir: Path, version: int = 1) -> Dict[str, "Dfn"]:
        if version == 1:
            return cls._load_all_v1(dfndir)
        elif version == 2:
            return cls._load_all_v2(dfndir)
        else:
            raise ValueError(f"Unsupported DFN file version {version}")


if __name__ == "__main__":
    """Convert DFN files to TOML (or JSON or YAML)."""

    import argparse

    mf6_path = Path(__file__).parents[2]
    dfn_path = mf6_path / "data" / "dfn"

    parser = argparse.ArgumentParser(
        description="Convert DFN files to TOML (or JSON or YAML)."
    )
    parser.add_argument(
        "--dfndir",
        type=str,
        default=dfn_path,
        help="Directory containing DFN files.",
    )
    parser.add_argument(
        "--outdir",
        default=curdir,
        help="Output directory.",
    )

    args = parser.parse_args()
    dfndir = args.dfndir
    outdir = args.outdir
    for dfn in Dfn.load_all(dfndir).values():
        with open(Path(outdir) / f"{'-'.join(dfn.name)}.toml", "w") as f:
            tomlkit.dump(dfn, f)
