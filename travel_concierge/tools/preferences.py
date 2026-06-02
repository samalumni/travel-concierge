"""Tools for extracting and persisting guest preferences from free-text feedback."""

import json
import logging

from google import genai
from google.genai import types as genai_types
from sqlalchemy import select

from travel_concierge import MODEL
from travel_concierge.database.db import get_session
from travel_concierge.database.models import Guest
from travel_concierge.shared_libraries.types import ExtractedPreference

logger = logging.getLogger(__name__)


def extract_preferences(feedback_text: str) -> list[dict]:
    """Parse free-text guest feedback into structured preference field/value pairs.

    Uses Gemini controlled generation with ExtractedPreference output schema.

    Args:
        feedback_text: Raw feedback from the guest.

    Returns:
        List of dicts with keys: field, value, confidence.
        Returns [] on parse failure.
    """
    client = genai.Client()
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                "Extract guest hotel stay preferences from the following feedback. "
                "Map them to structured fields such as pillow_preference, "
                "room_temperature_c, floor_preference, bed_type_preference, "
                "view_preference, or dietary_restrictions. "
                f"Feedback: {feedback_text}"
            ),
            config=genai_types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=list[ExtractedPreference],
            ),
        )
        items = json.loads(response.text)
        return [
            {"field": p["field"], "value": p["value"], "confidence": p["confidence"]}
            for p in items
        ]
    except Exception as exc:
        logger.warning("extract_preferences failed to parse response: %s", exc)
        return []


def update_guest_preferences(guest_id: str, preferences: dict) -> dict:
    """Merge new preference values into the guest's stored preferences.

    Merge rule: provided values always overwrite the stored value (most recent wins).
    Fields absent from `preferences` are untouched.

    Args:
        guest_id: The guest's DB ID.
        preferences: Dict of field -> value to merge.

    Returns:
        A dict with status and the updated preferences.
    """
    with get_session() as session:
        guest = session.execute(
            select(Guest).where(Guest.guest_id == guest_id)
        ).scalar_one_or_none()

        if guest is None:
            return {"status": f"Guest {guest_id} not found", "updated": {}}

        existing = json.loads(guest.preferences) if guest.preferences else {}
        existing.update(preferences)
        guest.preferences = json.dumps(existing)
        session.commit()

    logger.info("Updated preferences for guest %s: %s", guest_id, list(preferences.keys()))
    return {"status": "preferences updated", "updated": existing}
