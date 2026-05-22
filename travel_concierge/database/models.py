# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""SQLAlchemy ORM models for the Travel Concierge backend database.

Tables:
    guest   — traveler profile
    hotel   — hotel property
    room    — room type offered by a hotel
    booking — reservation linking a guest to a room
"""

import enum
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    String,
    Integer,
    Boolean,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


# ---------------------------------------------------------------------------
# Guest
# ---------------------------------------------------------------------------

class Guest(Base):
    """A registered traveler / user of the travel concierge."""

    __tablename__ = "guest"

    guest_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    bookings: Mapped[list["Booking"]] = relationship(
        "Booking", back_populates="guest", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Guest {self.guest_id!r} {self.email!r}>"


# ---------------------------------------------------------------------------
# Hotel
# ---------------------------------------------------------------------------

class Hotel(Base):
    """A hotel property available for booking."""

    __tablename__ = "hotel"

    hotel_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str] = mapped_column(String(500))
    city: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100))
    # Stored as "HH:MM", e.g. "16:00"
    check_in_time: Mapped[str] = mapped_column(String(5), default="15:00")
    check_out_time: Mapped[str] = mapped_column(String(5), default="11:00")
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    star_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    rooms: Mapped[list["Room"]] = relationship(
        "Room", back_populates="hotel", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="hotel")

    __table_args__ = (
        CheckConstraint("star_rating >= 1 AND star_rating <= 5", name="ck_hotel_star_rating"),
    )

    def __repr__(self) -> str:
        return f"<Hotel {self.hotel_id!r} {self.name!r}>"


# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------

class Room(Base):
    """A room type offered by a hotel."""

    __tablename__ = "room"

    room_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    hotel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("hotel.hotel_id", ondelete="CASCADE"), index=True
    )
    # e.g. "King with Ocean View", "Twin with Balcony", "Suite"
    room_type: Mapped[str] = mapped_column(String(100))
    price_per_night_usd: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    max_occupancy: Mapped[int] = mapped_column(Integer, default=2)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="rooms")
    bookings: Mapped[list["Booking"]] = relationship("Booking", back_populates="room")

    __table_args__ = (
        UniqueConstraint("hotel_id", "room_type", name="uq_room_hotel_type"),
        CheckConstraint("price_per_night_usd > 0", name="ck_room_positive_price"),
        CheckConstraint("max_occupancy >= 1", name="ck_room_min_occupancy"),
    )

    def __repr__(self) -> str:
        return f"<Room {self.room_id!r} {self.room_type!r} @ hotel {self.hotel_id!r}>"


# ---------------------------------------------------------------------------
# Booking
# ---------------------------------------------------------------------------

class Booking(Base):
    """A hotel reservation linking a guest to a specific room."""

    __tablename__ = "booking"

    # booking_id matches the `booking_id` field in HotelEvent / itinerary
    booking_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    guest_id: Mapped[str] = mapped_column(String(36), ForeignKey("guest.guest_id", ondelete="RESTRICT"), index=True)
    hotel_id: Mapped[str] = mapped_column(String(36), ForeignKey("hotel.hotel_id", ondelete="RESTRICT"), index=True)
    room_id: Mapped[str] = mapped_column(String(36), ForeignKey("room.room_id", ondelete="RESTRICT"), index=True)
    check_in_date: Mapped[datetime] = mapped_column()
    check_out_date: Mapped[datetime] = mapped_column()
    num_nights: Mapped[int] = mapped_column(Integer)
    total_price_usd: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[BookingStatus] = mapped_column(default=BookingStatus.PENDING)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    payment_status: Mapped[PaymentStatus] = mapped_column(default=PaymentStatus.PENDING)
    # Optional free-text notes (special requests, accessibility needs, etc.)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    guest: Mapped["Guest"] = relationship("Guest", back_populates="bookings")
    hotel: Mapped["Hotel"] = relationship("Hotel", back_populates="bookings")
    room: Mapped["Room"] = relationship("Room", back_populates="bookings")

    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date", name="ck_booking_dates"),
        CheckConstraint("num_nights >= 1", name="ck_booking_min_nights"),
        CheckConstraint("total_price_usd > 0", name="ck_booking_positive_total"),
    )

    def __repr__(self) -> str:
        return (
            f"<Booking {self.booking_id!r} guest={self.guest_id!r} "
            f"hotel={self.hotel_id!r} status={self.status}>"
        )
