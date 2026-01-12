#!/usr/bin/env python3
"""
Local test script for the Evenflow MCP server.

This script tests the MCP tools directly without needing a transport layer.
Run with: python test_mcp_local.py
"""

import asyncio
import json
from evenflow_mcp.server import create_server


async def test_tools():
    """Test all MCP tools."""
    print("=" * 60)
    print("Evenflow MCP Server - Local Test")
    print("=" * 60)
    
    # Create server
    mcp = create_server()
    
    # Get registered tools
    tools = list(mcp._tool_manager._tools.keys())
    print(f"\n✓ Server created with {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool}")
    
    # Test 1: List locations
    print("\n" + "-" * 40)
    print("Test 1: list_locations")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["list_locations"].run({})
        print(json.dumps(result, indent=2, default=str)[:500])
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 2: Get location state
    print("\n" + "-" * 40)
    print("Test 2: get_location_state('whispering_woods')")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["get_location_state"].run({
            "location_id": "whispering_woods"
        })
        print(json.dumps(result, indent=2, default=str)[:800])
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 3: Get affordance registry
    print("\n" + "-" * 40)
    print("Test 3: get_affordance_registry")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["get_affordance_registry"].run({})
        print(json.dumps(result, indent=2, default=str)[:500])
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 4: Predict action
    print("\n" + "-" * 40)
    print("Test 4: predict_action")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["predict_action"].run({
            "actor_id": "player_1",
            "actor_tags": ["adventurer"],
            "location_id": "whispering_woods",
            "event_type": "harm.fire",
            "intensity": 0.5
        })
        print(json.dumps(result, indent=2, default=str)[:800])
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 5: Explain valuation
    print("\n" + "-" * 40)
    print("Test 5: explain_valuation")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["explain_valuation"].run({
            "location_id": "whispering_woods",
            "event_type": "harm.fire"
        })
        print(json.dumps(result, indent=2, default=str)[:500])
    except Exception as e:
        print(f"Error: {e}")
    
    # Test 6: Export world state
    print("\n" + "-" * 40)
    print("Test 6: export_world_state")
    print("-" * 40)
    try:
        result = await mcp._tool_manager._tools["export_world_state"].run({})
        export = json.loads(result) if isinstance(result, str) else result
        print(f"Exported {len(export.get('locations', []))} locations")
        print(f"Total traces: {export.get('metadata', {}).get('total_traces', 0)}")
    except Exception as e:
        print(f"Error: {e}")
    
    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_tools())
