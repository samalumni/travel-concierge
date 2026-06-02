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
    field: str                  # e.g. "pillow_preference"
    value: str | list[str]      # list for multi-value fields like dietary_restrictions
    confidence: str             # "high" | "medium" | "low"


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
