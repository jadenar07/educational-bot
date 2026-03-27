import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
import pytest

from src.backend.modelsPydantic import BotHandshakeRequest, BotHandshakeResponse, BotHeartbeatRequest, BotHeartbeatResponse
from pydantic import ValidationError
from datetime import datetime


def test_handshake_resquest():
    # Test BotHandshakeResquest with all fields
    data = {
        "bot_id": "bot-123",
        "version": "1.0.0",
        "capabilities": ["commands", "metrics"],
        "shared_secret": "supersecret"
    }

    model = BotHandshakeRequest(**data)

    assert model.bot_id == "bot-123"
    assert model.version == "1.0.0"
    assert model.capabilities == ["commands", "metrics"]
    assert model.shared_secret == "supersecret"


def test_handshake_response():
    # Test BotHandshakeResponse with all fields
    data = {
        "session_token": "abc123",
        "expires_at": datetime.now(),
        "interval": 30,
        "flags": {"maintenance_mode": False}
    }
    model = BotHandshakeResponse(**data)
    assert model.session_token == "abc123"
    assert isinstance(model.expires_at, datetime)
    assert model.interval == 30
    assert model.flags["maintenance_mode"] is False


def test_heartbeat_request():
    # Test BotHeartbeatResquest with all fields
    data = {
        "bot_id": "bot-345",
        "latency": 30,
        "stats": None
    }

    model = BotHeartbeatRequest(**data);
    assert model.bot_id == "bot-345"
    assert model.latency == 30
    assert model.stats is None

    serialized = model.model_dump();
    assert serialized == data


def test_heartbeat_response():
    # Test BotHeartbeatResponse with all fields
    data = {
        "bot_id": "bot-123",
        "flags": {"online": True},
        "required_version": "2.0.0"
    }
    model = BotHeartbeatResponse(**data)
    assert model.bot_id == "bot-123"
    assert model.flags["online"] is True
    assert model.required_version == "2.0.0"


def test_missing_field():
    invalid_data = {
        "bot-123": "bot-123",
        "capabilities": ["commands", "metrics"],
        "shared_secret": "supersecret"
    }
    with pytest.raises(ValidationError):
        BotHandshakeRequest(**invalid_data)
        BotHeartbeatRequest(**invalid_data)


def test_json_serialization():
    #Test JSON serialization
    data = {
        "bot_id": "bot-123",
        "latency": 50.5
    }
    model = BotHeartbeatRequest(**data)
    json_str = model.model_dump_json()
    assert "bot-123" in json_str
    assert "50.5" in json_str