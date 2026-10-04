"""Web push to the user's devices: an agent finished its answer or waits for the user.

A browser subscribes (Push API) with the server's VAPID public key; Agent-Orc keeps the
subscriptions and sends through the browser vendor's push service, encrypted by pywebpush
(RFC 8291). The agent's hooks run `agent-orc agent-idle` and `agent-orc agent-waiting`,
which send; the service worker of the web app shows the message.
"""

import base64
import json
import logging
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02
from pywebpush import WebPushException, webpush

from agent_orc.config import PushConfig
from agent_orc.state import state_dir, write_atomically

logger = logging.getLogger(__name__)

VAPID_KEY_FILE = "vapid-private.pem"
SUBSCRIPTIONS_FILE = "push-subscriptions.json"
PRIVATE_KEY_MODE = 0o600
# A push message carries at most 4 KB, and a notification shows a few lines anyway.
MAX_TEXT_CHARS = 300
# The push service answers so for a subscription the browser has given up.
GONE_STATUSES = {404, 410}


def vapid_key() -> Vapid02:
    """The server's signing key, created on first use; browsers subscribe to its public half."""
    path = state_dir() / VAPID_KEY_FILE
    if path.is_file():
        return Vapid02.from_file(str(path))
    key = Vapid02()
    key.generate_keys()
    path.parent.mkdir(parents=True, exist_ok=True)
    key.save_key(str(path))
    path.chmod(PRIVATE_KEY_MODE)
    return key


def application_server_key() -> str:
    """The public key as the Push API takes it: the uncompressed point, base64url."""
    point = vapid_key().public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    return base64.urlsafe_b64encode(point).rstrip(b"=").decode()


def _subscriptions_path() -> Path:
    return state_dir() / SUBSCRIPTIONS_FILE


def read_subscriptions() -> list[dict[str, Any]]:
    path = _subscriptions_path()
    if not path.is_file():
        return []
    subscriptions: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    return subscriptions


def _write_subscriptions(subscriptions: list[dict[str, Any]]) -> None:
    write_atomically(_subscriptions_path(), json.dumps(subscriptions))


def add_subscription(subscription: dict[str, Any]) -> None:
    """Keep a device's subscription; subscribing again replaces it (same endpoint)."""
    others = [s for s in read_subscriptions() if s["endpoint"] != subscription["endpoint"]]
    _write_subscriptions([*others, subscription])


def remove_subscription(endpoint: str) -> None:
    _write_subscriptions([s for s in read_subscriptions() if s["endpoint"] != endpoint])


def agent_message(kind: str, session_id: str, folder: str, text: str) -> dict[str, Any]:
    """What the service worker shows (its texts per kind are in push-sw.js), for the agent in
    folder."""
    return {"kind": kind, "session": session_id, "folder": folder, "text": text[:MAX_TEXT_CHARS]}


def send_to_all(message: dict[str, Any], config: PushConfig) -> int:
    """Send to every subscribed device; returns how many took it.

    A device that fails is logged and skipped, so one broken phone does not silence the
    others; a subscription the push service reports as gone is dropped.
    """
    key = vapid_key()
    data = json.dumps(message)
    delivered = 0
    for subscription in read_subscriptions():
        try:
            webpush(
                subscription,
                data,
                vapid_private_key=key,
                vapid_claims={"sub": config.contact},
                ttl=config.time_to_live_seconds,
                timeout=config.timeout_seconds,
            )
        except WebPushException as error:
            status = error.response.status_code if error.response is not None else None
            if status in GONE_STATUSES:
                remove_subscription(subscription["endpoint"])
            else:
                logger.warning("push to %s failed: %s", subscription["endpoint"], error)
            continue
        delivered += 1
    return delivered
