"""
World adapter: bridges MCP server to Evenflow game state.

Provides read/write access to locations, artifacts, traces, and affordances.
Handles both in-memory state (for local testing) and database state (for AWS).
"""

import os
import time
import json
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field

from world.affinity.core import (
    Location,
    TraceRecord,
    AffordanceConfig,
    SaturationState,
    AffinityEvent,
)
from world.affinity.config import get_config
from world.affinity.computation import (
    compute_affinity,
    get_threshold_label,
    get_decayed_value,
    score_personal,
    score_group,
    score_behavior,
)
from world.affinity.events import log_event
from world.affinity.affordances import (
    admin_get_registry,
    is_affordance_enabled,
)

from mcp.schemas import (
    LocationState,
    LocationQuery,
    TraceInfo,
    AffordanceInfo,
    AffinityScore,
    ActionConsequence,
    ActionPrediction,
    TraceQuery,
    WorldHistorySummary,
)


class EvenflowAdapter:
    """
    Adapter between MCP server and Evenflow world state.
    
    Supports two modes:
    - In-memory: Loads YAML locations, stores state in memory (for local dev)
    - Database: Uses PostgreSQL for persistent state (for AWS deployment)
    """
    
    def __init__(self, db_url: Optional[str] = None):
        """
        Initialize the adapter.
        
        Args:
            db_url: PostgreSQL connection URL. If None, uses in-memory mode.
        """
        self.db_url = db_url
        self._locations: Dict[str, Location] = {}
        self._config = get_config()
        
        if db_url:
            self._init_database()
        else:
            self._load_yaml_locations()
    
    def _init_database(self) -> None:
        """Initialize database connection (for AWS mode)."""
        # Placeholder for database initialization
        # Will be implemented when deploying to AWS
        pass
    
    def _load_yaml_locations(self) -> None:
        """Load locations from YAML files in world/locations/."""
        locations_dir = Path(__file__).parent.parent / "world" / "locations"
        if not locations_dir.exists():
            # Fallback to relative path from workspace root
            locations_dir = Path("world/locations")
        
        for yaml_file in locations_dir.glob("*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                location = self._parse_location_yaml(data)
                self._locations[location.location_id] = location
            except Exception as e:
                print(f"Warning: Failed to load {yaml_file}: {e}")
    
    def _parse_location_yaml(self, data: Dict[str, Any]) -> Location:
        """Parse a location YAML file into a Location object."""
        # Parse affordances
        affordances = []
        for aff_data in data.get("affordances", []):
            severity = aff_data.get("severity_clamp", {})
            tells = aff_data.get("tells", {})
            affordances.append(AffordanceConfig(
                affordance_type=aff_data["type"],
                enabled=aff_data.get("enabled", True),
                mechanical_handle=aff_data.get("mechanical_handle"),
                severity_clamp_hostile=severity.get("hostile", 0.5),
                severity_clamp_favorable=severity.get("favorable", -0.3),
                cooldown_seconds=aff_data.get("cooldown_seconds", 3600),
                tells_hostile=tells.get("hostile", []),
                tells_favorable=tells.get("favorable", []),
            ))
        
        return Location(
            location_id=data["location_id"],
            name=data["name"],
            description=data.get("description", ""),
            valuation_profile=data.get("valuation_profile", {}),
            affordances=affordances,
        )
    
    # =========================================================================
    # Location Queries
    # =========================================================================
    
    def get_location(self, location_id: str) -> Optional[Location]:
        """Get a location by ID."""
        return self._locations.get(location_id)
    
    def list_locations(self) -> List[str]:
        """List all location IDs."""
        return list(self._locations.keys())
    
    def get_location_state(self, query: LocationQuery) -> Optional[LocationState]:
        """
        Get complete location state snapshot.
        
        Args:
            query: Location query parameters
            
        Returns:
            LocationState or None if not found
        """
        location = self._locations.get(query.location_id)
        if not location:
            return None
        
        now = time.time()
        traces = []
        
        if query.include_traces:
            # Personal traces
            personal_hl = self._config.half_lives.location.personal * 86400
            for (actor_id, event_type), trace in location.personal_traces.items():
                decayed = get_decayed_value(trace, personal_hl, now) if query.decay_to_now else trace.accumulated
                traces.append(TraceInfo(
                    key=f"({actor_id}, {event_type})",
                    channel="personal",
                    accumulated=trace.accumulated,
                    decayed_value=decayed,
                    last_updated=trace.last_updated,
                    event_count=trace.event_count,
                    is_scar=trace.is_scar,
                ))
            
            # Group traces
            group_hl = self._config.half_lives.location.group * 86400
            for (actor_tag, event_type), trace in location.group_traces.items():
                decayed = get_decayed_value(trace, group_hl, now) if query.decay_to_now else trace.accumulated
                traces.append(TraceInfo(
                    key=f"({actor_tag}, {event_type})",
                    channel="group",
                    accumulated=trace.accumulated,
                    decayed_value=decayed,
                    last_updated=trace.last_updated,
                    event_count=trace.event_count,
                    is_scar=trace.is_scar,
                ))
            
            # Behavior traces
            behavior_hl = self._config.half_lives.location.behavior * 86400
            for event_type, trace in location.behavior_traces.items():
                decayed = get_decayed_value(trace, behavior_hl, now) if query.decay_to_now else trace.accumulated
                traces.append(TraceInfo(
                    key=event_type,
                    channel="behavior",
                    accumulated=trace.accumulated,
                    decayed_value=decayed,
                    last_updated=trace.last_updated,
                    event_count=trace.event_count,
                    is_scar=trace.is_scar,
                ))
        
        affordances = []
        if query.include_affordances:
            for aff in location.affordances:
                cooldown_remaining = None
                cooldown_key = aff.affordance_type
                if cooldown_key in location.cooldowns:
                    remaining = location.cooldowns[cooldown_key] - now
                    cooldown_remaining = max(0, remaining)
                
                affordances.append(AffordanceInfo(
                    affordance_type=aff.affordance_type,
                    enabled=aff.enabled and is_affordance_enabled(aff.affordance_type),
                    mechanical_handle=aff.mechanical_handle,
                    severity_clamp_hostile=aff.severity_clamp_hostile,
                    severity_clamp_favorable=aff.severity_clamp_favorable,
                    cooldown_seconds=aff.cooldown_seconds,
                    cooldown_remaining=cooldown_remaining,
                    tells_hostile=aff.tells_hostile,
                    tells_favorable=aff.tells_favorable,
                ))
        
        return LocationState(
            location_id=location.location_id,
            name=location.name,
            description=location.description,
            valuation_profile=location.valuation_profile,
            saturation={
                "personal": location.saturation.personal,
                "group": location.saturation.group,
                "behavior": location.saturation.behavior,
            },
            traces=traces,
            affordances=affordances,
            last_tick=location.last_tick,
        )
    
    # =========================================================================
    # Affinity Queries
    # =========================================================================
    
    def compute_affinity_for_actor(
        self,
        location_id: str,
        actor_id: str,
        actor_tags: Set[str],
    ) -> Optional[AffinityScore]:
        """
        Compute affinity score for an actor at a location.
        
        Args:
            location_id: Location to check
            actor_id: Actor to compute affinity for
            actor_tags: Actor's categorical tags
            
        Returns:
            AffinityScore breakdown or None if location not found
        """
        location = self._locations.get(location_id)
        if not location:
            return None
        
        now = time.time()
        config = self._config
        
        # Compute channel scores
        personal_hl = config.half_lives.location.personal * 86400
        group_hl = config.half_lives.location.group * 86400
        behavior_hl = config.half_lives.location.behavior * 86400
        
        personal = score_personal(
            location.personal_traces,
            actor_id,
            personal_hl,
            location.valuation_profile,
            now,
        )
        
        group = score_group(
            location.group_traces,
            actor_tags,
            group_hl,
            location.valuation_profile,
            now,
        )
        
        behavior = score_behavior(
            location.behavior_traces,
            behavior_hl,
            location.valuation_profile,
            now,
        )
        
        # Weighted blend
        weights = config.channel_weights
        total = (
            personal * weights.personal +
            group * weights.group +
            behavior * weights.behavior
        )
        
        return AffinityScore(
            total=total,
            personal=personal,
            group=group,
            behavior=behavior,
            threshold_label=get_threshold_label(total),
        )
    
    # =========================================================================
    # Trace Queries
    # =========================================================================
    
    def query_traces(self, query: TraceQuery) -> List[TraceInfo]:
        """
        Query traces across locations.
        
        Args:
            query: Trace query parameters
            
        Returns:
            List of matching traces
        """
        results = []
        now = time.time()
        config = self._config
        
        locations = [self._locations[query.location_id]] if query.location_id else self._locations.values()
        
        for location in locations:
            # Personal traces
            if query.channel is None or query.channel.value == "personal":
                personal_hl = config.half_lives.location.personal * 86400
                for (actor_id, event_type), trace in location.personal_traces.items():
                    if query.actor_id and actor_id != query.actor_id:
                        continue
                    if query.event_type and event_type != query.event_type:
                        continue
                    decayed = get_decayed_value(trace, personal_hl, now)
                    if decayed < query.min_intensity:
                        continue
                    results.append(TraceInfo(
                        key=f"({actor_id}, {event_type})",
                        channel="personal",
                        accumulated=trace.accumulated,
                        decayed_value=decayed,
                        last_updated=trace.last_updated,
                        event_count=trace.event_count,
                        is_scar=trace.is_scar,
                    ))
            
            # Group traces
            if query.channel is None or query.channel.value == "group":
                group_hl = config.half_lives.location.group * 86400
                for (actor_tag, event_type), trace in location.group_traces.items():
                    if query.event_type and event_type != query.event_type:
                        continue
                    decayed = get_decayed_value(trace, group_hl, now)
                    if decayed < query.min_intensity:
                        continue
                    results.append(TraceInfo(
                        key=f"({actor_tag}, {event_type})",
                        channel="group",
                        accumulated=trace.accumulated,
                        decayed_value=decayed,
                        last_updated=trace.last_updated,
                        event_count=trace.event_count,
                        is_scar=trace.is_scar,
                    ))
            
            # Behavior traces
            if query.channel is None or query.channel.value == "behavior":
                behavior_hl = config.half_lives.location.behavior * 86400
                for event_type, trace in location.behavior_traces.items():
                    if query.event_type and event_type != query.event_type:
                        continue
                    decayed = get_decayed_value(trace, behavior_hl, now)
                    if decayed < query.min_intensity:
                        continue
                    results.append(TraceInfo(
                        key=event_type,
                        channel="behavior",
                        accumulated=trace.accumulated,
                        decayed_value=decayed,
                        last_updated=trace.last_updated,
                        event_count=trace.event_count,
                        is_scar=trace.is_scar,
                    ))
        
        # Sort by decayed value, limit
        results.sort(key=lambda t: t.decayed_value, reverse=True)
        return results[:query.limit]
    
    # =========================================================================
    # Action Prediction
    # =========================================================================
    
    def predict_action_consequence(
        self,
        prediction: ActionPrediction,
    ) -> Optional[ActionConsequence]:
        """
        Predict the consequence of an action without applying it.
        
        Args:
            prediction: Action parameters
            
        Returns:
            ActionConsequence with before/after affinity and triggered affordances
        """
        location = self._locations.get(prediction.location_id)
        if not location:
            return None
        
        actor_tags = set(prediction.actor_tags)
        
        # Compute affinity before
        affinity_before = self.compute_affinity_for_actor(
            prediction.location_id,
            prediction.actor_id,
            actor_tags,
        )
        
        # Create a hypothetical event
        event = AffinityEvent(
            event_type=prediction.event_type,
            actor_id=prediction.actor_id,
            actor_tags=actor_tags,
            location_id=prediction.location_id,
            intensity=prediction.intensity,
        )
        
        # Clone location and apply event
        import copy
        temp_location = copy.deepcopy(location)
        log_event(temp_location, event)
        
        # Store temporarily to compute affinity
        original = self._locations.get(prediction.location_id)
        self._locations[prediction.location_id] = temp_location
        
        affinity_after = self.compute_affinity_for_actor(
            prediction.location_id,
            prediction.actor_id,
            actor_tags,
        )
        
        # Restore original
        if original:
            self._locations[prediction.location_id] = original
        
        # Determine which affordances might trigger
        triggered = []
        narrative_hints = []
        
        if affinity_after:
            if affinity_after.threshold_label in ["hostile", "wary"]:
                for aff in location.affordances:
                    if aff.enabled:
                        triggered.append(aff.affordance_type)
                        if aff.tells_hostile:
                            narrative_hints.append(aff.tells_hostile[0])
            elif affinity_after.threshold_label in ["warm", "favorable"]:
                for aff in location.affordances:
                    if aff.enabled:
                        if aff.tells_favorable:
                            narrative_hints.append(aff.tells_favorable[0])
        
        return ActionConsequence(
            location_id=prediction.location_id,
            actor_id=prediction.actor_id,
            event_type=prediction.event_type,
            affinity_before=affinity_before,
            affinity_after=affinity_after,
            triggered_affordances=triggered,
            narrative_hints=narrative_hints,
        )
    
    # =========================================================================
    # World History / Folklore
    # =========================================================================
    
    def get_world_history_summary(
        self,
        location_id: str,
        time_window_days: int = 30,
    ) -> Optional[WorldHistorySummary]:
        """
        Generate a summary of recent world history for folklore generation.
        
        Args:
            location_id: Location to summarize
            time_window_days: How far back to look
            
        Returns:
            WorldHistorySummary with dominant events and folklore seeds
        """
        location = self._locations.get(location_id)
        if not location:
            return None
        
        now = time.time()
        cutoff = now - (time_window_days * 86400)
        
        dominant_events = []
        notable_actors = set()
        
        # Analyze personal traces
        for (actor_id, event_type), trace in location.personal_traces.items():
            if trace.last_updated >= cutoff:
                notable_actors.add(actor_id)
                dominant_events.append({
                    "event_type": event_type,
                    "actor": actor_id,
                    "intensity": trace.accumulated,
                    "count": trace.event_count,
                })
        
        # Analyze behavior traces
        behavior_summary = {}
        for event_type, trace in location.behavior_traces.items():
            if trace.last_updated >= cutoff:
                category = event_type.split('.')[0]
                behavior_summary[category] = behavior_summary.get(category, 0) + trace.accumulated
        
        # Determine mood
        harm = behavior_summary.get("harm", 0)
        offer = behavior_summary.get("offer", 0)
        create = behavior_summary.get("create", 0)
        
        if harm > 0.5:
            mood = "troubled" if harm < 1.0 else "violent"
        elif offer > 0.3 or create > 0.3:
            mood = "sacred" if offer > 0.5 else "peaceful"
        else:
            mood = "peaceful"
        
        # Generate folklore seeds
        folklore_seeds = []
        valuation = location.valuation_profile
        
        if harm > 0 and valuation.get("harm", 0) < 0:
            folklore_seeds.append(f"The {location.name.lower()} remembers those who brought harm")
        if valuation.get("harm.fire", 0) < -0.5:
            folklore_seeds.append("Fire is forbidden in these parts")
        if offer > 0:
            folklore_seeds.append("Travelers who leave offerings find easier paths")
        if create > 0:
            folklore_seeds.append("Those who plant and tend are welcomed")
        
        # Sort by intensity
        dominant_events.sort(key=lambda e: e["intensity"], reverse=True)
        
        return WorldHistorySummary(
            location_id=location_id,
            time_window_days=time_window_days,
            dominant_events=dominant_events[:10],
            notable_actors=list(notable_actors)[:10],
            mood=mood,
            folklore_seeds=folklore_seeds,
        )
    
    # =========================================================================
    # Admin / Debug
    # =========================================================================
    
    def get_affordance_registry(self) -> Dict[str, bool]:
        """Get global affordance registry state."""
        return admin_get_registry()
    
    def export_world_state(self) -> Dict[str, Any]:
        """Export complete world state as JSON-serializable dict."""
        export = {}
        for loc_id, location in self._locations.items():
            state = self.get_location_state(LocationQuery(location_id=loc_id))
            if state:
                export[loc_id] = {
                    "location_id": state.location_id,
                    "name": state.name,
                    "description": state.description,
                    "valuation_profile": state.valuation_profile,
                    "saturation": state.saturation,
                    "traces": [
                        {
                            "key": t.key,
                            "channel": t.channel,
                            "accumulated": t.accumulated,
                            "decayed_value": t.decayed_value,
                            "event_count": t.event_count,
                            "is_scar": t.is_scar,
                        }
                        for t in state.traces
                    ],
                    "affordances": [
                        {
                            "type": a.affordance_type,
                            "enabled": a.enabled,
                            "mechanical_handle": a.mechanical_handle,
                        }
                        for a in state.affordances
                    ],
                }
        return export


# Singleton adapter instance (for MCP server)
_adapter: Optional[EvenflowAdapter] = None


def get_adapter() -> EvenflowAdapter:
    """Get or create the global adapter instance."""
    global _adapter
    if _adapter is None:
        db_url = os.environ.get("DATABASE_URL")
        _adapter = EvenflowAdapter(db_url=db_url)
    return _adapter


def reset_adapter() -> None:
    """Reset the adapter (for testing)."""
    global _adapter
    _adapter = None
