import base64
import io
import json
import stat
from pathlib import Path

import pytest
import yaml

from agent_orc import cli
from agent_orc.config import PushConfig, default_config_text
from agent_orc.push import (
    MAX_TEXT_CHARS,
    VAPID_KEY_FILE,
    add_subscription,
    agent_message,
    application_server_key,
    read_subscriptions,
    remove_subscription,
    send_to_all,
)
from agent_orc.sessions import SESSION_ENV
from tests.conftest import Device, FakePushService

PUSH_CONFIG = PushConfig(
    contact="mailto:test@example.org", time_to_live_seconds=60, timeout_seconds=5
)


@pytest.fixture(autouse=True)
def state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    return tmp_path / "state" / "agent-orc"


def test_vapid_key_is_created_once_and_private(state: Path) -> None:
    key = application_server_key()
    # The uncompressed P-256 point: 65 bytes.
    assert len(base64.urlsafe_b64decode(key + "=")) == 65
    assert application_server_key() == key
    assert stat.S_IMODE((state / VAPID_KEY_FILE).stat().st_mode) == 0o600


def test_subscriptions_are_replaced_by_endpoint_and_removed() -> None:
    add_subscription({"endpoint": "https://push/a", "keys": {"p256dh": "1", "auth": "1"}})
    add_subscription({"endpoint": "https://push/b", "keys": {"p256dh": "2", "auth": "2"}})
    add_subscription({"endpoint": "https://push/a", "keys": {"p256dh": "3", "auth": "3"}})
    assert [s["keys"]["p256dh"] for s in read_subscriptions()] == ["2", "3"]
    remove_subscription("https://push/b")
    assert [s["endpoint"] for s in read_subscriptions()] == ["https://push/a"]


def test_message_text_is_shortened() -> None:
    message = agent_message("done", "s-1", "project", "x" * (MAX_TEXT_CHARS + 50))
    assert len(message["text"]) == MAX_TEXT_CHARS


def test_every_device_gets_the_encrypted_signed_message(push_service: FakePushService) -> None:
    phone, laptop = Device(f"{push_service.url}/phone"), Device(f"{push_service.url}/laptop")
    add_subscription(phone.subscription)
    add_subscription(laptop.subscription)
    message = agent_message("done", "s-1", "weather-station", "All 18 tests pass.")
    assert send_to_all(message, PUSH_CONFIG) == 2
    received = {path: (headers, body) for path, headers, body in push_service.received}
    for path, device in (("/phone", phone), ("/laptop", laptop)):
        headers, body = received[path]
        assert device.decrypt(body) == message
        assert headers["authorization"].startswith("vapid t=")
        assert headers["ttl"] == "60"


def test_gone_devices_are_dropped_and_failing_ones_kept(push_service: FakePushService) -> None:
    gone, failing, fine = (Device(f"{push_service.url}/{name}") for name in ("gone", "fail", "ok"))
    for device in (gone, failing, fine):
        add_subscription(device.subscription)
    push_service.status_by_path = {"/gone": 410, "/fail": 500}
    assert send_to_all(agent_message("waiting", "s-1", "p", "May I?"), PUSH_CONFIG) == 1
    endpoints = [s["endpoint"] for s in read_subscriptions()]
    assert endpoints == [f"{push_service.url}/fail", f"{push_service.url}/ok"]


def test_hooks_store_the_activity_and_notify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, push_service: FakePushService
) -> None:
    config = yaml.safe_load(default_config_text())
    config["push"] = PUSH_CONFIG.model_dump()
    (tmp_path / "config" / "agent-orc").mkdir(parents=True)
    (tmp_path / "config" / "agent-orc" / "config.yaml").write_text(yaml.safe_dump(config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv(SESSION_ENV, "garden-1")
    phone = Device(f"{push_service.url}/phone")
    add_subscription(phone.subscription)

    stop = {"cwd": "/w/garden-planner", "last_assistant_message": "Two beds are free."}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(stop)))
    cli.agent_idle()
    notification = {"cwd": "/w/garden-planner", "message": "Claude needs your permission"}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(notification)))
    cli.agent_waiting()

    done, waiting = (phone.decrypt(body) for _, _, body in push_service.received)
    assert done == agent_message("done", "garden-1", "garden-planner", "Two beds are free.")
    assert waiting["kind"] == "waiting"
    assert waiting["text"] == "Claude needs your permission"
