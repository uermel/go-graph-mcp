"""Command line interface for setting up MCP server configuration."""

import json
import os
import platform
import sys
from pathlib import Path
from typing import Optional

import click


def get_claude_config_path() -> Path:
    """Get the Claude Desktop configuration file path for the current platform."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        appdata = os.getenv("APPDATA")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        else:
            return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    else:  # Linux and others
        # Claude Desktop may not be officially supported on Linux, but use a reasonable default
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


@click.group()
def cli():
    """Setup MCP server configuration for Claude Desktop and ChatGPT."""
    pass


@cli.command()
@click.option(
    "--server-name",
    default="go-graph-mcp",
    help="Name for the MCP server (default: go-graph-mcp)",
)
@click.option(
    "--python-path", 
    help="Path to Python executable (defaults to current Python)",
)
@click.option(
    "--db-path",
    help="Database path (defaults to ./go_db.kz)",
)
@click.option(
    "--namespace",
    default="cellular_component",
    help="GO namespace (default: cellular_component)",
    type=click.Choice(["cellular_component", "molecular_function", "biological_process"])
)
@click.option(
    "--force-rebuild",
    is_flag=True,
    help="Force rebuild database on startup",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force overwrite existing configuration",
)
def claude_desktop(server_name: str, python_path: Optional[str], db_path: Optional[str], 
                  namespace: str, force_rebuild: bool, force: bool):
    """Setup MCP server configuration for Claude Desktop."""
    config_path = get_claude_config_path()
    
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Get Python path
    if not python_path:
        python_path = sys.executable
    
    # Load existing configuration or create new one
    config = {}
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            if not force:
                click.echo(f"Error reading existing config: {e}")
                click.echo("Use --force to overwrite or fix the configuration manually.")
                sys.exit(1)
            click.echo(f"Warning: Existing config has errors, creating new one: {e}")
    
    # Initialize mcpServers section if it doesn't exist
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Check if server already exists
    if server_name in config["mcpServers"] and not force:
        click.echo(f"Server '{server_name}' already exists in configuration.")
        click.echo("Use --force to overwrite or choose a different --server-name.")
        sys.exit(1)
    
    # Build environment variables for server configuration
    env_vars = {}
    if db_path:
        env_vars["GO_GRAPH_DB_PATH"] = db_path
    if namespace != "cellular_component":
        env_vars["GO_GRAPH_NAMESPACE"] = namespace
    if force_rebuild:
        env_vars["GO_GRAPH_FORCE_REBUILD"] = "true"
    
    # Add GO Graph MCP server configuration
    config["mcpServers"][server_name] = {
        "command": python_path,
        "args": ["-m", "go_graph_mcp.mcp.server"],
        "env": env_vars
    }
    
    # Write configuration
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        click.echo(f"✅ Successfully configured Claude Desktop MCP server!")
        click.echo(f"   Server name: {server_name}")
        click.echo(f"   Config file: {config_path}")
        click.echo(f"   Python path: {python_path}")
        if env_vars:
            click.echo("   Environment variables:")
            for key, value in env_vars.items():
                click.echo(f"     {key}: {value}")
        else:
            import tempfile
            default_temp_path = os.path.join(tempfile.gettempdir(), "go_graph_mcp_db")
            click.echo(f"   Database path: {default_temp_path} (default)")
            click.echo("   Namespace: cellular_component (default)")
        click.echo()
        click.echo("📋 Next steps:")
        click.echo("   1. Restart Claude Desktop completely")
        click.echo("   2. The GO Graph MCP tools should now be available in Claude Desktop")
        click.echo("   💡 Note: The server starts automatically when Claude Desktop connects")
        
    except OSError as e:
        click.echo(f"❌ Error writing configuration file: {e}")
        sys.exit(1)


@cli.command()
@click.option(
    "--output-file",
    help="Output file path (default: prints to stdout)",
)
@click.option(
    "--server-name",
    default="go-graph-mcp", 
    help="Name for the MCP server (default: go-graph-mcp)",
)
@click.option(
    "--python-path",
    help="Path to Python executable (defaults to current Python)",
)
def chatgpt_config(output_file: Optional[str], server_name: str, python_path: Optional[str]):
    """Generate MCP server configuration for ChatGPT."""
    # Get Python path
    if not python_path:
        python_path = sys.executable
    
    # Create configuration for ChatGPT
    config = {
        "mcpServers": {
            server_name: {
                "command": python_path,
                "args": ["-m", "go_graph_mcp.mcp.server"],
                "env": {}
            }
        }
    }
    
    config_json = json.dumps(config, indent=2)
    
    if output_file:
        try:
            with open(output_file, 'w') as f:
                f.write(config_json)
            click.echo(f"✅ ChatGPT MCP configuration written to: {output_file}")
        except OSError as e:
            click.echo(f"❌ Error writing configuration file: {e}")
            sys.exit(1)
    else:
        click.echo("📋 ChatGPT MCP Server Configuration:")
        click.echo(config_json)
        click.echo()
        click.echo("📝 Copy this configuration to your ChatGPT MCP settings.")


@cli.command()
def status():
    """Check MCP server configuration status."""
    config_path = get_claude_config_path()
    
    click.echo(f"🔍 MCP Configuration Status")
    click.echo(f"   Platform: {platform.system()}")
    click.echo(f"   Config path: {config_path}")
    click.echo(f"   Config exists: {'✅ Yes' if config_path.exists() else '❌ No'}")
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            mcp_servers = config.get("mcpServers", {})
            click.echo(f"   MCP servers configured: {len(mcp_servers)}")
            
            # Check for GO Graph MCP server
            go_graph_servers = [name for name in mcp_servers.keys() if "go-graph" in name.lower()]
            if go_graph_servers:
                click.echo(f"   ✅ GO Graph MCP servers found: {', '.join(go_graph_servers)}")
                for server_name in go_graph_servers:
                    server_config = mcp_servers[server_name]
                    click.echo(f"      - {server_name}: {server_config.get('command', 'unknown command')}")
            else:
                click.echo(f"   ❌ No GO Graph MCP servers found")
                
        except (json.JSONDecodeError, OSError) as e:
            click.echo(f"   ❌ Error reading config: {e}")
    
    click.echo()
    click.echo("💡 To set up MCP server:")
    click.echo("   go_graph_setup claude-desktop")


@cli.command()
@click.option(
    "--server-name",
    help="Name of the MCP server to remove",
    required=True,
)
@click.option(
    "--force",
    is_flag=True,
    help="Force removal without confirmation",
)
def remove(server_name: str, force: bool):
    """Remove MCP server configuration."""
    config_path = get_claude_config_path()
    
    if not config_path.exists():
        click.echo("❌ No Claude Desktop configuration found.")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        click.echo(f"❌ Error reading configuration: {e}")
        sys.exit(1)
    
    mcp_servers = config.get("mcpServers", {})
    if server_name not in mcp_servers:
        click.echo(f"❌ Server '{server_name}' not found in configuration.")
        sys.exit(1)
    
    if not force:
        click.confirm(f"Remove MCP server '{server_name}'?", abort=True)
    
    # Remove server
    del mcp_servers[server_name]
    
    # Write updated configuration
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        click.echo(f"✅ Successfully removed MCP server '{server_name}'")
        click.echo("   Restart Claude Desktop to apply changes.")
        
    except OSError as e:
        click.echo(f"❌ Error writing configuration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    cli()