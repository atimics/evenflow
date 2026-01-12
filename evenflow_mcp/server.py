"""
Main MCP server for Evenflow MUD.

This server exposes the Evenflow affinity system via the Model Context Protocol,
enabling LLM clients to query world state, analyze mechanics, and generate
folklore about the game world.

Usage:
    # Run directly (stdio transport)
    python -m mcp.server
    
    # Or import and customize
    from mcp.server import create_server, run_server
    mcp = create_server()
    run_server(mcp)
"""

import os
import sys
from typing import Optional

# Add project root to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from mcp.server.fastmcp import FastMCP

from evenflow_mcp.tools import register_tools
from evenflow_mcp.resources import register_resources


def create_server(name: str = "evenflow-mcp") -> FastMCP:
    """
    Create and configure the Evenflow MCP server.
    
    Args:
        name: Server name for identification
        
    Returns:
        Configured FastMCP server instance
    """
    mcp = FastMCP(
        name=name,
        instructions="Evenflow MUD server exposing affinity system via MCP. Query world state, analyze mechanics, and explore the game world.",
    )
    
    # Register tools and resources
    register_tools(mcp)
    register_resources(mcp)
    
    return mcp


def run_server(
    mcp: Optional[FastMCP] = None,
    transport: str = "stdio",
) -> None:
    """
    Run the MCP server.
    
    Args:
        mcp: Server instance (creates new if None)
        transport: Transport type ("stdio" or "sse")
    """
    if mcp is None:
        mcp = create_server()
    
    if transport == "stdio":
        mcp.run()
    elif transport == "sse":
        # For HTTP/SSE transport (AWS Lambda compatible)
        mcp.run(transport="sse")
    else:
        raise ValueError(f"Unknown transport: {transport}")


# Global server instance for mcp dev command
mcp = create_server()


# Entry point for direct execution
if __name__ == "__main__":
    run_server(mcp)
