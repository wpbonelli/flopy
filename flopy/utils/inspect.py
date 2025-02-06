from collections.abc import Callable
import inspect


def get_classes(module: object, predicate: Callable = None) -> dict[str, type]:
    """Find classes in a module which satisfy a predicate."""
    classes = inspect.getmembers(module, inspect.isclass)
    return {name: cls for name, cls in classes if predicate(cls)}
