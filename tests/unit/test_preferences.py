"""Unit tests for preference extraction and persistence tools."""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from travel_concierge.database.models import Base, Guest
from travel_concierge.tools.preferences import extract_preferences, update_guest_preferences


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def guest_id(db_engine):
    with Session(db_engine) as session:
        g = Guest(
            guest_id=str(uuid.uuid4()),
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
        )
        session.add(g)
        session.commit()
        return g.guest_id


def test_extract_preferences_returns_results(monkeypatch):
    mock_response = MagicMock()
    mock_response.text = json.dumps([
        {"field": "pillow_preference", "value": "feather", "confidence": "high"},
        {"field": "dietary_restrictions", "value": "vegan", "confidence": "medium"},
    ])

    with patch("travel_concierge.tools.preferences.genai.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        results = extract_preferences("I loved the feather pillows and the vegan breakfast")

    assert len(results) == 2
    assert results[0]["field"] == "pillow_preference"
    assert results[1]["confidence"] == "medium"


def test_extract_preferences_invalid_json_returns_empty(monkeypatch):
    mock_response = MagicMock()
    mock_response.text = "not json"

    with patch("travel_concierge.tools.preferences.genai.Client") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        results = extract_preferences("some feedback")

    assert results == []


def test_update_guest_preferences_writes_new(guest_id, db_engine):
    with patch("travel_concierge.tools.preferences.get_session") as mock_gs:
        session = Session(db_engine)
        mock_gs.return_value.__enter__ = lambda s: session
        mock_gs.return_value.__exit__ = MagicMock(return_value=False)

        update_guest_preferences(guest_id, {"pillow_preference": "feather"})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)
        assert prefs["pillow_preference"] == "feather"


def test_update_guest_preferences_merges_fields(guest_id, db_engine):
    session = Session(db_engine)

    def make_ctx():
        ctx = MagicMock()
        ctx.__enter__ = lambda s: session
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("travel_concierge.tools.preferences.get_session", side_effect=make_ctx):
        update_guest_preferences(guest_id, {"pillow_preference": "feather"})
        update_guest_preferences(guest_id, {"dietary_restrictions": ["vegan"]})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)

    assert prefs["pillow_preference"] == "feather"
    assert prefs["dietary_restrictions"] == ["vegan"]


def test_update_guest_preferences_overwrites_same_field(guest_id, db_engine):
    session = Session(db_engine)

    def make_ctx():
        ctx = MagicMock()
        ctx.__enter__ = lambda s: session
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    with patch("travel_concierge.tools.preferences.get_session", side_effect=make_ctx):
        update_guest_preferences(guest_id, {"pillow_preference": "foam"})
        update_guest_preferences(guest_id, {"pillow_preference": "feather"})

        fetched = session.get(Guest, guest_id)
        prefs = json.loads(fetched.preferences)

    assert prefs["pillow_preference"] == "feather"
