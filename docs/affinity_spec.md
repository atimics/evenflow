# Affinity Specification

**Version:** 0.1
**Target Platform:** Evennia
**Purpose:** Define relationship intelligence as emergent world behavior

---

## 1. Core Concept

Affinity is **accumulated relational memory** stored in world entities. It is not a reputation system, not a morality meter, and never speaks. Affinity answers: *How does this place/object/culture feel about this actor or behavior, given everything that has happened here?*

Key principles:

- **No judgments, only correlations.** The system stores "elf + fire → harm happened" not "elves are bad."
- **No dialogue.** Entities express affinity through affordance modulation, never speech.
- **Slow drift.** Changes accumulate over hours/days, not seconds.
- **Emergent meaning.** Players infer relationships; the system never explains.

---

## 2. Entity Taxonomy

All world objects fall into four conceptual roles. These are not necessarily distinct classes—an object may fulfill multiple roles—but they define how affinity flows.

### 2.1 Actor

**Definition:** An entity with intent that initiates events.

| Subtype | Description | Affinity Role |
|---------|-------------|---------------|
| Player | Human-controlled character | Primary affinity target; accumulates reputation across entities |
| NPC | World-controlled agent | Can be affinity source or target; may reference institutional memory |
| Spirit | Manifested supernatural entity | Rare; typically bound to Location or Artifact |

**Key properties:**
- `actor_id`: Unique identifier
- `actor_tags`: Set of categorical markers (e.g., `{"elf", "mage", "outsider"}`)
- `behavior_signature`: Rolling window of recent action types

### 2.2 Location (Substrate)

**Definition:** A persistent place that accumulates memory even when empty.

| Examples | Memory Focus |
|----------|--------------|
| Forest, Grove | Ecological harm, reverence, extraction |
| City, Market | Commerce, violence, cultural mixing |
| Ruin, Battlefield | Death, desecration, remembrance |
| Sacred Site, Temple | Ritual correctness, devotion, transgression |
| River, Mountain | Passage, offering, obstruction |

**Key properties:**
- `location_id`: Unique identifier
- `memory_traces`: Dict mapping `(actor_tag, event_type) → TraceRecord`
- `affinity_fields`: Dict mapping `actor_tag → float` (range: -1.0 to 1.0)
- `behavior_biases`: Dict mapping `event_type → float` (modifier for that action here)
- `saturation`: Float (0.0–1.0) indicating how "full" memory is

### 2.3 Artifact

**Definition:** A mobile object that carries pressure and learns its bearer.

| Examples | Pressure Style |
|----------|----------------|
| Ring, Amulet | Amplifies existing desires |
| Weapon | Biases toward/against violence |
| Book, Song | Shapes perception and knowledge |
| Relic | Connects bearer to institutional memory |
| Cursed Tool | Creates dependency, fatigue, obsession |

**Key properties:**
- `artifact_id`: Unique identifier
- `origin_tags`: Set of source associations (e.g., `{"elven", "old_kingdom"}`)
- `bearer_memory`: Dict mapping `bearer_id → BearerRecord`
- `pressure_vectors`: List of `PressureRule` objects
- `influence_accumulator`: Float tracking current grip on bearer

### 2.4 Institution (Field)

**Definition:** A distributed pattern across multiple objects—not a single entity.

| Examples | Manifestation |
|----------|---------------|
| Elven Culture | Shared memory in forests, elven NPCs, elven artifacts |
| The Empire | Biases in imperial cities, soldier NPCs, official documents |
| Fire Magic Tradition | Spell behavior, mage NPCs, enchanted items |
| The Old Ways | Sacred sites, oral tradition, ancestral artifacts |

**Key properties:**
- Institutions have no single object representation
- They exist as **correlated affinity** across Locations, Artifacts, and NPCs
- Queried by aggregating relevant entities, never stored centrally

**Implementation note:** Create an `InstitutionQuery` service that computes institutional stance by sampling affiliated entities. Cache results with TTL.

---

## 3. Event Ontology

Events are the atomic unit of affinity change. Every logged event has:

```python
@dataclass
class AffinityEvent:
    event_type: str           # From controlled vocabulary
    actor_id: str             # Who initiated
    actor_tags: Set[str]      # Categorical markers at time of event
    target_id: Optional[str]  # Affected entity, if any
    location_id: str          # Where it happened
    intensity: float          # 0.0–1.0, magnitude of action
    timestamp: float          # Unix time
    context_tags: Set[str]    # Additional qualifiers
```

### 3.1 Event Type Vocabulary

| Category | Event Types | Typical Intensity |
|----------|-------------|-------------------|
| **Harm** | `harm.physical`, `harm.fire`, `harm.poison`, `harm.magical` | 0.3–1.0 |
| **Healing** | `heal.physical`, `heal.magical`, `heal.rest` | 0.2–0.6 |
| **Death** | `death.combat`, `death.sacrifice`, `death.natural` | 0.8–1.0 |
| **Extraction** | `extract.harvest`, `extract.mine`, `extract.hunt`, `extract.loot` | 0.2–0.7 |
| **Creation** | `create.build`, `create.plant`, `create.craft`, `create.ritual` | 0.2–0.6 |
| **Trespass** | `trespass.enter`, `trespass.defile`, `trespass.observe` | 0.1–0.5 |
| **Offering** | `offer.gift`, `offer.sacrifice`, `offer.prayer` | 0.2–0.8 |
| **Commerce** | `trade.fair`, `trade.exploit`, `trade.gift` | 0.1–0.4 |
| **Magic** | `magic.cast`, `magic.summon`, `magic.bind`, `magic.dispel` | 0.3–0.9 |
| **Social** | `social.aid`, `social.betray`, `social.honor`, `social.insult` | 0.2–0.7 |
| **Movement** | `move.pass`, `move.flee`, `move.pursue` | 0.05–0.2 |

### 3.2 Context Tags

Context tags qualify events without creating new event types:

- `violent`, `peaceful`
- `public`, `secret`
- `ritual`, `mundane`
- `first_time`, `repeated`
- `sanctioned`, `forbidden`

**Example event:**
```python
AffinityEvent(
    event_type="extract.hunt",
    actor_id="player_0042",
    actor_tags={"human", "hunter", "outsider"},
    target_id="deer_entity",
    location_id="whispering_woods",
    intensity=0.4,
    timestamp=1703520000.0,
    context_tags={"first_time", "mundane"}
)
```

---

## 4. Memory Model

Memory is how entities store and forget events. This creates the "slow drift" that makes affinity feel organic.

### 4.1 Trace Records

A trace is a single correlation stored in an entity's memory.

```python
@dataclass
class TraceRecord:
    actor_tag: str            # Which actor category
    event_type: str           # What happened
    accumulated: float        # Total weighted intensity
    last_updated: float       # Timestamp of last event
    event_count: int          # How many times
```

**Storage:** Locations store traces in `memory_traces[(actor_tag, event_type)]`.

### 4.2 Decay Function

Memory fades over time. Decay is exponential with a configurable half-life.

```
current_value = accumulated * (0.5 ^ (time_elapsed / half_life))
```

| Entity Type | Default Half-Life | Rationale |
|-------------|-------------------|-----------|
| Location | 30 days | Places remember slowly |
| Artifact | 7 days | Objects are more reactive |
| NPC | 3 days | Individuals forget faster |

**Implementation:** Decay is computed lazily on read, not continuously. Store `accumulated` and `last_updated`; compute decayed value when accessed.

```python
def get_decayed_value(trace: TraceRecord, half_life_seconds: float) -> float:
    elapsed = current_time() - trace.last_updated
    decay_factor = 0.5 ** (elapsed / half_life_seconds)
    return trace.accumulated * decay_factor
```

### 4.3 Accumulation

When a new event matches an existing trace:

```python
def accumulate(trace: TraceRecord, event: AffinityEvent, half_life: float):
    # First, decay existing value to present
    decayed = get_decayed_value(trace, half_life)

    # Add new intensity
    trace.accumulated = decayed + event.intensity
    trace.last_updated = event.timestamp
    trace.event_count += 1
```

### 4.4 Saturation

Entities have limited memory capacity. Saturation prevents runaway accumulation.

```
effective_intensity = raw_intensity * (1 - saturation^2)
```

| Saturation Level | Effect |
|------------------|--------|
| 0.0–0.3 | Full sensitivity to new events |
| 0.3–0.7 | Diminishing returns; entity is "experienced" |
| 0.7–1.0 | Near-deaf; only extreme events register |

**Saturation increases** with total trace volume. **Saturation decreases** slowly over time when no events occur.

### 4.5 Affinity Threshold Behaviors

Affinity fields (per actor_tag) range from -1.0 (hostile) to +1.0 (welcoming). Thresholds trigger affordance changes:

| Range | Label | Affordance Effect |
|-------|-------|-------------------|
| -1.0 to -0.7 | Hostile | Active hindrance; danger increases |
| -0.7 to -0.3 | Unwelcoming | Passive resistance; inefficiency |
| -0.3 to +0.3 | Neutral | No modification |
| +0.3 to +0.7 | Favorable | Passive assistance; luck |
| +0.7 to +1.0 | Aligned | Active cooperation; revelation |

### 4.6 Computing Affinity Fields

Affinity for an actor_tag is derived from traces, not stored directly:

```python
def compute_affinity(location, actor_tag: str) -> float:
    positive = 0.0
    negative = 0.0

    for (tag, event_type), trace in location.memory_traces.items():
        if tag != actor_tag:
            continue

        value = get_decayed_value(trace, location.half_life)
        weight = EVENT_WEIGHTS.get(event_type, 0.0)  # +1 for beneficial, -1 for harmful

        if weight > 0:
            positive += value * weight
        else:
            negative += value * abs(weight)

    # Normalize to [-1, 1] using tanh-like curve
    raw = positive - negative
    return math.tanh(raw / AFFINITY_SCALE)
```

---

## 5. Affordance Catalog

Affordances are the behavioral outputs of affinity. They modulate what happens, never what is said.

### 5.1 Location Affordances

| Affordance | Hostile Effect | Favorable Effect |
|------------|----------------|------------------|
| **Pathing** | Paths twist; travel takes longer | Shortcuts appear; travel is swift |
| **Encounter Rate** | Dangerous creatures more frequent | Peaceful creatures; threats avoid |
| **Spell Efficacy** | Spells misfire, reduced power | Spells amplified, unexpected success |
| **Resource Yield** | Harvests poor, veins barren | Bounty appears, hidden caches |
| **Rest Quality** | Sleep disturbed, healing slowed | Deep rest, bonus recovery |
| **Navigation** | Landmarks hidden, disorientation | Clear signs, intuitive direction |
| **Weather (local)** | Harsh micro-weather | Sheltering conditions |
| **Animal Behavior** | Wildlife flees or attacks | Wildlife approaches, aids |

### 5.2 Artifact Affordances (Pressure Vectors)

| Pressure Type | Mechanism | Example |
|---------------|-----------|---------|
| **Desire Amplification** | Increases existing wants | Ring makes power-hunger sharper |
| **Fatigue Timing** | Exhaustion at critical moments | Bearer tires when trying to discard |
| **Coincidence Bias** | Nudges random outcomes | "Lucky" finds that serve artifact's origin |
| **Skill Modulation** | Easier/harder by alignment | Elven blade flows for elves, resists orcs |
| **Perception Filter** | Notice more/less by category | Cursed gold makes other wealth invisible |
| **Dependency Curve** | Withdrawal when separated | Discomfort grows with distance |

**Pressure rules** are defined per artifact:

```python
@dataclass
class PressureRule:
    trigger: str              # "bearer_action", "bearer_state", "proximity"
    condition: str            # Expression evaluated against context
    effect_type: str          # From pressure type vocabulary
    intensity_base: float     # 0.0–1.0
    scales_with_influence: bool  # Grows as artifact learns bearer?
```

### 5.3 Institutional Affordances

Institutions modulate through their constituent entities:

| Domain | Effect |
|--------|--------|
| **NPC Disposition** | Affiliated NPCs slightly warmer/colder |
| **Artifact Attunement** | Items from institution work better/worse |
| **Ritual Success** | Ceremonies of that tradition more/less reliable |
| **Lore Access** | Knowledge surfaces or stays hidden |
| **Faction Perception** | Soft reputation by association |

---

## 6. Player Legibility Rules

Players must never see affinity values. They experience patterns.

### 6.1 What May Be Hinted

| Category | Permitted Hints |
|----------|-----------------|
| **Environmental description** | "The forest feels watchful." / "An easy path opens." |
| **Outcome flavor** | "Your spell flares unexpectedly bright." |
| **NPC behavior** | Wariness, warmth (no explanation why) |
| **Animal reactions** | Approach, avoidance, aggression |
| **Folklore from NPCs** | "They say elves are unwelcome in the iron hills." |
| **Contrast between characters** | Different outcomes for different actors in same place |
| **Generational echoes** | "Your family name carries weight here." |

### 6.2 What Must Never Be Shown

| Forbidden | Rationale |
|-----------|-----------|
| Numeric affinity values | Breaks immersion; invites gaming |
| Explicit cause-effect | "Because you killed the deer, the forest..." |
| System explanations | No meta-text about how affinity works |
| Progress bars, meters | No UI representation of hidden state |
| Artifact inner monologue | Objects do not speak their intent |
| Institutional stance readouts | Cultures don't issue press releases |

### 6.3 Discovery Mechanisms

Players learn affinity through:

1. **Repetition** — Same action, same place, pattern emerges
2. **Contrast** — Different character gets different treatment
3. **Folklore** — NPCs share beliefs (which may be wrong)
4. **Consequence** — Delayed effects trace back to past actions
5. **Generational memory** — New characters inherit hints of old
6. **Experimentation** — Deliberate testing by observant players

---

## 7. Implementation Checklist

A junior engineer implementing this system should build:

- [ ] `AffinityEvent` dataclass and event logging
- [ ] `TraceRecord` storage on Location objects
- [ ] Decay computation (lazy, on-read)
- [ ] `compute_affinity()` function per actor_tag
- [ ] Saturation tracking and diminishing returns
- [ ] Affordance modifier hooks for each system (pathing, spells, etc.)
- [ ] `PressureRule` evaluation loop for artifacts
- [ ] `InstitutionQuery` aggregator service
- [ ] Description generator that maps affinity ranges to flavor text
- [ ] Background task for periodic trace cleanup (remove near-zero traces)

---

## 8. Example Scenario

**Setup:** Whispering Woods has neutral affinity toward humans. Player (human, hunter) enters.

**Events over 3 sessions:**

1. Player hunts deer (`extract.hunt`, intensity 0.4) — trace created
2. Player hunts again (`extract.hunt`, intensity 0.5) — trace accumulates
3. Player builds campfire carelessly (`harm.fire`, intensity 0.3) — new trace
4. Player rests (`heal.rest`, intensity 0.2) — minor positive trace

**After 1 week (no visits):**

- Hunt traces decayed ~25% (half-life 30 days)
- Fire trace decayed ~25%
- Computed affinity for `human` ≈ -0.15 (slightly unwelcoming)

**Player returns:**

- Pathing: Slightly longer travel times
- Encounters: One extra wolf encounter
- Rest: Sleep messages mention "uneasy dreams"
- No explanation given

**If player brings offering:**

- `offer.gift` event with intensity 0.5
- Positive trace begins countering negative
- Over weeks, affinity drifts toward neutral

**Player never sees:** Numbers, cause-effect statements, or "the forest forgives you."

---

## 9. Glossary

| Term | Definition |
|------|------------|
| **Affinity** | Accumulated relational memory; how an entity feels about an actor category |
| **Trace** | A single stored correlation: (actor_tag, event_type) → accumulated value |
| **Decay** | Exponential memory fade over time |
| **Saturation** | Memory fullness; limits new accumulation |
| **Affordance** | Behavioral output; how affinity changes world mechanics |
| **Pressure** | Artifact influence on bearer; grows with exposure |
| **Institution** | Distributed pattern across multiple entities; never a single object |
| **Actor Tag** | Categorical marker (e.g., "elf", "mage") used for affinity grouping |

---

*End of specification.*
