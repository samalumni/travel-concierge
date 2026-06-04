# Hotel Concierge — System Design Spec

**Date:** 2026-06-01
**Branch:** jz_hotel
**Author:** Jeff Zhu
**Status:** Approved — ready for implementation planning

---

## Overview

Refocus the existing travel concierge multi-agent system into a **hotel concierge** system centered on the guest's stay experience after booking. The pre-booking travel planning flow (destination inspiration, flight search, booking) is removed. The system picks up from a confirmed hotel reservation and guides the guest through pre-arrival, the active stay, and post-departure.

All key architectural features are preserved: multi-agent orchestration (Google ADK), the two-level policy framework, stateful session memory, structured Pydantic outputs, Google Maps/Search grounding, and the SQLAlchemy database layer.

---

## Approach

**Clean hotel-first redesign (Approach 2):** rename agents and replace all travel-specific abstractions with hotel-native ones throughout — types, prompts, tools, policy files, and database schema. No travel artifacts remain in the codebase.

---

## Agent Architecture

### Agents removed

| Agent | Reason |
|---|---|
| `inspiration_agent` | Destination discovery — out of scope |
| `planning_agent` | Flight/hotel search — out of scope |
| `booking_agent` | Pre-booking payment flow — out of scope; replaced by room-charge tool |

### New hierarchy

```
root_agent  (Hotel Concierge)
├── pre_stay_agent
├── in_stay_agent
│   ├── dining_agent
│   ├── housekeeping_agent
│   ├── local_concierge_agent
│   └── stay_monitor_agent
└── post_stay_agent
```

### Agent responsibilities

**`root_agent`**
- Greets guest warmly, collects first name / last name / email
- Calls `load_guest_profile` immediately — never deferred
- Loads `StayRecord` from session state; determines stay phase (pre / in / post) by comparing current time against `check_in_date` and `check_out_date`
- Routes to the appropriate phase agent
- No travel routing logic (flights, destinations) remains

**`pre_stay_agent`**
- Collects digital check-in information: expected arrival time, room preferences (bed type, floor, view, temperature, pillow type), early check-in requests
- Saves preferences to session state via `memorize`
- Persists collected preferences to the guest DB profile via `update_guest_preferences`

**`in_stay_agent`**
- Orchestrator for the active stay period
- Routes requests to the appropriate sub-agent based on request type
- Sub-agents:

  **`dining_agent`**
  - Hotel restaurant table reservations
  - Room service orders
  - Dietary accommodation handling (cross-references guest `dietary_restrictions` from profile)
  - Posts charges to room via `post_room_charge`

  **`housekeeping_agent`**
  - Extra towels, pillows, amenities requests
  - Maintenance issue reporting
  - Room refresh scheduling
  - Most requests are no-charge; exceptions posted via `post_room_charge`

  **`local_concierge_agent`**
  - Transport options to/from hotel and around the local area
  - Local restaurant and attraction recommendations (Google Maps + Search grounding)
  - Tour and activity information; can book local tours and post charges via `post_room_charge`

  **`stay_monitor_agent`**
  - Monitors status of local tour/activity bookings via `event_booking_check`
  - Checks weather impact on outdoor activities via `weather_impact`
  - Surfaces issues proactively and escalates to human concierge when needed
  - Activated by the "monitor" command from `in_stay_agent` or when a local booking needs checking

**`post_stay_agent`**
- Collects free-text stay feedback
- Runs NLP preference extraction via `extract_preferences` (controlled generation)
- Filters to high/medium confidence extractions only; discards low confidence silently
- Informs guest that preferences will be saved before persisting
- Persists extracted preferences to DB via `update_guest_preferences`
- Retrieves itemized room charges via `get_room_charges`
- Presents itemized bill for guest review
- Confirms settlement; updates booking status to `COMPLETED`

---

## Data Model

### Types removed from `shared_libraries/types.py`

| Type | Reason |
|---|---|
| `Itinerary`, `ItineraryDay` | Replaced by `StayRecord` |
| `Destination`, `DestinationIdeas` | Destination discovery removed |
| `PackingList` | Travel-specific |
| `HotelEvent`, `AttractionEvent` | Replaced by hotel-native service types |

`POI` and `POISuggestions` are **kept** — reused by `local_concierge_agent`.

### New / updated Pydantic types (`shared_libraries/types.py`)

```python
class StayRecord(BaseModel):
    hotel_name: str
    hotel_address: str
    room_type: str
    booking_id: str
    check_in_date: str        # YYYY-MM-DD
    check_out_date: str       # YYYY-MM-DD
    check_in_time: str        # HH:MM
    check_out_time: str       # HH:MM
    arrival_eta: str | None   # guest-provided, set by pre_stay_agent
    num_nights: int


class GuestPreferences(BaseModel):
    pillow_preference: str | None        # e.g. "feather", "foam", "firm"
    room_temperature_c: int | None       # e.g. 20
    floor_preference: str | None         # e.g. "high", "low", "no preference"
    bed_type_preference: str | None      # e.g. "king", "twin"
    view_preference: str | None          # e.g. "ocean", "city", "garden"
    dietary_restrictions: list[str]      # e.g. ["vegan", "nut allergy"]
    special_requests: list[str]          # free-text carry-forwards


class ServiceCharge(BaseModel):
    charge_id: str
    service_type: str       # "dining" | "housekeeping" | "local"
    description: str        # e.g. "Room service: club sandwich x2"
    amount_usd: float
    posted_at: str          # ISO datetime


class ExtractedPreference(BaseModel):
    field: str      # e.g. "pillow_preference", "dietary_restrictions"
    value: str      # e.g. "feather", "vegan"
    confidence: str # "high" | "medium" | "low"
```

`UserProfile` is updated to absorb `GuestPreferences` fields and remove travel-specific fields (`passport_nationality`, `home_transit_preference`, `home_address`).

### Database changes

**`guest` table** — add `preferences TEXT` column (JSON-serialized `GuestPreferences`). Portable across SQLite (default) and PostgreSQL (production, where it can be promoted to `JSONB`).

**`service_charge` table** — new table:
```sql
service_charge(
    charge_id     TEXT PRIMARY KEY,
    booking_id    TEXT NOT NULL REFERENCES booking(booking_id),
    service_type  TEXT NOT NULL,
    description   TEXT NOT NULL,
    amount_usd    NUMERIC(10,2) NOT NULL,
    posted_at     DATETIME NOT NULL
)
```

**`hotel`, `room`, `booking` tables** — unchanged.

---

## Tools

### Tools removed

| Tool | Reason |
|---|---|
| `flight_search`, `flight_seat_selection` | Travel-specific |
| `hotel_search`, `hotel_room_selection` | Pre-booking discovery removed |
| `create_reservation`, `payment_choice`, `process_payment` | No payment flow during stay |

### Tools kept

- `memorize`, `forget`, `memorize_list` — session state management
- `load_guest_profile` — guest + booking profile loader
- `google_search_grounding` — local area recommendations
- Google Maps Grounding MCP (`places.py`) — geocoding, place search
- `event_booking_check` — local tour/activity booking status
- `weather_impact` — outdoor activity weather risk
- `get_booking_status`, `get_guest_bookings`, `update_booking` — booking lifecycle management

### New tools

**`post_room_charge(booking_id, service_type, description, amount_usd) → ServiceCharge`**
Posts a charge to the room bill. Inserts into `service_charge` table. Used by `dining_agent`, `housekeeping_agent`, and `local_concierge_agent`.

**`get_room_charges(booking_id) → list[ServiceCharge]`**
Returns all charges posted to a booking. Used by `post_stay_agent` at checkout.

**`extract_preferences(feedback_text) → list[ExtractedPreference]`**
Controlled generation call (Gemini, `output_schema=list[ExtractedPreference]`) that parses free-text feedback into structured field/value pairs with confidence ratings. Used only by `post_stay_agent`.

**`update_guest_preferences(guest_id, preferences: dict) → None`**
Merges extracted preferences into the guest's `preferences` column in the DB. Merge rule: high/medium confidence values from the current stay always overwrite the stored value (more recent feedback wins); low confidence values are never written. Fields absent from the current extraction are left unchanged.

### Tools per agent

| Agent | Tools |
|---|---|
| `root_agent` | `load_guest_profile`, `memorize` |
| `pre_stay_agent` | `memorize`, `update_guest_preferences` |
| `dining_agent` | `post_room_charge`, `memorize` |
| `housekeeping_agent` | `post_room_charge`, `memorize` |
| `local_concierge_agent` | `google_search_grounding`, Google Maps MCP, `post_room_charge` |
| `stay_monitor_agent` | `event_booking_check`, `weather_impact` |
| `post_stay_agent` | `extract_preferences`, `update_guest_preferences`, `get_room_charges`, `get_guest_bookings`, `update_booking`, `memorize` |

---

## Preference Extraction Flow

```
1. Collect feedback           ← free-text from guest at post_stay
2. extract_preferences()      ← Gemini controlled generation → list[ExtractedPreference]
3. Filter by confidence       ← keep "high" and "medium" only; discard "low" silently
4. Inform guest               ← "We've noted your preference for feather pillows."
5. update_guest_preferences() ← merge into guest DB profile
6. get_room_charges()         ← retrieve itemized bill
7. Present itemized bill      ← show charges with total
8. Guest confirms             ← booking status → COMPLETED
```

**Consent rule:** Before step 4, agent must inform the guest that preferences are being saved for future stays. If the guest objects, `update_guest_preferences` is not called.

---

## Policy Framework

### Mechanism unchanged

Two-level injection: `HotelPolicyPlugin` injects `general_hotel_policy.md` globally to all agents at model call time; per-agent callbacks inject domain-specific policy files.

### Policy files

| File | Action | Notes |
|---|---|---|
| `general_hotel_policy.md` | Update | Remove travel advisory language; add in-stay service scope; add preference extraction consent rule |
| `root_agent.md` | Update | Remove flight/inspiration routing rules |
| `inspiration_agent.md` | **Delete** | Agent removed |
| `planning_agent.md` | **Delete** | Agent removed |
| `booking_agent.md` | **Delete** | Agent removed |
| `pre_trip_agent.md` | Rename → `pre_stay_agent.md` | Refocus on digital check-in, preference collection |
| `in_trip_agent.md` | Rename → `in_stay_agent.md` | Refocus on in-stay service orchestration |
| `post_trip_agent.md` | Rename → `post_stay_agent.md` | Add preference extraction policy: confidence thresholds, consent language |
| `dining_agent.md` | **New** | Dietary allergy escalation, charge transparency |
| `housekeeping_agent.md` | **New** | Request prioritization, maintenance escalation to human staff |
| `local_concierge_agent.md` | **New** | Verified recommendations only; disclose suggestions are not hotel-endorsed |
| `stay_monitor_agent.md` | **New** | Proactive issue surfacing; escalation to human concierge |

### New global policy content (preference extraction)

> - Before extracting and storing preferences from guest feedback, inform the guest that their preferences will be saved to personalise future stays.
> - Never store preferences the guest explicitly says they do not want saved.
> - Low-confidence extractions must be silently discarded — never confirm a preference back to the guest unless confidence is high or medium.

---

## Files Affected (summary)

### Deleted
- `travel_concierge/sub_agents/inspiration/` (entire directory)
- `travel_concierge/sub_agents/planning/` (entire directory)
- `travel_concierge/sub_agents/booking/` (entire directory)
- `travel_concierge/hotel_policy/inspiration_agent.md`
- `travel_concierge/hotel_policy/planning_agent.md`
- `travel_concierge/hotel_policy/booking_agent.md`

### Renamed
- `sub_agents/pre_trip/` → `sub_agents/pre_stay/`
- `sub_agents/in_trip/` → `sub_agents/in_stay/`
- `sub_agents/post_trip/` → `sub_agents/post_stay/`
- `hotel_policy/pre_trip_agent.md` → `hotel_policy/pre_stay_agent.md`
- `hotel_policy/in_trip_agent.md` → `hotel_policy/in_stay_agent.md`
- `hotel_policy/post_trip_agent.md` → `hotel_policy/post_stay_agent.md`

### New files
- `travel_concierge/tools/room_charge.py` (`post_room_charge`, `get_room_charges`)
- `travel_concierge/tools/preferences.py` (`extract_preferences`, `update_guest_preferences`)

Note: `dining_agent`, `housekeeping_agent`, `local_concierge_agent`, and `stay_monitor_agent` follow the existing pattern — they are defined inline in `travel_concierge/sub_agents/in_stay/agent.py` alongside `in_stay_agent`, not in separate subdirectories. Prompts for these sub-agents live in `travel_concierge/sub_agents/in_stay/prompt.py`.
- `travel_concierge/hotel_policy/dining_agent.md`
- `travel_concierge/hotel_policy/housekeeping_agent.md`
- `travel_concierge/hotel_policy/local_concierge_agent.md`
- `travel_concierge/hotel_policy/stay_monitor_agent.md`
- `travel_concierge/database/migrations/add_preferences_and_service_charge.py`

### Modified
- `travel_concierge/shared_libraries/types.py` — replace travel types with hotel types
- `travel_concierge/database/models.py` — add `preferences` to `Guest`; add `ServiceCharge` model
- `travel_concierge/agent.py` — rewire root agent with new sub-agent set
- `travel_concierge/prompt.py` — rewrite root agent instruction
- `travel_concierge/hotel_policy/general_hotel_policy.md` — update scope
- `travel_concierge/hotel_policy/root_agent.md` — update routing rules
- `travel_concierge/hotel_policy/callbacks.py` — add callbacks for new agents
- `travel_concierge/sub_agents/pre_stay/agent.py` + `prompt.py` — refocus
- `travel_concierge/sub_agents/in_stay/agent.py` + `prompt.py` — refocus, wire new sub-agents
- `travel_concierge/sub_agents/post_stay/agent.py` + `prompt.py` — add extraction flow
