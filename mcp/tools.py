"""
MCP tool definitions for Evenflow.

Each tool is a function that can be invoked by LLM clients via MCP.
Tools provide read and analysis capabilities for the game world.
"""

from typing import Any, Dict, List, Optional
from mcp.server.fastmcp import FastMCP

from mcp.schemas import (
    LocationQuery,
    TraceQuery,
    ActionPrediction,
    DecayChannel,
    to_dict,
)
from mcp.world_adapter import get_adapter


def register_tools(mcp: FastMCP) -> None:
    """Register all Evenflow tools with the MCP server."""
    
    @mcp.tool()
    def get_location_state(
        location_id: str,
        include_traces: bool = True,
        include_affordances: bool = True,
    ) -> Dict[str, Any]:
        """
        Get the current state of a location including affinity traces and affordances.
        
        Args:
            location_id: The unique identifier of the location
            include_traces: Whether to include affinity trace records
            include_affordances: Whether to include affordance configurations
            
        Returns:
            Complete location state snapshot with name, description, valuation profile,
            saturation levels, traces (with decay applied), and affordance configs.
        """
        adapter = get_adapter()
        query = LocationQuery(
            location_id=location_id,
            include_traces=include_traces,
            include_affordances=include_affordances,
        )
        result = adapter.get_location_state(query)
        if result is None:
            return {"error": f"Location '{location_id}' not found"}
        return to_dict(result)
    
    @mcp.tool()
    def list_locations() -> List[str]:
        """
        List all available location IDs in the world.
        
        Returns:
            List of location identifiers that can be queried.
        """
        adapter = get_adapter()
        return adapter.list_locations()
    
    @mcp.tool()
    def compute_affinity(
        location_id: str,
        actor_id: str,
        actor_tags: List[str],
    ) -> Dict[str, Any]:
        """
        Compute the affinity score for an actor at a specific location.
        
        The affinity score determines how the location "feels" about the actor,
        based on their personal history, group affiliations, and recent behavior.
        
        Args:
            location_id: The location to check
            actor_id: The actor's unique identifier
            actor_tags: The actor's categorical tags (e.g., ["merchant", "human"])
            
        Returns:
            Affinity score breakdown with total, per-channel scores, and threshold label
            (hostile/wary/neutral/warm/favorable).
        """
        adapter = get_adapter()
        result = adapter.compute_affinity_for_actor(
            location_id=location_id,
            actor_id=actor_id,
            actor_tags=set(actor_tags),
        )
        if result is None:
            return {"error": f"Location '{location_id}' not found"}
        return to_dict(result)
    
    @mcp.tool()
    def query_traces(
        location_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        event_type: Optional[str] = None,
        channel: Optional[str] = None,
        min_intensity: float = 0.0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query affinity traces across the world.
        
        Traces record the memory of actions. They decay over time at different rates
        depending on their channel (personal, group, behavior).
        
        Args:
            location_id: Filter by location (optional)
            actor_id: Filter by actor (optional, personal channel only)
            event_type: Filter by event type like "harm.fire" (optional)
            channel: Filter by channel: "personal", "group", or "behavior" (optional)
            min_intensity: Minimum decayed intensity threshold (default 0.0)
            limit: Maximum number of results (default 100)
            
        Returns:
            List of matching traces sorted by decayed intensity.
        """
        adapter = get_adapter()
        channel_enum = None
        if channel:
            try:
                channel_enum = DecayChannel(channel)
            except ValueError:
                return [{"error": f"Invalid channel '{channel}'. Use: personal, group, behavior"}]
        
        query = TraceQuery(
            location_id=location_id,
            actor_id=actor_id,
            event_type=event_type,
            channel=channel_enum,
            min_intensity=min_intensity,
            limit=limit,
        )
        results = adapter.query_traces(query)
        return [to_dict(t) for t in results]
    
    @mcp.tool()
    def predict_action(
        actor_id: str,
        actor_tags: List[str],
        location_id: str,
        event_type: str,
        intensity: float,
    ) -> Dict[str, Any]:
        """
        Predict the consequences of an action without actually performing it.
        
        Simulates what would happen if the actor performed the specified action,
        showing the change in affinity and which affordances might trigger.
        
        Args:
            actor_id: The actor's unique identifier
            actor_tags: The actor's categorical tags
            location_id: Where the action would occur
            event_type: The type of action (e.g., "harm.fire", "offer.gift")
            intensity: Action intensity from 0.0 to 1.0
            
        Returns:
            Predicted consequence including before/after affinity, triggered
            affordances, and narrative hints.
        """
        adapter = get_adapter()
        prediction = ActionPrediction(
            actor_id=actor_id,
            actor_tags=actor_tags,
            location_id=location_id,
            event_type=event_type,
            intensity=intensity,
        )
        result = adapter.predict_action_consequence(prediction)
        if result is None:
            return {"error": f"Location '{location_id}' not found"}
        return to_dict(result)
    
    @mcp.tool()
    def get_world_history(
        location_id: str,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get a summary of recent world history for folklore generation.
        
        Analyzes recent traces to identify dominant events, notable actors,
        and the overall "mood" of the location. Provides folklore seeds
        that can be used by LLMs to generate rumor and legend.
        
        Args:
            location_id: The location to summarize
            time_window_days: How far back to look (default 30 days)
            
        Returns:
            World history summary with dominant events, notable actors,
            mood classification, and folklore seeds.
        """
        adapter = get_adapter()
        result = adapter.get_world_history_summary(
            location_id=location_id,
            time_window_days=time_window_days,
        )
        if result is None:
            return {"error": f"Location '{location_id}' not found"}
        return to_dict(result)
    
    @mcp.tool()
    def get_affordance_registry() -> Dict[str, bool]:
        """
        Get the global affordance registry showing which affordances are enabled.
        
        Affordances are the mechanical effects that can trigger based on affinity.
        This tool shows the admin-configurable on/off state for each type.
        
        Returns:
            Dictionary mapping affordance type to enabled status.
        """
        adapter = get_adapter()
        return adapter.get_affordance_registry()
    
    @mcp.tool()
    def export_world_state() -> Dict[str, Any]:
        """
        Export the complete world state as a JSON snapshot.
        
        Useful for backup, analysis, or debugging. Includes all locations
        with their traces, affordances, and current state.
        
        Returns:
            Complete world state as nested dictionary.
        """
        adapter = get_adapter()
        return adapter.export_world_state()
    
    @mcp.tool()
    def explain_valuation(
        location_id: str,
        event_type: str,
    ) -> Dict[str, Any]:
        """
        Explain how a location values a specific event type.
        
        Shows the valuation weight for an event, including category fallback
        logic if an exact match isn't found.
        
        Args:
            location_id: The location to check
            event_type: The event type like "harm.fire"
            
        Returns:
            Valuation explanation with weight and fallback chain.
        """
        adapter = get_adapter()
        location = adapter.get_location(location_id)
        if location is None:
            return {"error": f"Location '{location_id}' not found"}
        
        profile = location.valuation_profile
        
        # Check exact match
        if event_type in profile:
            return {
                "event_type": event_type,
                "weight": profile[event_type],
                "match_type": "exact",
                "explanation": f"Location has explicit valuation for '{event_type}'",
            }
        
        # Check category fallback
        category = event_type.split('.')[0]
        if category in profile:
            return {
                "event_type": event_type,
                "weight": profile[category],
                "match_type": "category",
                "category": category,
                "explanation": f"No exact match; using category '{category}' valuation",
            }
        
        # No match
        return {
            "event_type": event_type,
            "weight": 0.0,
            "match_type": "default",
            "explanation": "No valuation found; neutral (0.0) applied",
        }
