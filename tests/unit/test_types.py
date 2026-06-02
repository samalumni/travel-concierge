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
