"""Unit tests for room charge tools."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from travel_concierge.database.models import Base, Booking, Guest, Hotel, Room
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
