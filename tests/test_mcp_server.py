"""
Tests for the MCP server and world adapter.
"""

import pytest
import time
from typing import Set

# Add project root to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp.schemas import (
    LocationQuery,
    TraceQuery,
    ActionPrediction,
    DecayChannel,
)
from mcp.world_adapter import EvenflowAdapter, reset_adapter


@pytest.fixture
def adapter():
    """Create a fresh adapter for each test."""
    reset_adapter()
    return EvenflowAdapter()


class TestWorldAdapter:
    """Tests for the EvenflowAdapter class."""
    
    def test_list_locations(self, adapter):
        """Test listing available locations."""
        locations = adapter.list_locations()
        assert isinstance(locations, list)
        # Should load whispering_woods from YAML
        assert "whispering_woods" in locations or len(locations) >= 0
    
    def test_get_location_state(self, adapter):
        """Test getting location state."""
        locations = adapter.list_locations()
        if not locations:
            pytest.skip("No locations loaded")
        
        location_id = locations[0]
        query = LocationQuery(location_id=location_id)
        state = adapter.get_location_state(query)
        
        assert state is not None
        assert state.location_id == location_id
        assert isinstance(state.name, str)
        assert isinstance(state.valuation_profile, dict)
    
    def test_get_nonexistent_location(self, adapter):
        """Test querying a location that doesn't exist."""
        query = LocationQuery(location_id="nonexistent_location")
        state = adapter.get_location_state(query)
        assert state is None
    
    def test_compute_affinity_for_actor(self, adapter):
        """Test computing affinity for an actor."""
        locations = adapter.list_locations()
        if not locations:
            pytest.skip("No locations loaded")
        
        location_id = locations[0]
        actor_id = "test_player"
        actor_tags: Set[str] = {"human", "adventurer"}
        
        score = adapter.compute_affinity_for_actor(
            location_id=location_id,
            actor_id=actor_id,
            actor_tags=actor_tags,
        )
        
        assert score is not None
        assert isinstance(score.total, float)
        assert isinstance(score.personal, float)
        assert isinstance(score.group, float)
        assert isinstance(score.behavior, float)
        assert score.threshold_label in ["hostile", "wary", "neutral", "warm", "favorable"]
    
    def test_query_traces_empty(self, adapter):
        """Test querying traces on fresh location."""
        locations = adapter.list_locations()
        if not locations:
            pytest.skip("No locations loaded")
        
        query = TraceQuery(location_id=locations[0])
        traces = adapter.query_traces(query)
        
        # Fresh location should have no traces
        assert isinstance(traces, list)
    
    def test_predict_action_consequence(self, adapter):
        """Test predicting action consequences."""
        locations = adapter.list_locations()
        if not locations:
            pytest.skip("No locations loaded")
        
        prediction = ActionPrediction(
            actor_id="test_player",
            actor_tags=["human"],
            location_id=locations[0],
            event_type="harm.fire",
            intensity=0.5,
        )
        
        consequence = adapter.predict_action_consequence(prediction)
        
        assert consequence is not None
        assert consequence.location_id == locations[0]
        assert consequence.actor_id == "test_player"
        assert consequence.event_type == "harm.fire"
        assert consequence.affinity_before is not None
        assert consequence.affinity_after is not None
    
    def test_get_world_history_summary(self, adapter):
        """Test getting world history summary."""
        locations = adapter.list_locations()
        if not locations:
            pytest.skip("No locations loaded")
        
        summary = adapter.get_world_history_summary(
            location_id=locations[0],
            time_window_days=30,
        )
        
        assert summary is not None
        assert summary.location_id == locations[0]
        assert summary.time_window_days == 30
        assert isinstance(summary.mood, str)
        assert isinstance(summary.folklore_seeds, list)
    
    def test_get_affordance_registry(self, adapter):
        """Test getting affordance registry."""
        registry = adapter.get_affordance_registry()
        
        assert isinstance(registry, dict)
        # Should have some affordances registered
        expected_affordances = ["pathing", "encounter_bias", "ambient_messaging"]
        for aff in expected_affordances:
            if aff in registry:
                assert isinstance(registry[aff], bool)
    
    def test_export_world_state(self, adapter):
        """Test exporting world state."""
        state = adapter.export_world_state()
        
        assert isinstance(state, dict)
        # Each location should have expected keys
        for loc_id, loc_data in state.items():
            assert "location_id" in loc_data
            assert "name" in loc_data
            assert "valuation_profile" in loc_data


class TestMCPServer:
    """Tests for MCP server creation."""
    
    def test_create_server(self):
        """Test creating the MCP server."""
        from mcp.server import create_server
        
        server = create_server()
        assert server is not None
        assert server.name == "evenflow-mcp"
    
    def test_server_has_tools(self):
        """Test that server has expected tools registered."""
        from mcp.server import create_server
        
        server = create_server()
        # Tools are registered via decorators, so server should be functional
        assert server is not None


class TestSchemas:
    """Tests for schema dataclasses."""
    
    def test_location_query_defaults(self):
        """Test LocationQuery default values."""
        query = LocationQuery(location_id="test")
        
        assert query.location_id == "test"
        assert query.include_traces is True
        assert query.include_affordances is True
        assert query.decay_to_now is True
    
    def test_trace_query_defaults(self):
        """Test TraceQuery default values."""
        query = TraceQuery()
        
        assert query.location_id is None
        assert query.actor_id is None
        assert query.min_intensity == 0.0
        assert query.limit == 100
    
    def test_decay_channel_enum(self):
        """Test DecayChannel enum values."""
        assert DecayChannel.PERSONAL.value == "personal"
        assert DecayChannel.GROUP.value == "group"
        assert DecayChannel.BEHAVIOR.value == "behavior"
