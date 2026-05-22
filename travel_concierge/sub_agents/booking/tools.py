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

"""Database tools for the booking agent.

These tools persist confirmed booking information to the backend DB after
payment has been successfully processed.
"""

import logging
from datetime import datetime, timezone

from google.adk.tools import ToolContext
from sqlalchemy import select, and_
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

from travel_concierge.database.db import get_session
from travel_concierge.database.models import (
    Booking,
    BookingStatus,
    Guest,
    Hotel,
    Room,
    Guest,
    Hotel,
    PaymentStatus,
    Room,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD string into a timezone-aware datetime."""
    dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
    return dt.replace(tzinfo=timezone.utc)


def _get_or_create_guest(
    session,
    email: str,
    first_name: str,
    last_name: str,
    phone: str,
) -> Guest:
    guest = session.execute(
        select(Guest).where(Guest.email == email)
    ).scalar_one_or_none()
    if guest is None:
        logger.info("Creating new guest: %s", email)
        guest = Guest(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone or None,
        )
        session.add(guest)
        session.flush()  # populate guest_id
        logger.debug("New guest flushed with id=%s", guest.guest_id)
    else:
        logger.debug("Found existing guest id=%s for email=%s", guest.guest_id, email)
    return guest


def _get_or_create_hotel(
    session,
    name: str,
    address: str,
    city: str,
    country: str,
    check_in_time: str,
    check_out_time: str,
) -> Hotel:
    hotel = session.execute(
        select(Hotel).where(Hotel.name == name, Hotel.address == address)
    ).scalar_one_or_none()
    if hotel is None:
        logger.info("Creating new hotel: %s", name)
        hotel = Hotel(
            name=name,
            address=address,
            city=city or "Unknown",
            country=country or "Unknown",
            check_in_time=check_in_time or "15:00",
            check_out_time=check_out_time or "11:00",
        )
        session.add(hotel)
        session.flush()
        logger.debug("New hotel flushed with id=%s", hotel.hotel_id)
    else:
        logger.debug("Found existing hotel id=%s name=%s", hotel.hotel_id, name)
    return hotel


def _get_or_create_room(
    session,
    hotel_id: str,
    room_type: str,
    price_per_night_usd: float,
) -> Room:
    room = session.execute(
        select(Room).where(Room.hotel_id == hotel_id, Room.room_type == room_type)
    ).scalar_one_or_none()
    if room is None:
        logger.info("Creating new room: type=%s hotel_id=%s", room_type, hotel_id)
        room = Room(
            hotel_id=hotel_id,
            room_type=room_type,
            price_per_night_usd=price_per_night_usd,
        )
        session.add(room)
        session.flush()
        logger.debug("New room flushed with id=%s", room.room_id)
    else:
        logger.debug("Found existing room id=%s type=%s", room.room_id, room_type)
    return room


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------

def save_hotel_booking(
    booking_id: str,
    guest_email: str,
    guest_first_name: str,
    guest_last_name: str,
    hotel_name: str,
    hotel_address: str,
    room_type: str,
    check_in_date: str,
    check_out_date: str,
    total_price_usd: float,
    payment_method: str,
    tool_context: ToolContext,
    guest_phone: str = "",
    hotel_city: str = "",
    hotel_country: str = "",
    hotel_check_in_time: str = "15:00",
    hotel_check_out_time: str = "11:00",
    notes: str = "",
) -> dict:
    """Persist a confirmed hotel booking to the database.

    Call this tool immediately after ``process_payment`` returns a successful
    transaction for a hotel item.

    Args:
        booking_id: The reservation/order ID returned by ``process_payment``.
        guest_email: Traveler's email address (used as the unique guest key).
        guest_first_name: Traveler's first name.
        guest_last_name: Traveler's last name.
        hotel_name: Name of the hotel.
        hotel_address: Full address of the hotel.
        room_type: Room type selected, e.g. "King with Ocean View".
        check_in_date: Check-in date in YYYY-MM-DD format.
        check_out_date: Check-out date in YYYY-MM-DD format.
        total_price_usd: Total price paid (all nights combined).
        payment_method: Payment method used, e.g. "Google Pay".
        tool_context: ADK tool context (injected automatically).
        guest_phone: Traveler's phone number (optional).
        hotel_city: City where the hotel is located (optional).
        hotel_country: Country where the hotel is located (optional).
        hotel_check_in_time: Hotel's standard check-in time in HH:MM (optional).
        hotel_check_out_time: Hotel's standard check-out time in HH:MM (optional).
        notes: Any special requests or notes (optional).

    Returns:
        A dict with ``status`` and ``booking_id`` on success, or an ``error``
        key on failure.
    """
    logger.info(
        "save_hotel_booking called: booking_id=%s guest=%s hotel=%s",
        booking_id, guest_email, hotel_name,
    )
    try:
        check_in_dt = _parse_date(check_in_date)
        check_out_dt = _parse_date(check_out_date)
    except ValueError as exc:
        logger.warning("save_hotel_booking date parse error: %s", exc)
        return {"error": f"Invalid date format: {exc}. Use YYYY-MM-DD."}

    num_nights = (check_out_dt.date() - check_in_dt.date()).days
    if num_nights < 1:
        logger.warning("save_hotel_booking invalid dates: check_out <= check_in")
        return {"error": "check_out_date must be after check_in_date."}

    try:
        with get_session() as session:
            guest = _get_or_create_guest(
                session, guest_email, guest_first_name, guest_last_name, guest_phone
            )
            hotel = _get_or_create_hotel(
                session,
                hotel_name,
                hotel_address,
                hotel_city,
                hotel_country,
                hotel_check_in_time,
                hotel_check_out_time,
            )
            price_per_night = round(total_price_usd / num_nights, 2)
            room = _get_or_create_room(
                session, hotel.hotel_id, room_type, price_per_night
            )

            # Check for duplicate booking
            existing = session.execute(
                select(Booking).where(Booking.booking_id == booking_id)
            ).scalar_one_or_none()
            if existing:
                logger.warning("save_hotel_booking: booking_id=%s already exists, skipping", booking_id)
                return {
                    "status": "already_saved",
                    "booking_id": booking_id,
                    "message": "Booking already exists in the database.",
                }

            booking = Booking(
                booking_id=booking_id,
                guest_id=guest.guest_id,
                hotel_id=hotel.hotel_id,
                room_id=room.room_id,
                check_in_date=check_in_dt,
                check_out_date=check_out_dt,
                num_nights=num_nights,
                total_price_usd=total_price_usd,
                status=BookingStatus.CONFIRMED,
                payment_method=payment_method,
                payment_status=PaymentStatus.PAID,
                notes=notes or None,
            )
            session.add(booking)
            logger.info(
                "Booking persisted: id=%s guest_id=%s hotel_id=%s nights=%d total=$%.2f",
                booking_id, guest.guest_id, hotel.hotel_id, num_nights, total_price_usd,
            )

    except SQLAlchemyError as exc:
        logger.error("save_hotel_booking DB error for booking_id=%s: %s", booking_id, exc)
        return {"error": f"Database error: {exc}"}

    return {
        "status": "saved",
        "booking_id": booking_id,
        "guest_id": guest.guest_id,
        "hotel_id": hotel.hotel_id,
        "room_id": room.room_id,
        "num_nights": num_nights,
        "message": f"Booking {booking_id} saved successfully.",
    }


def get_booking_status(booking_id: str, tool_context: ToolContext) -> dict:
    """Look up a booking in the database by its booking ID.

    Args:
        booking_id: The reservation/order ID to look up.
        tool_context: ADK tool context (injected automatically).

    Returns:
        A dict with booking details on success, or an ``error`` key if not found.
    """
    logger.debug("get_booking_status: booking_id=%s", booking_id)
    try:
        with get_session() as session:
            booking = session.execute(
                select(Booking).where(Booking.booking_id == booking_id)
            ).scalar_one_or_none()

            if booking is None:
                logger.warning("get_booking_status: booking_id=%s not found", booking_id)
                return {"error": f"No booking found with ID '{booking_id}'."}

            return {
                "booking_id": booking.booking_id,
                "status": booking.status.value,
                "payment_status": booking.payment_status.value,
                "guest_id": booking.guest_id,
                "hotel_id": booking.hotel_id,
                "room_id": booking.room_id,
                "check_in_date": booking.check_in_date.strftime("%Y-%m-%d"),
                "check_out_date": booking.check_out_date.strftime("%Y-%m-%d"),
                "num_nights": booking.num_nights,
                "total_price_usd": float(booking.total_price_usd),
                "payment_method": booking.payment_method,
            }
    except SQLAlchemyError as exc:
        logger.error("get_booking_status DB error booking_id=%s: %s", booking_id, exc)
        return {"error": f"Database error: {exc}"}


def get_guest_bookings(guest_email: str, tool_context: ToolContext) -> dict:
    """Retrieve all bookings for a guest identified by their email address.

    Args:
        guest_email: The guest's email address.
        tool_context: ADK tool context (injected automatically).

    Returns:
        A dict with a ``bookings`` list (may be empty) or an ``error`` key.
    """
    logger.debug("get_guest_bookings: email=%s", guest_email)
    try:
        with get_session() as session:
            guest = session.execute(
                select(Guest).where(Guest.email == guest_email)
            ).scalar_one_or_none()

            if guest is None:
                logger.warning("get_guest_bookings: no guest found for email=%s", guest_email)
                return {"error": f"No guest found with email '{guest_email}'."}

            rows = session.execute(
                select(Booking)
                .where(Booking.guest_id == guest.guest_id)
                .order_by(Booking.check_in_date.desc())
            ).scalars().all()

            bookings = [
                {
                    "booking_id": b.booking_id,
                    "hotel_id": b.hotel_id,
                    "room_id": b.room_id,
                    "check_in_date": b.check_in_date.strftime("%Y-%m-%d"),
                    "check_out_date": b.check_out_date.strftime("%Y-%m-%d"),
                    "num_nights": b.num_nights,
                    "total_price_usd": float(b.total_price_usd),
                    "status": b.status.value,
                    "payment_status": b.payment_status.value,
                    "payment_method": b.payment_method,
                }
                for b in rows
            ]
            logger.debug("get_guest_bookings: found %d bookings for guest_id=%s", len(bookings), guest.guest_id)
            return {
                "guest_id": guest.guest_id,
                "guest_name": f"{guest.first_name} {guest.last_name}",
                "total_bookings": len(bookings),
                "bookings": bookings,
            }
    except SQLAlchemyError as exc:
        logger.error("get_guest_bookings DB error email=%s: %s", guest_email, exc)
        return {"error": f"Database error: {exc}"}


def list_available_rooms(hotel_name: str, tool_context: ToolContext) -> dict:
    """List all currently available rooms for a hotel by name.

    Args:
        hotel_name: The name of the hotel to query.
        tool_context: ADK tool context (injected automatically).

    Returns:
        A dict with a ``rooms`` list or an ``error`` key.
    """
    logger.debug("list_available_rooms: hotel_name=%s", hotel_name)
    try:
        with get_session() as session:
            hotel = session.execute(
                select(Hotel).where(Hotel.name == hotel_name)
            ).scalar_one_or_none()

            if hotel is None:
                logger.warning("list_available_rooms: no hotel found for name=%s", hotel_name)
                return {"error": f"No hotel found with name '{hotel_name}'."}

            rows = session.execute(
                select(Room).where(
                    and_(Room.hotel_id == hotel.hotel_id, Room.is_available == True)  # noqa: E712
                )
            ).scalars().all()

            rooms = [
                {
                    "room_id": r.room_id,
                    "room_type": r.room_type,
                    "price_per_night_usd": float(r.price_per_night_usd),
                    "max_occupancy": r.max_occupancy,
                }
                for r in rows
            ]
            logger.debug("list_available_rooms: %d available rooms for hotel_id=%s", len(rooms), hotel.hotel_id)
            return {
                "hotel_id": hotel.hotel_id,
                "hotel_name": hotel.name,
                "address": hotel.address,
                "check_in_time": hotel.check_in_time,
                "check_out_time": hotel.check_out_time,
                "available_rooms": rooms,
            }
    except SQLAlchemyError as exc:
        logger.error("list_available_rooms DB error hotel=%s: %s", hotel_name, exc)
        return {"error": f"Database error: {exc}"}


def search_bookings(
    tool_context: ToolContext,
    status: str = "",
    check_in_after: str = "",
    check_in_before: str = "",
    hotel_name: str = "",
) -> dict:
    """Search bookings with optional filters.

    Args:
        tool_context: ADK tool context (injected automatically).
        status: Filter by booking status — one of: pending, confirmed,
            cancelled, completed. Leave empty to include all statuses.
        check_in_after: Return bookings with check-in on or after this date
            (YYYY-MM-DD). Leave empty for no lower bound.
        check_in_before: Return bookings with check-in on or before this date
            (YYYY-MM-DD). Leave empty for no upper bound.
        hotel_name: Filter by hotel name (exact match). Leave empty for all hotels.

    Returns:
        A dict with a ``bookings`` list and ``total`` count, or an ``error`` key.
    """
    logger.debug(
        "search_bookings: status=%r after=%r before=%r hotel=%r",
        status, check_in_after, check_in_before, hotel_name,
    )
    try:
        filters = []

        if status:
            try:
                filters.append(Booking.status == BookingStatus(status))
            except ValueError:
                valid = [s.value for s in BookingStatus]
                return {"error": f"Invalid status '{status}'. Valid values: {valid}"}

        if check_in_after:
            try:
                filters.append(Booking.check_in_date >= _parse_date(check_in_after))
            except ValueError:
                return {"error": f"Invalid check_in_after '{check_in_after}'. Use YYYY-MM-DD."}

        if check_in_before:
            try:
                filters.append(Booking.check_in_date <= _parse_date(check_in_before))
            except ValueError:
                return {"error": f"Invalid check_in_before '{check_in_before}'. Use YYYY-MM-DD."}

        with get_session() as session:
            if hotel_name:
                hotel = session.execute(
                    select(Hotel).where(Hotel.name == hotel_name)
                ).scalar_one_or_none()
                if hotel is None:
                    return {"error": f"No hotel found with name '{hotel_name}'."}
                filters.append(Booking.hotel_id == hotel.hotel_id)

            stmt = select(Booking).order_by(Booking.check_in_date.desc())
            if filters:
                stmt = stmt.where(and_(*filters))

            rows = session.execute(stmt).scalars().all()

            bookings = [
                {
                    "booking_id": b.booking_id,
                    "guest_id": b.guest_id,
                    "hotel_id": b.hotel_id,
                    "room_id": b.room_id,
                    "check_in_date": b.check_in_date.strftime("%Y-%m-%d"),
                    "check_out_date": b.check_out_date.strftime("%Y-%m-%d"),
                    "num_nights": b.num_nights,
                    "total_price_usd": float(b.total_price_usd),
                    "status": b.status.value,
                    "payment_status": b.payment_status.value,
                    "payment_method": b.payment_method,
                }
                for b in rows
            ]
            logger.debug("search_bookings: returned %d results", len(bookings))
            return {"total": len(bookings), "bookings": bookings}
    except SQLAlchemyError as exc:
        logger.error("search_bookings DB error: %s", exc)
        return {"error": f"Database error: {exc}"}


def update_booking(
    booking_id: str,
    tool_context: ToolContext,
    new_check_out_date: str = "",
    new_check_in_date: str = "",
    new_status: str = "",
    new_notes: str = "",
) -> dict:
    """Update an existing booking's dates, status, or notes.

    Use this tool to modify an existing reservation — for example when a guest
    wants to extend their stay, change dates, or cancel.  Do NOT use
    ``create_reservation`` for these modifications.

    Args:
        booking_id: The ID of the booking to update.
        tool_context: ADK tool context (injected automatically).
        new_check_out_date: New check-out date in YYYY-MM-DD format.
            Leave empty to keep the current date.
        new_check_in_date: New check-in date in YYYY-MM-DD format.
            Leave empty to keep the current date.
        new_status: New booking status — one of: pending, confirmed,
            cancelled, completed. Leave empty to keep the current status.
        new_notes: Replace the notes field. Leave empty to keep current notes.

    Returns:
        A dict with the updated booking details, or an ``error`` key.
    """
    logger.info(
        "update_booking: booking_id=%s check_in=%r check_out=%r status=%r",
        booking_id, new_check_in_date, new_check_out_date, new_status,
    )
    try:
        with get_session() as session:
            booking = session.execute(
                select(Booking).where(Booking.booking_id == booking_id)
            ).scalar_one_or_none()

            if booking is None:
                logger.warning("update_booking: booking_id=%s not found", booking_id)
                return {"error": f"No booking found with ID '{booking_id}'."}

            if booking.status == BookingStatus.CANCELLED:
                return {"error": f"Booking '{booking_id}' is cancelled and cannot be modified."}

            # Apply check-in change
            if new_check_in_date:
                try:
                    booking.check_in_date = _parse_date(new_check_in_date)
                except ValueError as exc:
                    return {"error": f"Invalid new_check_in_date: {exc}. Use YYYY-MM-DD."}

            # Apply check-out change
            if new_check_out_date:
                try:
                    booking.check_out_date = _parse_date(new_check_out_date)
                except ValueError as exc:
                    return {"error": f"Invalid new_check_out_date: {exc}. Use YYYY-MM-DD."}

            # Recalculate nights and total price whenever dates change
            if new_check_in_date or new_check_out_date:
                num_nights = (
                    booking.check_out_date.date() - booking.check_in_date.date()
                ).days
                if num_nights < 1:
                    return {"error": "new_check_out_date must be after new_check_in_date."}
                # Derive price per night from the current total / original nights
                if booking.num_nights and booking.num_nights > 0:
                    price_per_night = float(booking.total_price_usd) / booking.num_nights
                else:
                    price_per_night = float(booking.total_price_usd)
                booking.num_nights = num_nights
                booking.total_price_usd = round(price_per_night * num_nights, 2)

            # Apply status change
            if new_status:
                try:
                    booking.status = BookingStatus(new_status)
                except ValueError:
                    valid = [s.value for s in BookingStatus]
                    return {"error": f"Invalid status '{new_status}'. Valid values: {valid}"}

            # Apply notes change
            if new_notes:
                booking.notes = new_notes

            logger.info(
                "update_booking: updated booking_id=%s nights=%s total=%.2f status=%s",
                booking_id, booking.num_nights, float(booking.total_price_usd), booking.status.value,
            )

            return {
                "status": "updated",
                "booking_id": booking.booking_id,
                "check_in_date": booking.check_in_date.strftime("%Y-%m-%d"),
                "check_out_date": booking.check_out_date.strftime("%Y-%m-%d"),
                "num_nights": booking.num_nights,
                "total_price_usd": float(booking.total_price_usd),
                "booking_status": booking.status.value,
                "payment_status": booking.payment_status.value,
                "message": f"Booking {booking_id} updated successfully.",
            }

    except SQLAlchemyError as exc:
        logger.error("update_booking DB error booking_id=%s: %s", booking_id, exc)
        return {"error": f"Database error: {exc}"}
