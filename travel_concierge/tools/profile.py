"""Tools for loading a guest's profile and booking history into session state."""

import logging

from google.adk.tools import ToolContext
from sqlalchemy import select

from travel_concierge.database.db import get_session
from travel_concierge.database.models import Booking, Guest
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
            )
            tool_context.state["guest_bookings"] = bookings

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
) -> None:
    """Merge name and email into the existing user_profile state dict."""
    profile = tool_context.state.get(constants.PROF_KEY) or {}
    profile["name"] = f"{first_name} {last_name}"
    profile["email"] = email
    tool_context.state[constants.PROF_KEY] = profile
