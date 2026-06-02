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
        description: Human-readable description.
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
    """Retrieve all charges posted to a booking, ordered by posted_at ascending.

    Args:
        booking_id: The booking to retrieve charges for.

    Returns:
        List of charge dicts.
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
