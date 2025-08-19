"""Command line interface for skuzu."""

import os
import sys
import tempfile
import traceback
from pathlib import Path
from urllib.parse import urlparse

import click
import requests

from go_graph_mcp.ontology.go_parser import GOParser


@click.group()
def cli():
    """skuzu - Tools for bioinformatics with KuzuDB."""
    pass


@cli.command(name="parse-go")
@click.option(
    "--input",
    "-i",
    required=False,
    type=click.Path(exists=True, file_okay=True, readable=True),
    help="Path to the GO JSON file (optional - will download from OBO if not provided)",
)
@click.option(
    "--output",
    "-o",
    required=True,
    type=click.Path(),
    help="Directory where to save the KuzuDB database",
)
@click.option(
    "--namespace",
    "-n",
    default="cellular_component",
    type=click.Choice(["cellular_component", "molecular_function", "biological_process"]),
    help="GO namespace to filter for (default: cellular_component)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force overwrite of existing database",
)
@click.option(
    "--debug",
    "-d",
    is_flag=True,
    help="Enable debug output",
)
def parse_go(input, output, namespace, verbose, force, debug):
    """Parse Gene Ontology data into a KuzuDB graph database.
    
    This command parses GO data from a JSON file and loads it into a KuzuDB graph database.
    By default, it only processes terms in the cellular_component namespace.
    If no input file is provided, it will automatically download the latest GO data.
    """
    # Handle input - either provided file or download
    if input:
        input_path = os.path.abspath(input)
        temp_file = None
    else:
        # Download GO data from OBO library
        input_path, temp_file = _download_go_data(verbose)
    
    output_path = os.path.abspath(output)
    
    click.echo(f"Processing GO data from {input_path}")
    click.echo(f"Saving KuzuDB to {output_path}")
    
    # Check if output directory exists
    if os.path.exists(output_path) and not force:
        click.echo(f"Error: Output directory '{output_path}' already exists. Use --force to overwrite.", err=True)
        sys.exit(1)
    
    # Initialize parser and process data
    parser = GOParser(output_path)
    
    try:
        parser.parse_go_json(input_path, namespace, debug=debug)
        click.echo(f"Successfully created KuzuDB graph database at {output_path}")
        
        # If verbose, run a quick query to show the number of terms and relationships
        if verbose:
            click.echo("\nDatabase Summary:")
            # Get term count
            result = parser.conn.execute("MATCH (n:GOTerm) RETURN count(n) as count")
            if result.has_next():
                row = result.get_next()
                click.echo(f"GO Terms: {row[0]}")
            else:
                click.echo("GO Terms: 0")
            
            # Get IS_A relationship count
            result = parser.conn.execute("MATCH ()-[r:IS_A]->() RETURN count(r) as count")
            if result.has_next():
                row = result.get_next()
                click.echo(f"IS_A Relationships: {row[0]}")
            else:
                click.echo("IS_A Relationships: 0")
            
            # Get PART_OF relationship count
            result = parser.conn.execute("MATCH ()-[r:PART_OF]->() RETURN count(r) as count")
            if result.has_next():
                row = result.get_next()
                click.echo(f"PART_OF Relationships: {row[0]}")
            else:
                click.echo("PART_OF Relationships: 0")
    except Exception as e:
        click.echo(f"Error processing GO data: {str(e)}", err=True)
        if verbose:
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)
    finally:
        if parser.conn:
            parser.close()
        # Clean up temporary file if we downloaded it
        if temp_file:
            try:
                os.unlink(temp_file)
                if verbose:
                    click.echo(f"Cleaned up temporary file: {temp_file}")
            except OSError:
                pass


def _download_go_data(verbose=False):
    """Download GO data from the OBO library.
    
    Args:
        verbose: Whether to show verbose output
        
    Returns:
        tuple: (file_path, temp_file_path) where temp_file_path needs cleanup
    """
    go_url = "https://purl.obolibrary.org/obo/go/go-basic.json"
    
    if verbose:
        click.echo(f"Downloading GO data from {go_url}")
    
    try:
        # Create a temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.json', prefix='go-basic-')
        
        # Download the data
        response = requests.get(go_url, stream=True)
        response.raise_for_status()
        
        # Write to temporary file
        with os.fdopen(temp_fd, 'wb') as temp_file:
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
        
        if verbose:
            file_size = os.path.getsize(temp_path)
            click.echo(f"Downloaded GO data ({file_size:,} bytes) to temporary file")
        
        return temp_path, temp_path
        
    except requests.exceptions.RequestException as e:
        click.echo(f"Error downloading GO data: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error creating temporary file: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli() 