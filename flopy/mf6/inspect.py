from collections.abc import Callable
from typing import Optional


def get_classes(predicate: Optional[Callable] = None) -> dict[str, type]:
    import flopy.mf6.modflow as modflow
    from flopy.utils.inspect import get_classes as _get_classes

    return _get_classes(
        modflow,
        lambda cls: hasattr(cls, "dfn") and (predicate(cls) if predicate else True),
    )


def is_multi_package(cls: type) -> bool:
    if (dfn := getattr(cls, "dfn", None)) is None:
        return False
    return (
        len(dfn) > 0
        and len(dfn[0]) >= 2
        and dfn[0][1] == "multi-package"
    )


def is_solution_package(cls: type) -> bool:
    if (dfn := getattr(cls, "dfn", None)) is None:
        return False
    return (
        len(dfn) > 0
        and len(dfn[0]) >= 2
        and len(dfn[0][1]) > 0
        and dfn[0][1][0] == "solution_package"
    )


def is_sub_package(cls: type) -> bool:
    if (dfn := getattr(cls, "dfn", None)) is None:
        return False
    return (
        len(dfn) > 0
        and len(dfn[0]) >= 2
        and len(dfn[0][1]) > 0
        and dfn[0][1][0] == "subpackage"
    )


def get_multi_packages() -> dict[str, type]:
    return get_classes(is_multi_package)


def get_solution_packages() -> dict[str, type]:
    return get_classes(is_solution_package)


def get_sub_packages() -> dict[str, type]:
    return get_classes(is_sub_package)
