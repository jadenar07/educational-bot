import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
import pytest
from datetime import timedelta, datetime
from backend.sessionManager import SessionManager, SessionData

@pytest.fixture
def manager():
    return SessionManager()


@pytest.fixture
def short_manager():
    return SessionManager(session_ttl=timedelta(seconds=1))


@pytest.fixture
def token(manager):
    return manager.create_session("bot-1", "1.0.0", ["query"])


def test_create_session_returns_token(manager):
    token = manager.create_session("bot-1", "1.0.0", ["query"])
    assert isinstance(token, str)
    assert len(token) > 0


def test_create_session_stores_session(manager):
    token = manager.create_session("bot-1", "1.0.0", ["query", "moderation"])
    session = manager.get_session(token)
    assert session is not None
    assert session.bot_id == "bot-1"
    assert session.version == "1.0.0"
    assert session.capabilities == ["query", "moderation"]
    assert session.revoked is False
    assert session.last_heartbeat is None


def test_create_session_unique_tokens(manager):
    t1 = manager.create_session("bot-1", "1.0.0", [])
    t2 = manager.create_session("bot-1", "1.0.0", [])
    assert t1 != t2
    # rehandshake revokes the old session
    assert manager.get_session(t1).revoked is True
    assert manager.get_session(t2).revoked is False


def test_get_session_returns_none_for_unknown_token(manager):
    assert manager.get_session("nonexistent") is None


def test_get_session_returns_correct_session(manager, token):
    session = manager.get_session(token)
    assert session is not None
    assert session.bot_id == "bot-1"

def test_validate_session_valid_token(manager, token):
    assert manager.validate_session(token) == "valid"


def test_validate_session_unknown_token(manager):
    assert manager.validate_session("bad-token") == "invalid"


def test_validate_session_revoked_token(manager, token):
    manager.revoke_session(token)
    assert manager.validate_session(token) == "revoked"


def test_validate_session_expired_token(short_manager):
    token = short_manager.create_session("bot-1", "1.0.0", [])
    import time; time.sleep(1.1)
    assert short_manager.validate_session(token) == "expired"
    assert short_manager.get_session(token) is None

def test_revoke_session(manager, token):
    manager.revoke_session(token)
    session = manager.get_session(token)
    assert session.revoked is True


def test_revoke_session_unknown_token(manager):
    manager.revoke_session("nonexistent")

def test_update_heartbeat_records_latency(manager, token):
    manager.update_heartbeat(token, latency=42.5)
    session = manager.get_session(token)

    assert session.last_heartbeat is not None
    assert session.last_latency == 42.5


def test_update_heartbeat_merges_stats(manager, token):
    manager.update_heartbeat(token, latency=10.0, stats={"commands": 5})
    manager.update_heartbeat(token, latency=12.0, stats={"errors": 1})
    session = manager.get_session(token)

    assert session.stats["commands"] == 5
    assert session.stats["errors"] == 1
    assert session.last_latency == 12.0


def test_update_heartbeat_unknown_token(manager):
    manager.update_heartbeat("bad-token", latency=10.0)

def test_cleanup_removes_expired(short_manager):
    token = short_manager.create_session("bot-1", "1.0.0", [])
    import time; time.sleep(1.1)
    short_manager.cleanup_expired_sessions()
    assert short_manager.get_session(token) is None


def test_cleanup_keeps_active(manager, token):
    manager.cleanup_expired_sessions()
    assert manager.get_session(token) is not None


def test_get_active_sessions(manager):
    t1 = manager.create_session("bot-1", "1.0.0", [])
    t2 = manager.create_session("bot-2", "1.0.0", [])
    manager.revoke_session(t1)

    active = manager.get_active_sessions()
    assert t1 not in active
    assert t2 in active


def test_get_active_sessions_empty(manager):
    assert manager.get_active_sessions() == {}