from dataclasses import dataclass
from typing import (
    Iterator,
    List,
    NamedTuple,
    Optional,
)

from flopy.mf6.utils.codegen.dfn import Dfn, Vars
from flopy.mf6.utils.codegen.renderable import renderable
from flopy.mf6.utils.codegen.shim import SHIM


@renderable(**SHIM)
@dataclass
class Context:
    """
    An input context. Each of these is specified by a definition file
    and becomes a generated class. A definition file may specify more
    than one input context (e.g. model DFNs yield a model class and a
    package class).

    Notes
    -----
    A context minimally consists of a name and a map of variables.

    The context class may inherit from a base class, and may specify
    a parent context within which it can be created (the parent then
    becomes the first `__init__` method parameter).

    The context class may reference other contexts via foreign key
    relations held by its variables, and may itself be referenced.

    """

    class Name(NamedTuple):
        """
        Uniquely identifies an input context. The name
        consists of a left term and optional right term.

        Notes
        -----
        A single definition may be associated with one or more
        contexts. For instance, a model DFN file will produce
        both a namefile package class and a model class.

        From the context name several other things are derived:

        - a description of the context
        - the input context class' name
        - the template the context will populate
        - the base class the context inherits from
        - the name of the source file the context is in
        - the name of the parent parameter in the context
        class' `__init__` method, if it can have a parent

        """

        component: str
        subcomponent: Optional[str]

        @property
        def title(self) -> str:
            """
            The input context's unique title. This is not
            identical to `f"{l}{r}` in some cases, but it
            remains unique. The title is substituted into
            the file name and class name.
            """
            comp, sub = self
            if self == ("sim", "nam"):
                return "simulation"
            if comp is None:
                return sub
            if sub is None:
                return comp
            if comp == "sim":
                return sub
            if comp in ["sln", "exg"]:
                return sub
            return comp + sub

        @property
        def base(self) -> str:
            """Base class from which the input context should inherit."""
            _, sub = self
            if self == ("sim", "nam"):
                return "MFSimulationBase"
            if sub is None:
                return "MFModel"
            return "MFPackage"

        @property
        def target(self) -> str:
            """The source file name to generate."""
            return f"mf{self.title}.py"

        @property
        def template(self) -> str:
            """The template file to use."""
            if self.base == "MFSimulationBase":
                return "simulation.py.jinja"
            elif self.base == "MFModel":
                return "model.py.jinja"
            elif self.base == "MFPackage":
                if self.component == "exg":
                    return "exchange.py.jinja"
                return "package.py.jinja"

        @property
        def description(self) -> str:
            """A description of the input context."""
            comp, sub = self
            title = self.title.title()
            if self.base == "MFPackage":
                return f"Modflow{title} defines a {sub.upper()} package."
            elif self.base == "MFModel":
                return f"Modflow{title} defines a {comp.upper()} model."
            elif self.base == "MFSimulationBase":
                return (
                    "MFSimulation is used to load, build, and/or save a MODFLOW 6 simulation."
                    " A MFSimulation object must be created before creating any of the MODFLOW"
                    " 6 model objects."
                )

        @staticmethod
        def from_dfn(dfn: Dfn) -> List["Context.Name"]:
            """
            Returns a list of context names this definition produces.

            Notes
            -----
            An input definition may produce one or more input contexts.

            Model definition files produce both a model class context and
            a model namefile package context. The same goes for simulation
            definition files. All other definition files produce a single
            context.
            """
            if dfn.name.subcomponent == "nam":
                if dfn.name.component == "sim":
                    return [
                        Context.Name(None, dfn.name.subcomponent),  # nam pkg
                        Context.Name(*dfn.name),  # simulation
                    ]
                else:
                    return [
                        Context.Name(*dfn.name),  # nam pkg
                        Context.Name(dfn.name.component, None),  # model
                    ]
            elif (dfn.name.component, dfn.name.subcomponent) in [
                ("gwf", "mvr"),
                ("gwf", "gnc"),
                ("gwt", "mvt"),
            ]:
                return [
                    Context.Name(*dfn.name),
                    Context.Name(None, dfn.name.subcomponent),
                ]
            return [Context.Name(*dfn.name)]

    name: Name
    vars: Vars
    base: Optional[type] = None
    description: Optional[str] = None

    @classmethod
    def from_dfn(cls, dfn: Dfn) -> Iterator["Context"]:
        """
        Extract context class descriptor(s) from an input definition.
        These are structured representations of input context classes.
        Each input definition yields one or more input contexts.
        """
        for name in Context.Name.from_dfn(dfn):
            yield Context(
                name=name,
                vars=dfn.data,
                base=name.base,
                description=name.description,
            )
