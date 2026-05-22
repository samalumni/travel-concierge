#!/usr/bin/env python3
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

"""Standalone CLI for querying the Travel Concierge backend database.

Usage examples
--------------
  # List all guests
  python travel_concierge/database/query_cli.py guests

  # Show all bookings for a guest
  python travel_concierge/database/query_cli.py guest-bookings --email alice@example.com

  # Show a single booking
  python travel_concierge/database/query_cli.py booking --id <booking_id>

  # List all hotels
  python travel_concierge/database/query_cli.py hotels

  # List rooms at a hotel (add --available-only to filter)
  python travel_concierge/database/query_cli.py rooms --hotel "Grand Hyatt Seattle"
  python travel_concierge/database/query_cli.py rooms --hotel "Grand Hyatt Seattle" --available-only

  # Search bookings with filters
  python travel_concierge/database/query_cli.py search-bookings \\
      --status confirmed --after 2026-01-01 --before 2026-12-31 --hotel "Grand Hyatt Seattle"

  # Also runnable as a module from the project root:
  python -m travel_concierge.database.query_cli hotels

  # Override the database URL (defaults to sqlite:///travel_concierge.db)
  DATABASE_URL=postgresql+psycopg2://user:pw@host/db python travel_concierge/database/query_cli.py guests
"""

# ---------------------------------------------------------------------------
# Path bootstrap — allows running the script directly from any working
# directory without needing to install the package:
#   python /path/to/travel_concierge/database/query_cli.py hotels
# ---------------------------------------------------------------------------
import os
import sys

_PROJECT_ROOT = os.path.dirname(        # .../deploy-travel-concierge
    os.path.dirname(                    # .../travel_concierge
        os.path.dirname(                # .../database
            os.path.abspath(__file__)
        )
    )
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Standard imports (after path is set)
# ---------------------------------------------------------------------------
import argparse
import json
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import and_, select

from travel_concierge.database.db import get_session, init_db
from travel_concierge.database.models import (
    Booking,
    BookingStatus,
    Guest,
    Hotel,
    Room,
)


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

class _DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _out(data: object) -> None:
    print(json.dumps(data, indent=2, cls=_DecimalEncoder))


def _exit_err(msg: str) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(1)


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_guests(_args) -> None:
    """List all registered guests."""
    with get_session() as session:
        rows = session.execute(
            select(Guest).order_by(Guest.last_name, Guest.first_name)
        ).scalars().all()
    _out([
        {
            "guest_id": g.guest_id,
            "name": f"{g.first_name} {g.last_name}",
            "email": g.email,
            "phone": g.phone,
            "created_at": g.created_at.isoformat(),
        }
        for g in rows
    ])


def cmd_guest_bookings(args) -> None:
    """Show all bookings for a guest by email."""
    with get_session() as session:
        guest = session.execute(
            select(Guest).where(Guest.email == args.email)
        ).scalar_one_or_none()
        if guest is None:
            _exit_err(f"No guest found with email '{args.email}'.")
        rows = session.execute(
            select(Booking)
            .where(Booking.guest_id == guest.guest_id)
            .order_by(Booking.check_in_date.desc())
        ).scalars().all()
    _out({
        "guest_id": guest.guest_id,
        "name": f"{guest.first_name} {guest.last_name}",
        "email": guest.email,
        "total_bookings": len(rows),
        "bookings": [_booking_dict(b) for b in rows],
    })


def cmd_booking(args) -> None:
    """Show a single booking by ID, including guest/hotel/room names."""
    with get_session() as session:
        b = session.execute(
            select(Booking).where(Booking.booking_id == args.id)
        ).scalar_one_or_none()
        if b is None:
            _exit_err(f"No booking found with ID '{args.id}'.")
        result = _booking_dict(b)
        guest = session.get(Guest, b.guest_id)
        hotel = session.get(Hotel, b.hotel_id)
        room  = session.get(Room,  b.room_id)
    result["guest_email"] = guest.email if guest else None
    result["hotel_name"]  = hotel.name  if hotel else None
    result["room_type"]   = room.room_type if room else None
    _out(result)


def cmd_hotels(_args) -> None:
    """List all hotels."""
    with get_session() as session:
        rows = session.execute(
            select(Hotel).order_by(Hotel.name)
        ).scalars().all()
    _out([
        {
            "hotel_id": h.hotel_id,
            "name": h.name,
            "address": h.address,
            "city": h.city,
            "country": h.country,
            "check_in_time": h.check_in_time,
            "check_out_time": h.check_out_time,
            "star_rating": h.star_rating,
        }
        for h in rows
    ])


def cmd_rooms(args) -> None:
    """List rooms for a hotel, optionally only available ones."""
    with get_session() as session:
        hotel = session.execute(
            select(Hotel).where(Hotel.name == args.hotel)
        ).scalar_one_or_none()
        if hotel is None:
            _exit_err(f"No hotel found with name '{args.hotel}'.")

        filters = [Room.hotel_id == hotel.hotel_id]
        if args.available_only:
            filters.append(Room.is_available == True)  # noqa: E712

        rows = session.execute(
            select(Room).where(and_(*filters)).order_by(Room.room_type)
        ).scalars().all()

    _out({
        "hotel_id": hotel.hotel_id,
        "hotel_name": hotel.name,
        "rooms": [
            {
                "room_id": r.room_id,
                "room_type": r.room_type,
                "price_per_night_usd": float(r.price_per_night_usd),
                "max_occupancy": r.max_occupancy,
                "is_available": r.is_available,
            }
            for r in rows
        ],
    })


def cmd_search_bookings(args) -> None:
    """Search bookings with optional filters."""
    filters = []

    if args.status:
        try:
            filters.append(Booking.status == BookingStatus(args.status))
        except ValueError:
            _exit_err(f"Invalid status '{args.status}'. Valid: {[s.value for s in BookingStatus]}")

    if args.after:
        try:
            filters.append(Booking.check_in_date >= _parse_date(args.after))
        except ValueError:
            _exit_err(f"Invalid --after '{args.after}'. Use YYYY-MM-DD.")

    if args.before:
        try:
            filters.append(Booking.check_in_date <= _parse_date(args.before))
        except ValueError:
            _exit_err(f"Invalid --before '{args.before}'. Use YYYY-MM-DD.")

    with get_session() as session:
        if args.hotel:
            hotel = session.execute(
                select(Hotel).where(Hotel.name == args.hotel)
            ).scalar_one_or_none()
            if hotel is None:
                _exit_err(f"No hotel found with name '{args.hotel}'.")
            filters.append(Booking.hotel_id == hotel.hotel_id)

        stmt = select(Booking).order_by(Booking.check_in_date.desc())
        if filters:
            stmt = stmt.where(and_(*filters))

        rows = session.execute(stmt).scalars().all()

    _out({"total": len(rows), "bookings": [_booking_dict(b) for b in rows]})


# ---------------------------------------------------------------------------
# Shared serialiser
# ---------------------------------------------------------------------------

def _booking_dict(b: Booking) -> dict:
    return {
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
        "notes": b.notes,
    }


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="query_cli.py",
        description="Query the Travel Concierge backend database.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    sub.add_parser("guests", help="List all registered guests.")

    p = sub.add_parser("guest-bookings", help="List all bookings for a guest.")
    p.add_argument("--email", required=True, metavar="EMAIL")

    p = sub.add_parser("booking", help="Show details of a single booking.")
    p.add_argument("--id", required=True, metavar="BOOKING_ID")

    sub.add_parser("hotels", help="List all hotels.")

    p = sub.add_parser("rooms", help="List rooms for a hotel.")
    p.add_argument("--hotel", required=True, metavar="HOTEL_NAME")
    p.add_argument("--available-only", action="store_true", default=False,
                   help="Show only available rooms.")

    p = sub.add_parser("search-bookings", help="Search bookings with optional filters.")
    p.add_argument("--status", choices=[s.value for s in BookingStatus], metavar="STATUS")
    p.add_argument("--after",  metavar="YYYY-MM-DD", help="Check-in on or after this date.")
    p.add_argument("--before", metavar="YYYY-MM-DD", help="Check-in on or before this date.")
    p.add_argument("--hotel",  metavar="HOTEL_NAME",  help="Filter by exact hotel name.")

    return parser


_COMMANDS = {
    "guests":          cmd_guests,
    "guest-bookings":  cmd_guest_bookings,
    "booking":         cmd_booking,
    "hotels":          cmd_hotels,
    "rooms":           cmd_rooms,
    "search-bookings": cmd_search_bookings,
}


def main() -> None:
    args = _build_parser().parse_args()
    init_db()  # create tables if they don't exist yet
    _COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
