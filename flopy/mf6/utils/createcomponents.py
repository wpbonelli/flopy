"""
Generate components from templates given DFN specs.
"""

from jinja2 import Environment, PackageLoader, Template


env = Environment(loader=PackageLoader("flopy", "mf6/templates"))

def create_components():
    pass


if __name__ == "__main__":
    create_components()