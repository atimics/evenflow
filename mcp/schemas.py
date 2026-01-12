"""
JSON schemas for MCP tools and resources.

Defines the input/output shapes for all MCP endpoints.
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class DecayChannel(str, Enum):
    """Affinity decay channel types."""
    PERSONAL = "personal"
    GROUP = "group"
    BEHAVIOR = "behavior"


class AffordanceMode(str, Enum):
    """Affordance trigger modes."""
    HOSTILE = "hostile"
    FAVORABLE = "favorable"
    NEUTRAL = "neutral"


# =============================================================================
# Input Schemas
# =============================================================================

@dataclass
class LocationQuery:
    """Query for location state."""
    location_id: str
    include_traces: bool = True
    include_affordances: bool = True
    decay_to_now: bool = True


@dataclass
class ArtifactQuery:
    """Query for artifact state."""
    artifact_id: str
    include_traces: bool = True


@dataclass
class TraceQuery:
    """Query for affinity traces."""
    location_id: Optional[str] = None
    actor_id: Optional[str] = None
    event_type: Optional[str] = None
    channel: Optional[DecayChannel] = None
    min_intensity: float = 0.0
    limit: int = 100


@dataclass
class ActionPrediction:
    """Predict consequences of an action."""
    actor_id: str
    actor_tags: List[str]
    location_id: str
    event_type: str
    intensity: float


# =============================================================================
# Output Schemas
# =============================================================================

@dataclass
class TraceInfo:
    """Trace record with decay applied."""
    key: str  # "(actor_id, event_type)" or "event_type"
    channel: str
    accumulated: float
    decayed_value: float
    last_updated: float
    event_count: int
    is_scar: bool


@dataclass
class AffordanceInfo:
    """Affordance configuration and state."""
    affordance_type: str
    enabled: bool
    mechanical_handle: Optional[str]
    severity_clamp_hostile: float
    severity_clamp_favorable: float
    cooldown_seconds: int
    cooldown_remaining: Optional[float]
    tells_hostile: List[str]
    tells_favorable: List[str]


@dataclass
class LocationState:
    """Complete location state snapshot."""
    location_id: str
    name: str
    description: str
    valuation_profile: Dict[str, float]
    saturation: Dict[str, float]
    traces: List[TraceInfo]
    affordances: List[AffordanceInfo]
    last_tick: float


@dataclass
class AffinityScore:
    """Computed affinity score breakdown."""
    total: float
    personal: float
    group: float
    behavior: float
    threshold_label: str  # "hostile", "wary", "neutral", "warm", "favorable"


@dataclass
class ActionConsequence:
    """Predicted consequence of an action."""
    location_id: str
    actor_id: str
    event_type: str
    affinity_before: AffinityScore
    affinity_after: AffinityScore
    triggered_affordances: List[str]
    narrative_hints: List[str]


@dataclass
class WorldHistorySummary:
    """Summary of recent world events for folklore generation."""
    location_id: str
    time_window_days: int
    dominant_events: List[Dict[str, Any]]
    notable_actors: List[str]
    mood: str  # "peaceful", "troubled", "violent", "sacred"
    folklore_seeds: List[str]


# =============================================================================
# Serialization helpers
# =============================================================================

def to_dict(obj: Any) -> Dict[str, Any]:
    """Convert dataclass to dict, handling nested objects."""
    if hasattr(obj, '__dataclass_fields__'):
        return asdict(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_dict(item) for item in obj]
    return obj
