"""Tools for loading a guest's profile and booking history into session state."""

import logging
from datetime import datetime, timezone

from google.adk.tools import ToolContext
from sqlalchemy import select

from travel_concierge.database.db import get_session
from travel_concierge.database.models import Booking, BookingStatus, Guest
from travel_concierge.shared_libraries import constants

logger = logging.getLogger(__name__)


def load_guest_profile(
    email: str,
    first_name: str,
    last_name: str,
    tool_context: ToolContext,
) -> dict:
    """Load a guest's profile and booking history from the database into session state.

    Call this once at the start of the conversation after the user provides
    their name and email address. The results are stored in session state so
    all agents can access them, and a formatted summary is returned for display.

    Args:
        email: The guest's email address (used as the unique identifier).
        first_name: The guest's first name.
        last_name: The guest's last name.
        tool_context: ADK tool context (injected automatically).

    Returns:
        A dict containing ``found`` (bool), ``guest`` info, and ``bookings``.
    """
    logger.info("load_guest_profile: email=%s", email)

    try:
        with get_session() as session:
            guest = session.execute(
                select(Guest).where(Guest.email == email)
            ).scalar_one_or_none()

            if guest is None:
                logger.info("load_guest_profile: new guest %s", email)
                # Store minimal profile so agents know the user's name/email
                _update_profile(tool_context, first_name, last_name, email)
                tool_context.state["guest_bookings"] = []
                return {
                    "found": False,
                    "guest": {
                        "name": f"{first_name} {last_name}",
                        "email": email,
                    },
                    "bookings": [],
                    "message": (
                        f"Welcome, {first_name}! No previous bookings found for "
                        f"{email}. How can I help you plan your next trip?"
                    ),
                }

            # Guest exists — load their bookings
            rows = session.execute(
                select(Booking)
                .where(Booking.guest_id == guest.guest_id)
                .order_by(Booking.check_in_date.desc())
            ).scalars().all()

            bookings = [
                {
                    "booking_id": b.booking_id,
                    "hotel_id": b.hotel_id,
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

            logger.info(
                "load_guest_profile: found guest_id=%s with %d bookings",
                guest.guest_id,
                len(bookings),
            )

            _update_profile(
                tool_context,
                guest.first_name,
                guest.last_name,
                guest.email,
                guest_id=guest.guest_id,
            )
            tool_context.state["guest_bookings"] = bookings
            _hydrate_stay_record(tool_context, rows)

            return {
                "found": True,
                "guest": {
                    "guest_id": guest.guest_id,
                    "name": f"{guest.first_name} {guest.last_name}",
                    "email": guest.email,
                    "phone": guest.phone,
                },
                "total_bookings": len(bookings),
                "bookings": bookings,
                "message": (
                    f"Welcome back, {guest.first_name}! "
                    + (
                        f"You have {len(bookings)} booking(s) on record."
                        if bookings
                        else "You have no previous bookings on record."
                    )
                ),
            }

    except Exception as exc:
        logger.error("load_guest_profile error for %s: %s", email, exc)
        return {"error": f"Could not load profile: {exc}"}


def _update_profile(
    tool_context: ToolContext,
    first_name: str,
    last_name: str,
    email: str,
    guest_id: str | None = None,
) -> None:
    """Merge name, email, and (when known) guest_id into user_profile state."""
    profile = tool_context.state.get(constants.PROF_KEY) or {}
    profile["name"] = f"{first_name} {last_name}"
    profile["email"] = email
    if guest_id is not None:
        profile["guest_id"] = guest_id
    tool_context.state[constants.PROF_KEY] = profile


def _hydrate_stay_record(tool_context: ToolContext, bookings: list[Booking]) -> None:
    """Populate stay_record in session state from the guest's active/upcoming CONFIRMED booking.

    Picks the currently active stay (check_in <= now <= check_out) first, then the
    nearest upcoming CONFIRMED booking. Does nothing if no suitable booking exists.
    """
    now_utc = datetime.now(timezone.utc)

    def _to_utc(dt: datetime) -> datetime:
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    best: Booking | None = None
    for b in bookings:
        if b.status != BookingStatus.CONFIRMED:
            continue
        ci = _to_utc(b.check_in_date)
        co = _to_utc(b.check_out_date)
        if ci <= now_utc <= co:
            best = b
            break
        if ci > now_utc:
            if best is None or _to_utc(best.check_in_date) > ci:
                best = b

    if best is None:
        return

    stay_record = {
        "hotel_name": best.hotel.name,
        "hotel_address": best.hotel.address,
        "room_type": best.room.room_type,
        "booking_id": best.booking_id,
        "check_in_date": best.check_in_date.strftime("%Y-%m-%d"),
        "check_out_date": best.check_out_date.strftime("%Y-%m-%d"),
        "check_in_time": best.hotel.check_in_time,
        "check_out_time": best.hotel.check_out_time,
        "arrival_eta": None,
        "num_nights": best.num_nights,
    }
    tool_context.state[constants.STAY_KEY] = stay_record
    tool_context.state[constants.STAY_CHECK_IN] = stay_record["check_in_date"]
    tool_context.state[constants.STAY_CHECK_OUT] = stay_record["check_out_date"]
    logger.info(
        "Hydrated stay_record from booking %s (check-in %s)",
        best.booking_id,
        stay_record["check_in_date"],
    )
