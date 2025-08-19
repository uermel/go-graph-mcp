"""go_graph_mcp package."""

__version__ = "0.1.0"

from go_graph_mcp.ontology.go_parser import GOParser
from go_graph_mcp.cli.go_parser import cli as go_cli

__all__ = ["GOParser", "go_cli",]