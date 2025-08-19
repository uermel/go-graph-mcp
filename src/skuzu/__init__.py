"""skuzu package."""

__version__ = "0.1.0"

from skuzu.ontology.go_parser import GOParser
from skuzu.hierarchy.hierarchy_parser import HierarchyParser
from skuzu.cli.go_parser import cli as go_cli
from skuzu.cli.hierarchy_parser import cli as hierarchy_cli

__all__ = ["GOParser", "HierarchyParser", "go_cli", "hierarchy_cli"]