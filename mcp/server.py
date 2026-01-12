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

from mcp.tools import register_tools
from mcp.resources import register_resources


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
        version="0.1.0",
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


# Entry point for direct execution
if __name__ == "__main__":
    server = create_server()
    run_server(server)
