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
    from travel_concierge.database.models import Hotel as HotelORM, Room as RoomORM

    guest = Guest(
        guest_id=str(uuid.uuid4()),
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
    )
    db_session.add(guest)
    db_session.flush()

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
