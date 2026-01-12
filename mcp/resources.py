"""
MCP resource definitions for Evenflow.

Resources provide read-only access to game data in a URI-addressable format.
LLM clients can subscribe to resources for updates.
"""

from typing import Any, Dict
from mcp.server.fastmcp import FastMCP

from mcp.schemas import LocationQuery, to_dict
from mcp.world_adapter import get_adapter


def register_resources(mcp: FastMCP) -> None:
    """Register all Evenflow resources with the MCP server."""
    
    @mcp.resource("location://{location_id}")
    def get_location_resource(location_id: str) -> str:
        """
        Get a location's complete state as a resource.
        
        URI format: location://whispering_woods
        
        Returns JSON representation of location state including name,
        description, valuation profile, saturation, traces, and affordances.
        """
        adapter = get_adapter()
        query = LocationQuery(location_id=location_id)
        result = adapter.get_location_state(query)
        
        if result is None:
            return f'{{"error": "Location \'{location_id}\' not found"}}'
        
        import json
        return json.dumps(to_dict(result), indent=2)
    
    @mcp.resource("affordance://registry")
    def get_affordance_registry_resource() -> str:
        """
        Get the global affordance registry as a resource.
        
        URI format: affordance://registry
        
        Returns JSON mapping of affordance types to their enabled status.
        """
        adapter = get_adapter()
        registry = adapter.get_affordance_registry()
        
        import json
        return json.dumps(registry, indent=2)
    
    @mcp.resource("world://state")
    def get_world_state_resource() -> str:
        """
        Get complete world state export as a resource.
        
        URI format: world://state
        
        Returns JSON snapshot of the entire world including all locations,
        traces, and affordances.
        """
        adapter = get_adapter()
        state = adapter.export_world_state()
        
        import json
        return json.dumps(state, indent=2)
    
    @mcp.resource("config://affinity")
    def get_config_resource() -> str:
        """
        Get the affinity system configuration as a resource.
        
        URI format: config://affinity
        
        Returns JSON representation of half-lives, channel weights,
        saturation capacity, and other system parameters.
        """
        from world.affinity.config import get_config
        config = get_config()
        
        config_dict = {
            "half_lives": {
                "location": {
                    "personal": config.half_lives.location.personal,
                    "group": config.half_lives.location.group,
                    "behavior": config.half_lives.location.behavior,
                },
                "artifact": {
                    "personal": config.half_lives.artifact.personal,
                    "group": config.half_lives.artifact.group,
                    "behavior": config.half_lives.artifact.behavior,
                },
                "npc": {
                    "personal": config.half_lives.npc.personal,
                    "group": config.half_lives.npc.group,
                    "behavior": config.half_lives.npc.behavior,
                },
            },
            "channel_weights": {
                "personal": config.channel_weights.personal,
                "group": config.channel_weights.group,
                "behavior": config.channel_weights.behavior,
            },
            "saturation_capacity": {
                "personal": config.saturation_capacity.personal,
                "group": config.saturation_capacity.group,
                "behavior": config.saturation_capacity.behavior,
            },
            "world_tick_interval": config.world_tick_interval,
            "affinity_scale": config.affinity_scale,
        }
        
        import json
        return json.dumps(config_dict, indent=2)
