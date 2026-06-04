# Hotel Concierge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refocus the travel concierge multi-agent system into a hotel stay concierge that handles pre-arrival, in-stay services, and post-stay preference extraction.

**Architecture:** A root agent loads the guest's confirmed `StayRecord` and routes to one of three phase agents (`pre_stay`, `in_stay`, `post_stay`). `in_stay` orchestrates four sub-agents (dining, housekeeping, local_concierge, stay_monitor). `post_stay` uses Gemini controlled generation to extract structured preferences from free-text feedback and persist them to the guest DB profile.

**Tech Stack:** Python 3.11+, Google ADK 1.31+, Gemini 2.5 Flash, SQLAlchemy + SQLite, Pydantic v2, Google Maps MCP, Google Search grounding, Arize/OpenTelemetry.

**Spec:** `docs/superpowers/specs/2026-06-01-hotel-concierge-design.md`

---

## File Map

| Action | Path |
|---|---|
| Modify | `travel_concierge/shared_libraries/types.py` |
| Modify | `travel_concierge/shared_libraries/constants.py` |
| Modify | `travel_concierge/database/models.py` |
| **Create** | `travel_concierge/tools/room_charge.py` |
| **Create** | `travel_concierge/tools/preferences.py` |
| Modify | `travel_concierge/hotel_policy/general_hotel_policy.md` |
| Modify | `travel_concierge/hotel_policy/root_agent.md` |
| Delete | `travel_concierge/hotel_policy/inspiration_agent.md` |
| Delete | `travel_concierge/hotel_policy/planning_agent.md` |
| Delete | `travel_concierge/hotel_policy/booking_agent.md` |
| Rename+modify | `hotel_policy/pre_trip_agent.md` → `hotel_policy/pre_stay_agent.md` |
| Rename+modify | `hotel_policy/in_trip_agent.md` → `hotel_policy/in_stay_agent.md` |
| Rename+modify | `hotel_policy/post_trip_agent.md` → `hotel_policy/post_stay_agent.md` |
| **Create** | `travel_concierge/hotel_policy/dining_agent.md` |
| **Create** | `travel_concierge/hotel_policy/housekeeping_agent.md` |
| **Create** | `travel_concierge/hotel_policy/local_concierge_agent.md` |
| **Create** | `travel_concierge/hotel_policy/stay_monitor_agent.md` |
| Modify | `travel_concierge/hotel_policy/callbacks.py` |
| git mv+modify | `sub_agents/pre_trip/` → `sub_agents/pre_stay/` (agent.py, prompt.py, `__init__.py`) |
| git mv+modify | `sub_agents/in_trip/` → `sub_agents/in_stay/` (agent.py, prompt.py, tools.py, `__init__.py`) |
| git mv+modify | `sub_agents/post_trip/` → `sub_agents/post_stay/` (agent.py, prompt.py, `__init__.py`) |
| Modify | `travel_concierge/agent.py` |
| Modify | `travel_concierge/prompt.py` |
| Modify | `travel_concierge/tools/memory.py` |
| **Create** | `travel_concierge/profiles/stay_empty_default.json` |
| Delete | `travel_concierge/sub_agents/inspiration/` (whole dir) |
| Delete | `travel_concierge/sub_agents/planning/` (whole dir) |
| Delete | `travel_concierge/sub_agents/booking/` (whole dir) |
| **Create** | `tests/unit/test_room_charge.py` |
| **Create** | `tests/unit/test_preferences.py` |
| Modify | `tests/unit/test_tools.py` |

---

## Task 1: Replace travel types with hotel-native Pydantic models

**Files:**
- Modify: `travel_concierge/shared_libraries/types.py`
- Test: `tests/unit/test_types.py` *(create)*

- [ ] **Step 1.1 — Write failing tests for new types**

Create `tests/unit/test_types.py`:

```python
import pytest
from pydantic import ValidationError
from travel_concierge.shared_libraries.types import (
    StayRecord,
    GuestPreferences,
    ServiceCharge,
    ExtractedPreference,
)


def test_stay_record_valid():
    s = StayRecord(
        hotel_name="IHG Grand",
        hotel_address="1 Main St, Seattle, WA",
        room_type="King Ocean View",
        booking_id="BK-001",
        check_in_date="2026-07-01",
        check_out_date="2026-07-05",
        check_in_time="15:00",
        check_out_time="11:00",
        arrival_eta=None,
        num_nights=4,
    )
    assert s.num_nights == 4
    assert s.arrival_eta is None


def test_guest_preferences_defaults():
    prefs = GuestPreferences()
    assert prefs.dietary_restrictions == []
    assert prefs.special_requests == []
    assert prefs.pillow_preference is None


def test_service_charge_valid():
    sc = ServiceCharge(
        charge_id="SC-001",
        service_type="dining",
        description="Club sandwich x2",
        amount_usd=38.0,
        posted_at="2026-07-02T12:00:00",
    )
    assert sc.service_type == "dining"


def test_extracted_preference_valid():
    ep = ExtractedPreference(field="pillow_preference", value="feather", confidence="high")
    assert ep.confidence == "high"


def test_itinerary_not_importable():
    """Itinerary should no longer exist in types."""
    import travel_concierge.shared_libraries.types as t
    assert not hasattr(t, "Itinerary")
    assert not hasattr(t, "PackingList")
    assert not hasattr(t, "Destination")
```

- [ ] **Step 1.2 — Run tests to verify they fail**

```
pytest tests/unit/test_types.py -v
```
Expected: FAIL — `StayRecord`, `GuestPreferences`, `ServiceCharge`, `ExtractedPreference` not importable.

- [ ] **Step 1.3 — Rewrite types.py**

Replace the full contents of `travel_concierge/shared_libraries/types.py`:

```python
"""Common data schema and types for hotel-concierge agents."""

from google.genai import types
from pydantic import BaseModel, Field

json_response_config = types.GenerateContentConfig(
    response_mime_type="application/json"
)


class StayRecord(BaseModel):
    """The guest's confirmed hotel stay — central session state object."""
    hotel_name: str
    hotel_address: str
    room_type: str
    booking_id: str
    check_in_date: str        # YYYY-MM-DD
    check_out_date: str       # YYYY-MM-DD
    check_in_time: str        # HH:MM
    check_out_time: str       # HH:MM
    arrival_eta: str | None = None
    num_nights: int


class GuestPreferences(BaseModel):
    """Structured hotel stay preferences, built up across stays."""
    pillow_preference: str | None = None
    room_temperature_c: int | None = None
    floor_preference: str | None = None
    bed_type_preference: str | None = None
    view_preference: str | None = None
    dietary_restrictions: list[str] = Field(default_factory=list)
    special_requests: list[str] = Field(default_factory=list)


class ServiceCharge(BaseModel):
    """A charge posted to the guest's room during their stay."""
    charge_id: str
    service_type: str   # "dining" | "housekeeping" | "local"
    description: str
    amount_usd: float
    posted_at: str      # ISO datetime


class ExtractedPreference(BaseModel):
    """A single structured preference extracted from free-text feedback."""
    field: str          # e.g. "pillow_preference"
    value: str          # e.g. "feather"
    confidence: str     # "high" | "medium" | "low"


class Room(BaseModel):
    """A room for selection."""
    is_available: bool = Field(description="Whether the room type is available.")
    price_in_usd: int = Field(description="The cost of the room.")
    room_type: str = Field(description="Type of room, e.g. King with Ocean View.")


class RoomsSelection(BaseModel):
    rooms: list[Room]


class Hotel(BaseModel):
    """A hotel property."""
    name: str = Field(description="Name of the hotel")
    address: str = Field(description="Full address of the hotel")
    check_in_time: str = Field(description="Time in HH:MM format")
    check_out_time: str = Field(description="Time in HH:MM format")
    thumbnail: str = Field(description="Hotel logo location")
    price: int = Field(description="Price of the room per night")


class HotelsSelection(BaseModel):
    hotels: list[Hotel]


class POI(BaseModel):
    """A Point Of Interest for local area recommendations."""
    place_name: str = Field(description="Name of the attraction")
    address: str = Field(description="Address or geocodable location")
    lat: str = Field(description="Latitude, e.g. 47.6062")
    long: str = Field(description="Longitude, e.g. -122.3321")
    review_ratings: str = Field(description="Rating, e.g. 4.8")
    highlights: str = Field(description="Short description")
    image_url: str = Field(description="URL to an image")
    map_url: str | None = Field(default=None, description="Google Maps URL")
    place_id: str | None = Field(default=None, description="Google Maps place_id")


class POISuggestions(BaseModel):
    places: list[POI]
```

- [ ] **Step 1.4 — Run tests to verify they pass**

```
pytest tests/unit/test_types.py -v
```
Expected: all 5 tests PASS.

- [ ] **Step 1.5 — Commit**

```bash
git add travel_concierge/shared_libraries/types.py tests/unit/test_types.py
git commit -m "feat: replace travel types with hotel-native Pydantic models"
```

---

## Task 2: Update state constants

**Files:**
- Modify: `travel_concierge/shared_libraries/constants.py`

- [ ] **Step 2.1 — Replace constants.py**

```python
"""Constants used as keys into ADK's session state."""

SYSTEM_TIME = "_time"
STAY_INITIALIZED = "_stay_initialized"

STAY_KEY = "stay_record"       # StayRecord JSON in session state
PROF_KEY = "user_profile"      # guest profile dict in session state

STAY_CHECK_IN = "stay_check_in_date"   # YYYY-MM-DD, for prompt template injection
STAY_CHECK_OUT = "stay_check_out_date"
```

- [ ] **Step 2.2 — Commit**

```bash
git add travel_concierge/shared_libraries/constants.py
git commit -m "feat: replace itinerary state keys with hotel stay keys"
```

---

## Task 3: Extend database models

**Files:**
- Modify: `travel_concierge/database/models.py`

- [ ] **Step 3.1 — Write a failing test for ServiceCharge ORM model**

Add to `tests/unit/test_types.py` (append, don't replace):

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from travel_concierge.database.models import Base, ServiceCharge as ServiceChargeORM, Guest, Booking


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_service_charge_orm_creation(db_session):
    """ServiceCharge table exists and a row can be inserted."""
    import uuid
    from datetime import datetime, timezone

    # need a guest and booking first (FK constraints)
    guest = Guest(
        guest_id=str(uuid.uuid4()),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
    )
    db_session.add(guest)
    db_session.flush()

    from travel_concierge.database.models import Hotel as HotelORM, Room as RoomORM, BookingStatus, PaymentStatus
    hotel = HotelORM(
        hotel_id=str(uuid.uuid4()),
        name="Test Hotel",
        address="1 Test St",
        city="Seattle",
        country="US",
    )
    db_session.add(hotel)
    db_session.flush()

    room = RoomORM(
        room_id=str(uuid.uuid4()),
        hotel_id=hotel.hotel_id,
        room_type="King",
        price_per_night_usd=200,
    )
    db_session.add(room)
    db_session.flush()

    booking = Booking(
        booking_id=str(uuid.uuid4()),
        guest_id=guest.guest_id,
        hotel_id=hotel.hotel_id,
        room_id=room.room_id,
        check_in_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
        check_out_date=datetime(2026, 7, 5, tzinfo=timezone.utc),
        num_nights=4,
        total_price_usd=800,
    )
    db_session.add(booking)
    db_session.flush()

    charge = ServiceChargeORM(
        charge_id=str(uuid.uuid4()),
        booking_id=booking.booking_id,
        service_type="dining",
        description="Club sandwich x2",
        amount_usd=38.00,
        posted_at=datetime.now(timezone.utc),
    )
    db_session.add(charge)
    db_session.commit()

    fetched = db_session.get(ServiceChargeORM, charge.charge_id)
    assert fetched.service_type == "dining"
    assert float(fetched.amount_usd) == 38.00


def test_guest_preferences_column(db_session):
    """Guest has a preferences TEXT column that stores JSON."""
    import json, uuid
    guest = Guest(
        guest_id=str(uuid.uuid4()),
        first_name="Bob",
        last_name="Smith",
        email="bob@example.com",
        preferences=json.dumps({"pillow_preference": "feather"}),
    )
    db_session.add(guest)
    db_session.commit()

    fetched = db_session.get(Guest, guest.guest_id)
    prefs = json.loads(fetched.preferences)
    assert prefs["pillow_preference"] == "feather"
```

- [ ] **Step 3.2 — Run to verify failure**

```
pytest tests/unit/test_types.py::test_service_charge_orm_creation tests/unit/test_types.py::test_guest_preferences_column -v
```
Expected: FAIL — `ServiceCharge` ORM model not found, `Guest.preferences` column missing.

- [ ] **Step 3.3 — Update models.py**

Add `preferences` to `Guest` and add `ServiceCharge` model. The full additions at the bottom of `travel_concierge/database/models.py`:

In the `Guest` class, add after `updated_at`:
```python
    preferences: Mapped[str | None] = mapped_column(String(4096), nullable=True)
```

After the `Booking` class, append the new `ServiceCharge` model:
```python
# ---------------------------------------------------------------------------
# ServiceCharge
# ---------------------------------------------------------------------------

class ServiceCharge(Base):
    """A charge posted to the guest's room bill during their stay."""

    __tablename__ = "service_charge"

    charge_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    booking_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("booking.booking_id", ondelete="CASCADE"), index=True
    )
    service_type: Mapped[str] = mapped_column(String(50))   # "dining" | "housekeeping" | "local"
    description: Mapped[str] = mapped_column(String(500))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    posted_at: Mapped[datetime] = mapped_column(default=_utcnow)

    booking: Mapped["Booking"] = relationship("Booking", back_populates="charges")

    __table_args__ = (
        CheckConstraint("amount_usd >= 0", name="ck_charge_non_negative"),
    )

    def __repr__(self) -> str:
        return f"<ServiceCharge {self.charge_id!r} {self.service_type!r} ${self.amount_usd}>"
```

Also add the back-reference to `Booking`:
```python
    charges: Mapped[list["ServiceCharge"]] = relationship(
        "ServiceCharge", back_populates="booking", cascade="all, delete-orphan"
    )
```
(Add this line inside the `Booking` class, after the existing relationships.)

- [ ] **Step 3.4 — Run tests to verify they pass**

```
pytest tests/unit/test_types.py -v
```
Expected: all tests PASS.

- [ ] **Step 3.5 — Commit**

```bash
git add travel_concierge/database/models.py tests/unit/test_types.py
git commit -m "feat: add Guest.preferences column and ServiceCharge ORM model"
```

---

## Task 4: Create room charge tools (TDD)

**Files:**
- Create: `travel_concierge/tools/room_charge.py`
- Create: `tests/unit/test_room_charge.py`

- [ ] **Step 4.1 — Write failing tests**

Create `tests/unit/test_room_charge.py`:

```python
"""Unit tests for room charge tools."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from travel_concierge.database.models import Base, Booking, Guest, Hotel, Room, BookingStatus, PaymentStatus
from travel_concierge.tools.room_charge import post_room_charge, get_room_charges


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def booking_id(db_engine):
    """Insert a minimal guest+hotel+room+booking and return the booking_id."""
    with Session(db_engine) as session:
        g = Guest(guest_id=str(uuid.uuid4()), first_name="A", last_name="B", email="a@b.com")
        session.add(g)
        session.flush()

        h = Hotel(hotel_id=str(uuid.uuid4()), name="H", address="1 St", city="C", country="US")
        session.add(h)
        session.flush()

        r = Room(room_id=str(uuid.uuid4()), hotel_id=h.hotel_id, room_type="King", price_per_night_usd=200)
        session.add(r)
        session.flush()

        b = Booking(
            booking_id=str(uuid.uuid4()),
            guest_id=g.guest_id,
            hotel_id=h.hotel_id,
            room_id=r.room_id,
            check_in_date=datetime(2026, 7, 1, tzinfo=timezone.utc),
            check_out_date=datetime(2026, 7, 5, tzinfo=timezone.utc),
            num_nights=4,
            total_price_usd=800,
        )
        session.add(b)
        session.commit()
        return b.booking_id


def test_post_room_charge_returns_service_charge(booking_id, db_engine):
    with patch("travel_concierge.tools.room_charge.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = lambda s: Session(db_engine)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = post_room_charge(
            booking_id=booking_id,
            service_type="dining",
            description="Club sandwich x2",
            amount_usd=38.0,
        )
    assert result["service_type"] == "dining"
    assert result["amount_usd"] == 38.0
    assert "charge_id" in result


def test_get_room_charges_empty(booking_id, db_engine):
    with patch("travel_concierge.tools.room_charge.get_session") as mock_get_session:
        mock_get_session.return_value.__enter__ = lambda s: Session(db_engine)
        mock_get_session.return_value.__exit__ = MagicMock(return_value=False)

        result = get_room_charges(booking_id=booking_id)
    assert result == []


def test_post_then_get_room_charges(booking_id, db_engine):
    session = Session(db_engine)

    def make_ctx():
        ctx = MagicMock()
        ctx.__enter__ = lambda s: session
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("travel_concierge.tools.room_charge.get_session", side_effect=make_ctx):
        post_room_charge(booking_id, "dining", "Breakfast", 25.0)
        post_room_charge(booking_id, "housekeeping", "Extra towels", 0.0)
        charges = get_room_charges(booking_id)

    assert len(charges) == 2
    assert charges[0]["service_type"] == "dining"
    assert charges[1]["service_type"] == "housekeeping"
```

- [ ] **Step 4.2 — Run tests to verify failure**

```
pytest tests/unit/test_room_charge.py -v
```
Expected: FAIL — `travel_concierge.tools.room_charge` not found.

- [ ] **Step 4.3 — Create tools/room_charge.py**

```python
"""Tools for posting and retrieving room charges during a guest's stay."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from travel_concierge.database.db import get_session
from travel_concierge.database.models import ServiceCharge

logger = logging.getLogger(__name__)


def post_room_charge(
    booking_id: str,
    service_type: str,
    description: str,
    amount_usd: float,
) -> dict:
    """Post a charge to the guest's room bill.

    Args:
        booking_id: The booking this charge belongs to.
        service_type: One of "dining", "housekeeping", or "local".
        description: Human-readable description, e.g. "Room service: club sandwich x2".
        amount_usd: Charge amount in USD.

    Returns:
        A dict with charge_id, service_type, description, amount_usd, posted_at.
    """
    charge_id = str(uuid.uuid4())
    posted_at = datetime.now(timezone.utc)

    with get_session() as session:
        charge = ServiceCharge(
            charge_id=charge_id,
            booking_id=booking_id,
            service_type=service_type,
            description=description,
            amount_usd=amount_usd,
            posted_at=posted_at,
        )
        session.add(charge)
        session.commit()

    logger.info("Posted %s charge %.2f for booking %s", service_type, amount_usd, booking_id)
    return {
        "charge_id": charge_id,
        "booking_id": booking_id,
        "service_type": service_type,
        "description": description,
        "amount_usd": amount_usd,
        "posted_at": posted_at.isoformat(),
    }


def get_room_charges(booking_id: str) -> list[dict]:
    """Retrieve all charges posted to a booking.

    Args:
        booking_id: The booking to retrieve charges for.

    Returns:
        List of charge dicts ordered by posted_at ascending.
    """
    with get_session() as session:
        rows = session.execute(
            select(ServiceCharge)
            .where(ServiceCharge.booking_id == booking_id)
            .order_by(ServiceCharge.posted_at)
        ).scalars().all()

        return [
            {
                "charge_id": r.charge_id,
                "booking_id": r.booking_id,
                "service_type": r.service_type,
                "description": r.description,
                "amount_usd": float(r.amount_usd),
                "posted_at": r.posted_at.isoformat(),
            }
            for r in rows
        ]
```

- [ ] **Step 4.4 — Run tests to verify they pass**

```
pytest tests/unit/test_room_charge.py -v
```
Expected: all 3 tests PASS.

- [ ] **Step 4.5 — Commit**

```bash
git add travel_concierge/tools/room_charge.py tests/unit/test_room_charge.py
git commit -m "feat: add post_room_charge and get_room_charges tools"
```

---

## Task 5: Create preference extraction tools (TDD)

**Files:**
- Create: `travel_concierge/tools/preferences.py`
- Create: `tests/unit/test_preferences.py`

- [ ] **Step 5.1 — Write failing tests**

Create `tests/unit/test_preferences.py`:

```python
"""Unit tests for preference extraction and persistence tools."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from travel_concierge.database.models import Base, Guest
from travel_concierge.tools.preferences import extract_preferences, update_guest_preferences


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def guest_id(db_engine):
    with Session(db_engine) as session:
        g = Guest(
            guest_id=str(uuid.uuid4()),
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        session.add(g)
        session.commit()
        return g.guest_id


# ── extract_preferences ────────────────────────────────────────────────────


def test_extract_preferences_returns_high_confidence(monkeypatch):
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {"field": "pillow_preference", "value": "feather", "confidence": "high"},
        {"field": "dietary_restrictions", "value": "vegan", "confidence": "medium"},
    ])

    with patch("travel_concierge.tools.preferences.genai.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        results = extract_preferences("I loved the feather pillows and the vegan breakfast")

    assert len(results) == 2
    assert results[0]["field"] == "pillow_preference"
    assert results[1]["confidence"] == "medium"


def test_extract_preferences_invalid_json_returns_empty(monkeypatch):
    mock_response = MagicMock()
    mock_response.text = "not json"

    with patch("travel_concierge.tools.preferences.genai.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        results = extract_preferences("some feedback")

    assert results == []


# ── update_guest_preferences ───────────────────────────────────────────────


def test_update_guest_preferences_writes_new(guest_id, db_engine):
    with patch("travel_concierge.tools.preferences.get_session") as mock_gs:
        session = Session(db_engine)
        mock_gs.return_value.__enter__ = lambda s: session
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        update_guest_preferences(guest_id, {"pillow_preference": "feather"})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)
        assert prefs["pillow_preference"] == "feather"


def test_update_guest_preferences_merges_without_overwriting_other_fields(guest_id, db_engine):
    session = Session(db_engine)

    def make_ctx():
        ctx = MagicMock()
        ctx.__enter__ = lambda s: session
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("travel_concierge.tools.preferences.get_session", side_effect=make_ctx):
        update_guest_preferences(guest_id, {"pillow_preference": "feather"})
        update_guest_preferences(guest_id, {"dietary_restrictions": ["vegan"]})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)

    assert prefs["pillow_preference"] == "feather"
    assert prefs["dietary_restrictions"] == ["vegan"]


def test_update_guest_preferences_overwrites_same_field(guest_id, db_engine):
    session = Session(db_engine)

    def make_ctx():
        ctx = MagicMock()
        ctx.__enter__ = lambda s: session
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("travel_concierge.tools.preferences.get_session", side_effect=make_ctx):
        update_guest_preferences(guest_id, {"pillow_preference": "foam"})
        update_guest_preferences(guest_id, {"pillow_preference": "feather"})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)

    assert prefs["pillow_preference"] == "feather"
```

- [ ] **Step 5.2 — Run tests to verify failure**

```
pytest tests/unit/test_preferences.py -v
```
Expected: FAIL — `travel_concierge.tools.preferences` not found.

- [ ] **Step 5.3 — Create tools/preferences.py**

```python
"""Tools for extracting and persisting guest preferences from free-text feedback."""

import json
import logging

from google import genai
from google.genai import types as genai_types
from sqlalchemy import select

from travel_concierge import MODEL
from travel_concierge.database.db import get_session
from travel_concierge.database.models import Guest
from travel_concierge.shared_libraries.types import ExtractedPreference

logger = logging.getLogger(__name__)


def extract_preferences(feedback_text: str) -> list[dict]:
    """Parse free-text guest feedback into structured preference field/value pairs.

    Uses Gemini controlled generation with ExtractedPreference output schema.
    Only the raw dicts are returned — confidence filtering happens in
    update_guest_preferences or in the calling agent.

    Args:
        feedback_text: Raw feedback from the guest, e.g. from post_stay conversation.

    Returns:
        List of dicts with keys: field, value, confidence.
        Returns [] on parse failure.
    """
    client = genai.Client()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                "Extract guest hotel stay preferences from the following feedback. "
                "Map them to structured fields such as pillow_preference, "
                "room_temperature_c, floor_preference, bed_type_preference, "
                "view_preference, or dietary_restrictions. "
                f"Feedback: {feedback_text}"
            ),
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[ExtractedPreference],
            ),
        )
        items = json.loads(response.text)
        return [
            {"field": p["field"], "value": p["value"], "confidence": p["confidence"]}
            for p in items
        ]
    except Exception as exc:
        logger.warning("extract_preferences failed to parse response: %s", exc)
        return []


def update_guest_preferences(guest_id: str, preferences: dict) -> dict:
    """Merge new preference values into the guest's stored preferences.

    Merge rule: provided values always overwrite the stored value for that field
    (most recent feedback wins). Fields absent from `preferences` are untouched.
    Never called with low-confidence values — that filtering is the caller's responsibility.

    Args:
        guest_id: The guest's DB ID.
        preferences: Dict of field → value to merge, e.g. {"pillow_preference": "feather"}.

    Returns:
        A dict with status and the updated preferences.
    """
    with get_session() as session:
        guest = session.execute(
            select(Guest).where(Guest.guest_id == guest_id)
        ).scalar_one_or_none()

        if guest is None:
            return {"status": f"Guest {guest_id} not found", "updated": {}}

        existing = json.loads(guest.preferences) if guest.preferences else {}
        existing.update(preferences)
        guest.preferences = json.dumps(existing)
        session.commit()

    logger.info("Updated preferences for guest %s: %s", guest_id, list(preferences.keys()))
    return {"status": "preferences updated", "updated": existing}
```

- [ ] **Step 5.4 — Run tests to verify they pass**

```
pytest tests/unit/test_preferences.py -v
```
Expected: all 4 tests PASS.

- [ ] **Step 5.5 — Commit**

```bash
git add travel_concierge/tools/preferences.py tests/unit/test_preferences.py
git commit -m "feat: add extract_preferences and update_guest_preferences tools"
```

---

## Task 6: Update policy files and callbacks

**Files:**
- Modify: `travel_concierge/hotel_policy/general_hotel_policy.md`
- Modify: `travel_concierge/hotel_policy/root_agent.md`
- Delete: `inspiration_agent.md`, `planning_agent.md`, `booking_agent.md`
- git mv: `pre_trip_agent.md` → `pre_stay_agent.md`, etc.
- Create: `dining_agent.md`, `housekeeping_agent.md`, `local_concierge_agent.md`, `stay_monitor_agent.md`
- Modify: `travel_concierge/hotel_policy/callbacks.py`

- [ ] **Step 6.1 — Rename existing policy files**

```bash
cd travel_concierge/hotel_policy
git mv pre_trip_agent.md pre_stay_agent.md
git mv in_trip_agent.md in_stay_agent.md
git mv post_trip_agent.md post_stay_agent.md
```

- [ ] **Step 6.2 — Update pre_stay_agent.md**

Replace contents of `travel_concierge/hotel_policy/pre_stay_agent.md`:

```markdown
# Pre-Stay Agent — Hotel Policy

## Role
Handles digital pre-arrival check-in for guests. Collects arrival time, room preferences, and special requests before the guest reaches the hotel.

## Policy Guidelines
- Collect arrival ETA, bed type, floor, view, pillow type, and room temperature preference.
- Confirm that collected preferences will be saved to personalise future stays before persisting them.
- Never pressure guests to provide preferences — all fields are optional.
- If a guest has existing saved preferences, surface them and ask if they still apply.
- Do not make guarantees about room assignments — clearly state requests are "noted" and subject to availability.
- Escalate accessibility or medical requirements immediately to a human concierge.
```

- [ ] **Step 6.3 — Update in_stay_agent.md**

Replace contents of `travel_concierge/hotel_policy/in_stay_agent.md`:

```markdown
# In-Stay Agent — Hotel Policy

## Role
Orchestrates all guest service requests during the active stay. Routes to dining, housekeeping, local concierge, or stay monitor sub-agents.

## Policy Guidelines
- Route dining requests (restaurant, room service) to dining_agent.
- Route housekeeping and maintenance requests to housekeeping_agent.
- Route transport and local area queries to local_concierge_agent.
- Route booking status and weather monitoring to stay_monitor_agent.
- All charges are posted to the room bill — never request payment from the guest directly during the stay.
- When a request is ambiguous, ask one clarifying question before routing.
- Maintain a warm, attentive tone consistent with IHG concierge standards.
```

- [ ] **Step 6.4 — Update post_stay_agent.md**

Replace contents of `travel_concierge/hotel_policy/post_stay_agent.md`:

```markdown
# Post-Stay Agent — Hotel Policy

## Role
Collects stay feedback, extracts and saves preferences, presents the final room bill, and confirms checkout.

## Policy Guidelines

### Feedback & Preference Extraction
- Before saving any extracted preferences, inform the guest: "Based on your feedback, we'd like to save your preferences for a more personalised future stay. Is that alright?"
- Only proceed with update_guest_preferences if the guest consents.
- Never surface or confirm low-confidence extractions back to the guest.
- If the guest explicitly says they don't want preferences saved, do not call update_guest_preferences.

### Billing & Checkout
- Present a clear itemised summary of all room charges before requesting settlement confirmation.
- Never omit charges from the bill summary.
- Do not pressure or rush the guest to confirm — allow time to review.
- After the guest confirms the bill, update the booking status to COMPLETED.

### Tone
- Thank the guest sincerely for their stay.
- Express that their feedback directly improves future experiences.
```

- [ ] **Step 6.5 — Update general_hotel_policy.md**

Replace full contents:

```markdown
# IHG Hotel Concierge Policy — All Agents

## Guest Interaction
- Always address guests professionally and warmly.
- Use the guest's name when a profile is available.
- Escalate complaints or sensitive requests to a human representative.

## Data & Privacy
- Guest data must only be used to personalize the current guest's experience.
- Never share, log, or expose payment card details or PII.
- Before saving guest preferences extracted from conversation, obtain explicit consent.
- Retain guest data only for the duration of the active session unless explicitly memorized or persisted with consent.

## Scope: In-Stay Focus
- This system handles the guest's experience from pre-arrival through post-departure.
- All bookings are assumed confirmed before the guest interacts with this system.
- All charges during the stay are posted to the room bill and settled at checkout.
- Never initiate pre-booking travel planning (flights, destination search) — that is out of scope.

## Information Accuracy
- Only present verified, up-to-date information.
- Clearly distinguish between "available", "noted", and "confirmed" at all times.

## Scope & Escalation
- Each agent must operate within its defined scope; do not perform actions belonging to another agent.
- When unable to resolve a request, provide a clear escalation path to a human concierge.
```

- [ ] **Step 6.6 — Update root_agent.md**

Update `travel_concierge/hotel_policy/root_agent.md` — remove the "Neutrality: Do not express preferences for specific hotels, destinations" line (no longer relevant) and replace with:

```markdown
# Root Agent — Hotel Policy & Code of Conduct

## Role
The root agent is the main orchestrator of the IHG Hotel Concierge. It receives all guest requests and routes them to the appropriate phase agent (pre_stay, in_stay, post_stay). It is the first and last point of contact for the guest.

## Hotel Policy Guidelines
- Always greet guests by name when a guest profile is available.
- Maintain a professional, warm, and helpful tone aligned with IHG brand standards.
- Never disclose internal system details, backend configurations, or room pricing algorithms to guests.
- All guest data accessed via `load_guest_profile` must be used solely to personalize the guest's experience.
- Escalate any complaints or sensitive requests (e.g., accessibility needs, medical concerns) to a human representative immediately.
- Do not make commitments (e.g., guaranteed upgrades, price matches) outside the scope of approved IHG policies.
- This system covers pre-arrival, in-stay, and post-stay only. Do not route to travel planning or flight booking.

## Code of Conduct
1. **Accuracy**: Only present information confirmed by a sub-agent or verified source. Do not speculate.
2. **Delegation**: Route requests to the most appropriate phase agent; do not attempt to fulfill tasks outside its own scope.
3. **Transparency**: Inform the guest when they are being routed to a specialized service.
4. **Privacy**: Handle all PII in accordance with IHG's data privacy standards.
5. **Escalation**: When unable to resolve a guest request, surface a clear escalation path rather than providing an incorrect answer.
```

- [ ] **Step 6.7 — Create dining_agent.md**

Create `travel_concierge/hotel_policy/dining_agent.md`:

```markdown
# Dining Agent — Hotel Policy

## Role
Handles hotel restaurant reservations and room service orders.

## Policy Guidelines
- Always cross-reference the guest's dietary_restrictions from their profile before confirming a menu or order.
- If a guest has a severe allergy, escalate immediately to a human staff member — do not attempt to confirm safety yourself.
- Clearly state whether a dining charge will be posted to the room bill before confirming the order.
- Do not confirm a restaurant reservation without first checking availability.
- Room service orders must include the room number before posting a charge.
```

- [ ] **Step 6.8 — Create housekeeping_agent.md**

Create `travel_concierge/hotel_policy/housekeeping_agent.md`:

```markdown
# Housekeeping Agent — Hotel Policy

## Role
Handles room service requests, extra amenities, and maintenance issues.

## Policy Guidelines
- Acknowledge every request and provide an estimated response time.
- Escalate maintenance issues (plumbing, electrical, safety) to hotel engineering staff immediately — do not attempt to troubleshoot.
- Most housekeeping requests are complimentary; only post a charge for chargeable items (e.g., laundry service) after clearly informing the guest.
- Never enter a guest's room without explicit consent for non-emergency requests.
```

- [ ] **Step 6.9 — Create local_concierge_agent.md**

Create `travel_concierge/hotel_policy/local_concierge_agent.md`:

```markdown
# Local Concierge Agent — Hotel Policy

## Role
Provides transport options and local area restaurant/attraction recommendations.

## Policy Guidelines
- All recommendations must be based on verified sources (Google Search or Maps grounding).
- Clearly disclose that local recommendations are not hotel-endorsed unless they are official hotel partners.
- When booking local tours or activities that carry a charge, post to the room bill and inform the guest of the amount before confirming.
- For transport, always provide estimated travel time and the guest's hotel address as the origin.
- Do not book transport services that cannot be verified or that require payment outside the room-charge system.
```

- [ ] **Step 6.10 — Create stay_monitor_agent.md**

Create `travel_concierge/hotel_policy/stay_monitor_agent.md`:

```markdown
# Stay Monitor Agent — Hotel Policy

## Role
Monitors local tour/activity booking statuses and weather impacts on outdoor activities.

## Policy Guidelines
- Surface issues proactively — do not wait for the guest to ask.
- Provide a concise, actionable summary: what changed and what the guest should do.
- For cancelled or disrupted bookings, suggest alternatives before presenting the issue.
- Escalate to a human concierge if a monitored issue requires hotel intervention.
- After delivering the monitor summary, transfer control back to in_stay_agent.
```

- [ ] **Step 6.11 — Update callbacks.py**

Replace the full contents of `travel_concierge/hotel_policy/callbacks.py`:

```python
"""Per-agent before_model_callbacks that inject agent-specific hotel policies.

Design:
  - Each function injects the policy for its designated agent domain.
  - Functions match ADK's BeforeModelCallback protocol and return None.
  - Sub-agents in the same domain share their parent's callback.

Execution order (ADK):
  HotelPolicyPlugin.before_model_callback  (general policy, runs first)
      └── <this callback>                  (agent-specific policy, runs second)
"""

from pathlib import Path
from typing import Optional

from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

_DIR = Path(__file__).parent


def _load(filename: str) -> str:
    return (_DIR / filename).read_text(encoding="utf-8")


_ROOT_POLICY       = _load("root_agent.md")
_PRE_STAY_POLICY   = _load("pre_stay_agent.md")
_IN_STAY_POLICY    = _load("in_stay_agent.md")
_POST_STAY_POLICY  = _load("post_stay_agent.md")
_DINING_POLICY     = _load("dining_agent.md")
_HOUSEKEEPING_POLICY = _load("housekeeping_agent.md")
_LOCAL_CONCIERGE_POLICY = _load("local_concierge_agent.md")
_STAY_MONITOR_POLICY = _load("stay_monitor_agent.md")


async def root_agent_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_ROOT_POLICY])
    return None


async def pre_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_PRE_STAY_POLICY])
    return None


async def in_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_IN_STAY_POLICY])
    return None


async def post_stay_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_POST_STAY_POLICY])
    return None


async def dining_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_DINING_POLICY])
    return None


async def housekeeping_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_HOUSEKEEPING_POLICY])
    return None


async def local_concierge_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_LOCAL_CONCIERGE_POLICY])
    return None


async def stay_monitor_policy_callback(
    callback_context: CallbackContext,
    llm_request: LlmRequest,
) -> Optional[LlmResponse]:
    llm_request.append_instructions([_STAY_MONITOR_POLICY])
    return None
```

- [ ] **Step 6.12 — Delete removed policy files**

```bash
git rm travel_concierge/hotel_policy/inspiration_agent.md
git rm travel_concierge/hotel_policy/planning_agent.md
git rm travel_concierge/hotel_policy/booking_agent.md
```

- [ ] **Step 6.13 — Commit all policy changes**

```bash
git add travel_concierge/hotel_policy/
git commit -m "feat: update hotel policy files and callbacks for hotel concierge"
```

---

## Task 7: Build pre_stay agent

**Files:**
- git mv: `sub_agents/pre_trip/` → `sub_agents/pre_stay/`

- [ ] **Step 7.1 — Rename the directory**

```bash
git mv travel_concierge/sub_agents/pre_trip travel_concierge/sub_agents/pre_stay
```

- [ ] **Step 7.2 — Replace pre_stay/prompt.py**

```python
"""Prompts for the pre_stay agent."""

PRE_STAY_AGENT_INSTR = """
You are a hotel pre-arrival concierge. You help guests prepare for their upcoming stay.

The guest's confirmed stay:
<stay_record>
{stay_record}
</stay_record>

The guest's profile:
<user_profile>
{user_profile}
</user_profile>

If stay_record is empty, inform the guest that you need a confirmed booking on file and
ask them to contact the front desk. Do not proceed further.

Your goal is to collect digital check-in information. Ask the guest about the following,
one at a time — do not ask multiple questions at once:

1. Expected arrival time (check-in is at {stay_check_in_date}, standard time in stay_record)
2. Bed type preference (if not already in profile)
3. Floor preference — high floor, low floor, or no preference
4. View preference — ocean, city, garden, or no preference
5. Pillow preference — feather, foam, firm, or no preference
6. Room temperature preference in Celsius

For each preference collected:
- Store it in session state using the `memorize` tool with a clear key (e.g. "arrival_eta", "pillow_preference").
- After all preferences are collected, call `update_guest_preferences` with the guest_id from the profile
  and a dict of all collected preferences.
- Before calling `update_guest_preferences`, inform the guest:
  "We'd like to save these preferences to personalise your future stays. Is that alright?"
- Only call `update_guest_preferences` if the guest consents.

Current time: {_time}
"""
```

- [ ] **Step 7.3 — Replace pre_stay/agent.py**

```python
"""Pre-stay agent: digital check-in and preference collection before arrival."""

from google.adk.agents import Agent

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import pre_stay_policy_callback
from travel_concierge.sub_agents.pre_stay import prompt
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.preferences import update_guest_preferences

pre_stay_agent = Agent(
    model=MODEL,
    name="pre_stay_agent",
    description="Collects digital check-in information and room preferences before the guest arrives.",
    instruction=prompt.PRE_STAY_AGENT_INSTR,
    tools=[memorize, update_guest_preferences],
    before_model_callback=pre_stay_policy_callback,
)
```

- [ ] **Step 7.4 — Update pre_stay/__init__.py**

Replace the contents of `travel_concierge/sub_agents/pre_stay/__init__.py` with an empty file (or keep as-is if it was already empty). Verify there are no old `pre_trip` references:

```bash
grep -r "pre_trip" travel_concierge/sub_agents/pre_stay/
```
Expected: no output.

- [ ] **Step 7.5 — Commit**

```bash
git add travel_concierge/sub_agents/pre_stay/
git commit -m "feat: build pre_stay agent with digital check-in flow"
```

---

## Task 8: Build in_stay agent with four sub-agents

**Files:**
- git mv: `sub_agents/in_trip/` → `sub_agents/in_stay/`

- [ ] **Step 8.1 — Rename the directory**

```bash
git mv travel_concierge/sub_agents/in_trip travel_concierge/sub_agents/in_stay
```

- [ ] **Step 8.2 — Replace in_stay/tools.py**

The transit_coordination function and itinerary parsing are removed. Keep only the monitoring tools:

```python
"""Tools for stay_monitor_agent: activity booking checks and weather impact."""


def event_booking_check(event_name: str, event_date: str, event_location: str) -> dict:
    """Check the status of a booked local tour or activity.

    Args:
        event_name: Name of the tour or activity.
        event_date: Date of the event in YYYY-MM-DD format.
        event_location: Location or venue name.

    Returns:
        A dict with a "status" key describing the booking state.
    """
    print("Checking", event_name, event_date, event_location)
    return {"status": f"{event_name}: confirmed"}


def weather_impact_check(
    activity_name: str, activity_date: str, activity_location: str
) -> dict:
    """Check weather impact on an outdoor activity.

    Args:
        activity_name: Name of the outdoor activity.
        activity_date: Date of the activity in YYYY-MM-DD format.
        activity_location: Location of the activity.

    Returns:
        A dict with a "status" key describing any weather risk.
    """
    print("Checking weather for", activity_name, activity_date, activity_location)
    return {"status": f"{activity_name}: no weather disruption expected"}
```

- [ ] **Step 8.3 — Replace in_stay/prompt.py**

```python
"""Prompts for in_stay_agent and its sub-agents."""

IN_STAY_AGENT_INSTR = """
You are an in-stay hotel concierge. You help guests with all needs during their active stay.

The guest's stay:
<stay_record>
{stay_record}
</stay_record>

The guest's profile:
<user_profile>
{user_profile}
</user_profile>

Route guest requests as follows:
- Dining requests (restaurant reservation, room service, food questions) → transfer to `dining_agent`
- Housekeeping requests (extra towels, pillows, maintenance, room refresh) → transfer to `housekeeping_agent`
- Transport, local restaurants, attractions, tours → transfer to `local_concierge_agent`
- Booking status checks or weather impact on activities → call `trip_monitor_agent` (or instruct with "monitor")

When a request is ambiguous, ask one clarifying question before routing.
All charges are posted to the room bill — do not request payment.

Current time: {_time}
"""

DINING_AGENT_INSTR = """
You are the hotel dining concierge. You handle restaurant reservations and room service orders.

The guest's profile (check dietary_restrictions before confirming any order):
<user_profile>
{user_profile}
</user_profile>

Stay details (use booking_id when posting charges):
<stay_record>
{stay_record}
</stay_record>

For restaurant reservations:
- Confirm date, time, party size, and any dietary requirements.
- Check against the guest profile for dietary_restrictions.
- Confirm the reservation and note it in session state using `memorize`.
- Restaurant reservations at hotel restaurants are complimentary to book — no charge to post.

For room service orders:
- Confirm the items and the guest's room number.
- If a charge applies, state the amount before confirming: "This will be posted to your room bill."
- Call `post_room_charge` with service_type="dining" after confirmation.

Current time: {_time}
"""

HOUSEKEEPING_AGENT_INSTR = """
You are the hotel housekeeping concierge. You handle room requests and maintenance issues.

Stay details (use booking_id when posting charges):
<stay_record>
{stay_record}
</stay_record>

For standard requests (extra towels, pillows, amenities):
- Acknowledge the request and provide an estimated delivery time (typically 15-20 minutes).
- Standard amenity requests are complimentary — do not post a charge.
- Use `memorize` to note the request.

For chargeable services (laundry, dry cleaning):
- Inform the guest of the charge before confirming: "This will be posted to your room bill."
- Call `post_room_charge` with service_type="housekeeping" after confirmation.

For maintenance issues:
- Escalate immediately: "I'm escalating this to our engineering team right away. Someone will be with you shortly."
- Do not attempt to troubleshoot. Do not post charges for maintenance.

Current time: {_time}
"""

LOCAL_CONCIERGE_AGENT_INSTR = """
You are the hotel local area concierge. You help guests with transport and local recommendations.

The guest's hotel address (use as origin for all directions):
<stay_record>
{stay_record}
</stay_record>

For transport queries:
- Provide estimated travel time and recommended transport mode.
- Suggest taxi/rideshare pickup points near the hotel entrance.
- For airport trips, recommend adding 30 minutes buffer for security.

For local restaurant and attraction recommendations:
- Use `google_search_grounding` or the Google Maps tool to find verified options.
- Disclose: "These are local recommendations and are not hotel-endorsed unless noted."
- Tailor suggestions to the guest's dietary_restrictions from their profile when relevant.

For local tour bookings:
- State the cost before confirming: "This will be posted to your room bill."
- Call `post_room_charge` with service_type="local" after the guest confirms.

Current time: {_time}
"""

STAY_MONITOR_INSTR = """
You monitor the guest's booked local activities and flag any issues that need attention.

The guest's stay:
<stay_record>
{stay_record}
</stay_record>

Steps:
1. Check each booked local activity using `event_booking_check`.
2. For outdoor activities, check weather risk using `weather_impact_check`.
3. Summarise any issues: what changed and what the guest should do.
4. If no issues found, briefly confirm everything looks good.
5. Transfer back to `in_stay_agent` after delivering the summary.

Current time: {_time}
"""
```

- [ ] **Step 8.4 — Replace in_stay/agent.py**

```python
"""In-stay agent: orchestrates dining, housekeeping, local concierge, and monitoring."""

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import (
    dining_policy_callback,
    housekeeping_policy_callback,
    in_stay_policy_callback,
    local_concierge_policy_callback,
    stay_monitor_policy_callback,
)
from travel_concierge.sub_agents.in_stay import prompt
from travel_concierge.sub_agents.in_stay.tools import event_booking_check, weather_impact_check
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.places import get_places_toolset
from travel_concierge.tools.room_charge import get_room_charges, post_room_charge
from travel_concierge.tools.search import google_search_grounding

try:
    _places_toolset = get_places_toolset()
    _maps_tools = [_places_toolset]
except EnvironmentError:
    _maps_tools = []

dining_agent = Agent(
    model=MODEL,
    name="dining_agent",
    description="Hotel dining concierge: restaurant reservations and room service orders.",
    instruction=prompt.DINING_AGENT_INSTR,
    tools=[post_room_charge, memorize],
    before_model_callback=dining_policy_callback,
)

housekeeping_agent = Agent(
    model=MODEL,
    name="housekeeping_agent",
    description="Hotel housekeeping concierge: room requests, amenities, and maintenance.",
    instruction=prompt.HOUSEKEEPING_AGENT_INSTR,
    tools=[post_room_charge, memorize],
    before_model_callback=housekeeping_policy_callback,
)

local_concierge_agent = Agent(
    model=MODEL,
    name="local_concierge_agent",
    description="Local area concierge: transport options and local restaurant/attraction recommendations.",
    instruction=prompt.LOCAL_CONCIERGE_AGENT_INSTR,
    tools=[google_search_grounding, post_room_charge, memorize, *_maps_tools],
    before_model_callback=local_concierge_policy_callback,
)

stay_monitor_agent = Agent(
    model=MODEL,
    name="stay_monitor_agent",
    description="Monitors local activity bookings and weather impact for the guest's stay.",
    instruction=prompt.STAY_MONITOR_INSTR,
    tools=[event_booking_check, weather_impact_check],
    output_key="stay_monitor_summary",
    before_model_callback=stay_monitor_policy_callback,
)

in_stay_agent = Agent(
    model=MODEL,
    name="in_stay_agent",
    description="In-stay hotel concierge: routes guest requests during their active stay.",
    instruction=prompt.IN_STAY_AGENT_INSTR,
    sub_agents=[stay_monitor_agent],
    tools=[
        AgentTool(agent=dining_agent),
        AgentTool(agent=housekeeping_agent),
        AgentTool(agent=local_concierge_agent),
        get_room_charges,
        memorize,
    ],
    before_model_callback=in_stay_policy_callback,
)
```

- [ ] **Step 8.5 — Verify no old in_trip references remain in the directory**

```bash
grep -r "in_trip\|day_of_agent\|trip_monitor\|transit_coordination\|find_segment" travel_concierge/sub_agents/in_stay/
```
Expected: no output.

- [ ] **Step 8.6 — Commit**

```bash
git add travel_concierge/sub_agents/in_stay/
git commit -m "feat: build in_stay agent with dining, housekeeping, local concierge and monitor sub-agents"
```

---

## Task 9: Build post_stay agent

**Files:**
- git mv: `sub_agents/post_trip/` → `sub_agents/post_stay/`

- [ ] **Step 9.1 — Rename the directory**

```bash
git mv travel_concierge/sub_agents/post_trip travel_concierge/sub_agents/post_stay
```

- [ ] **Step 9.2 — Replace post_stay/prompt.py**

```python
"""Prompts for the post_stay agent."""

POST_STAY_AGENT_INSTR = """
You are a hotel post-stay concierge. You collect stay feedback, extract guest preferences,
present the final room bill, and confirm checkout.

The guest's stay:
<stay_record>
{stay_record}
</stay_record>

The guest's profile:
<user_profile>
{user_profile}
</user_profile>

Follow this exact sequence:

## Step 1 — Collect Feedback
Open with warm thanks and ask the guest about their stay. Use questions like:
- "How was your overall experience?"
- "Was there anything about the room that could have been better?"
- "How did you find the dining options?"
- "Is there anything we should know for your next visit?"

Allow the guest to share as much or as little as they want.

## Step 2 — Extract and Save Preferences
Once feedback is collected:
1. Call `extract_preferences` with the full feedback text.
2. From the results, filter to only high and medium confidence items. Discard low confidence.
3. If any high/medium confidence items exist:
   - Say: "Based on your feedback, we'd like to note a few preferences for your next stay: [list them].
     Is it alright if we save these to your profile?"
   - If the guest consents, call `update_guest_preferences` with the guest_id from user_profile
     and a dict of the filtered preferences.
   - If the guest declines, skip `update_guest_preferences`.

## Step 3 — Present Bill
Call `get_room_charges` with the booking_id from stay_record.
Present an itemised summary:
  - Each charge: service type, description, amount
  - Total amount
Example:
  "Here is a summary of your room charges:
   - Dining: Club sandwich x2 — $38.00
   - Local: City tour booking — $75.00
   Total: $113.00"

## Step 4 — Confirm Checkout
Ask: "Does everything look correct on your bill?"
When the guest confirms, call `update_booking` to set status to "completed".
Then thank the guest sincerely and wish them a safe journey.

Current time: {_time}
"""
```

- [ ] **Step 9.3 — Replace post_stay/agent.py**

```python
"""Post-stay agent: feedback, preference extraction, billing, and checkout."""

from google.adk.agents import Agent

from travel_concierge import MODEL
from travel_concierge.hotel_policy.callbacks import post_stay_policy_callback
from travel_concierge.sub_agents.post_stay import prompt
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.preferences import extract_preferences, update_guest_preferences
from travel_concierge.tools.room_charge import get_room_charges

post_stay_agent = Agent(
    model=MODEL,
    name="post_stay_agent",
    description="Post-stay concierge: collects feedback, extracts preferences, presents bill, confirms checkout.",
    instruction=prompt.POST_STAY_AGENT_INSTR,
    tools=[
        extract_preferences,
        update_guest_preferences,
        get_room_charges,
        memorize,
    ],
    before_model_callback=post_stay_policy_callback,
)
```

- [ ] **Step 9.4 — Verify no old post_trip references remain**

```bash
grep -r "post_trip\|inspiration_agent\|itinerary" travel_concierge/sub_agents/post_stay/
```
Expected: no output.

- [ ] **Step 9.5 — Commit**

```bash
git add travel_concierge/sub_agents/post_stay/
git commit -m "feat: build post_stay agent with feedback, preference extraction, and checkout flow"
```

---

## Task 10: Rewire root agent and delete pre-booking agents

> **Ordering note:** Complete Steps 11.1 and 11.2 (memory.py update + profile JSON) BEFORE Step 10.2 (agent.py). `agent.py` imports `_load_precreated_stay` which is defined in memory.py in Task 11.

**Files:**
- Modify: `travel_concierge/prompt.py`
- Modify: `travel_concierge/agent.py`
- Delete: `sub_agents/inspiration/`, `sub_agents/planning/`, `sub_agents/booking/`

- [ ] **Step 10.1 — Update prompt.py (root agent instruction)**

Replace the full contents of `travel_concierge/prompt.py`:

```python
"""Root agent instruction for the IHG Hotel Concierge."""

ROOT_AGENT_INSTR = """
You are an IHG Hotel Concierge agent.
You help guests through every phase of their hotel stay: pre-arrival, in-stay, and post-stay.

## Greeting and login
- At the very start of the conversation, warmly greet the guest and ask for their
  **first name, last name, and email address** to personalise their experience.
- As soon as the guest provides all three, call `load_guest_profile` with those values.
- Display the message returned by the tool verbatim.
- If the guest has confirmed bookings, briefly list each one:
  hotel name, check-in/check-out dates, number of nights, and booking status.
- If no bookings are found, welcome them and offer to connect them with the reservations team.
- Do NOT skip or defer this step — always call `load_guest_profile` before anything else.

## Routing by stay phase
Determine the stay phase from the stay_record dates vs. the current time.
<stay_record>
{stay_record}
</stay_record>

Current time: {_time}

- If current time is **before** check-in date ({stay_check_in_date}): route to `pre_stay_agent`.
- If current time is **between** check-in ({stay_check_in_date}) and check-out ({stay_check_out_date}): route to `in_stay_agent`.
- If current time is **after** check-out date ({stay_check_out_date}): route to `post_stay_agent`.
- If stay_record is empty (no confirmed booking): inform the guest and offer to connect them with the reservations desk.

## General routing
- Pre-arrival questions (check-in prep, room preferences, arrival time) → `pre_stay_agent`
- In-stay requests (dining, housekeeping, local area, transport) → `in_stay_agent`
- Post-stay matters (feedback, bill review, checkout) → `post_stay_agent`

Current guest profile:
<user_profile>
{user_profile}
</user_profile>
"""
```

- [ ] **Step 10.2 — Update agent.py (root agent wiring)**

Replace the full contents of `travel_concierge/agent.py`:

```python
"""IHG Hotel Concierge — root agent and app initialisation."""

import uuid

from google.adk.agents import Agent
from google.adk.apps import App
from openinference.instrumentation import using_session

from travel_concierge import prompt
from travel_concierge.hotel_policy.callbacks import root_agent_policy_callback
from travel_concierge.hotel_policy.plugin import HotelPolicyPlugin
from travel_concierge.sub_agents.in_stay.agent import in_stay_agent
from travel_concierge.sub_agents.post_stay.agent import post_stay_agent
from travel_concierge.sub_agents.pre_stay.agent import pre_stay_agent
from travel_concierge.tools.memory import _load_precreated_stay
from travel_concierge.tools.profile import load_guest_profile
from travel_concierge.tracing import instrument_adk_with_arize

from . import MODEL

_ = instrument_adk_with_arize()


with using_session(session_id=str(uuid.uuid4())):
    root_agent = Agent(
        model=MODEL,
        name="root_agent",
        description="IHG Hotel Concierge — guides guests through pre-arrival, in-stay, and post-stay.",
        instruction=prompt.ROOT_AGENT_INSTR,
        tools=[load_guest_profile],
        sub_agents=[
            pre_stay_agent,
            in_stay_agent,
            post_stay_agent,
        ],
        before_agent_callback=_load_precreated_stay,
        before_model_callback=root_agent_policy_callback,
    )

app = App(root_agent=root_agent, name="hotel_concierge", plugins=[HotelPolicyPlugin()])
```

- [ ] **Step 10.3 — Delete the pre-booking agent directories**

```bash
git rm -r travel_concierge/sub_agents/inspiration
git rm -r travel_concierge/sub_agents/planning
git rm -r travel_concierge/sub_agents/booking
```

- [ ] **Step 10.4 — Commit**

```bash
git add travel_concierge/prompt.py travel_concierge/agent.py
git commit -m "feat: rewire root agent for hotel concierge and remove pre-booking agents"
```

---

## Task 11: Update memory helpers, default profile, and fix tests

**Files:**
- Modify: `travel_concierge/tools/memory.py`
- Create: `travel_concierge/profiles/stay_empty_default.json`
- Modify: `tests/unit/test_tools.py`

- [ ] **Step 11.1 — Update memory.py**

Replace `_set_initial_states` and `_load_precreated_itinerary` (rename to `_load_precreated_stay`) in `travel_concierge/tools/memory.py`. Update the imports and SAMPLE_SCENARIO_PATH, and replace both functions:

```python
SAMPLE_SCENARIO_PATH = os.getenv(
    "HOTEL_CONCIERGE_SCENARIO",
    "travel_concierge/profiles/stay_empty_default.json",
)
```

Replace `_set_initial_states`:

```python
def _set_initial_states(source: dict[str, Any], target: State | dict[str, Any]):
    """Set initial session state from a JSON scenario file."""
    if constants.SYSTEM_TIME not in target:
        target[constants.SYSTEM_TIME] = str(datetime.now())

    if constants.STAY_INITIALIZED not in target:
        target[constants.STAY_INITIALIZED] = True
        target.update(source)

        stay = source.get(constants.STAY_KEY, {})
        if stay:
            target[constants.STAY_CHECK_IN] = stay.get("check_in_date", "")
            target[constants.STAY_CHECK_OUT] = stay.get("check_out_date", "")
```

Replace `_load_precreated_itinerary` with `_load_precreated_stay`:

```python
def _load_precreated_stay(callback_context: CallbackContext):
    """Load the initial session state from the scenario JSON file.

    Set this as before_agent_callback on root_agent.
    """
    data = {}
    with open(SAMPLE_SCENARIO_PATH) as file:
        data = json.load(file)
        print(f"\nLoading Initial State: {data}\n")

    _set_initial_states(data["state"], callback_context.state)
```

- [ ] **Step 11.2 — Create stay_empty_default.json**

Create `travel_concierge/profiles/stay_empty_default.json`:

```json
{
  "state": {
    "user_profile": {
      "dietary_restrictions": [],
      "special_requests": [],
      "pillow_preference": null,
      "room_temperature_c": null,
      "floor_preference": null,
      "bed_type_preference": null,
      "view_preference": null
    },
    "stay_record": {},
    "stay_check_in_date": "",
    "stay_check_out_date": "",
    "guest_bookings": []
  }
}
```

- [ ] **Step 11.3 — Fix test_tools.py**

The existing tests reference `inspiration_agent` and `poi_agent` which are deleted. Replace the file contents:

```python
"""Basic tests for individual tools."""

import unittest

import pytest
from dotenv import load_dotenv
from google.adk.agents.invocation_context import InvocationContext
from google.adk.artifacts import InMemoryArtifactService
from google.adk.sessions import InMemorySessionService
from google.adk.tools import ToolContext

from travel_concierge.agent import root_agent
from travel_concierge.tools.memory import memorize
from travel_concierge.tools.places import get_places_toolset


@pytest.fixture(scope="session", autouse=True)
def load_env():
    load_dotenv()


session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()


class TestMemoryTool(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.session = session_service.create_session_sync(
            app_name="hotel_concierge",
            user_id="guest0001",
        )
        self.invoc_context = InvocationContext(
            session_service=session_service,
            invocation_id="TEST-01",
            agent=root_agent,
            session=self.session,
        )
        self.tool_context = ToolContext(invocation_context=self.invoc_context)

    def test_memorize_stores_value(self):
        result = memorize(
            key="arrival_eta",
            value="15:30",
            tool_context=self.tool_context,
        )
        self.assertIn("status", result)
        self.assertEqual(self.tool_context.state["arrival_eta"], "15:30")


def test_maps_toolset_requires_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY", raising=False)
    with pytest.raises(EnvironmentError, match="GOOGLE_MAPS_API_KEY must be set"):
        get_places_toolset()


def test_maps_toolset_with_api_key(monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "test-key")
    toolset = get_places_toolset()
    assert toolset is not None
    from google.adk.tools.mcp_tool import McpToolset
    assert isinstance(toolset, McpToolset)
```

- [ ] **Step 11.4 — Run the full test suite**

```
pytest tests/unit/ -v
```
Expected: all tests PASS with no import errors.

- [ ] **Step 11.5 — Verify the package imports cleanly**

```
python -c "from travel_concierge.agent import root_agent; print('OK', root_agent.name)"
```
Expected output: `OK root_agent`

- [ ] **Step 11.6 — Commit**

```bash
git add travel_concierge/tools/memory.py travel_concierge/profiles/stay_empty_default.json tests/unit/test_tools.py
git commit -m "feat: update memory helpers and default scenario for hotel stay; fix tests"
```

---

## Final verification

- [ ] **Run full test suite one last time**

```
pytest tests/unit/ -v --tb=short
```
Expected: all tests green.

- [ ] **Verify no stale travel references remain in core source**

```bash
grep -r "inspiration_agent\|planning_agent\|booking_agent\|pre_trip\|in_trip\|post_trip\|itinerary_start_date\|itinerary_end_date\|ITIN_KEY" travel_concierge/ --include="*.py"
```
Expected: no output.

- [ ] **Final commit**

```bash
git add -A
git commit -m "chore: hotel concierge migration complete"
```
