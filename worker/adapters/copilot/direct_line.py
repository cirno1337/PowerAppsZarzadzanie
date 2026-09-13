"""Bot Framework Direct Line REST client — the verified real mechanism for
invoking a Copilot Studio agent (see ``docs/COPILOT_INTEGRATION.md``).

REQUIRES LICENSING VERIFICATION for the company tenant — the Direct Line
mechanism itself is verified against official Microsoft docs and
structurally confirmed on a personal test tenant, but has not been
end-to-end tested against the company's own Copilot Studio agent.

Pure HTTP functions (no secret handling beyond passing it straight into an
Authorization header) so they're unit-testable by monkeypatching
``requests``. The secret itself is never logged.
"""

from __future__ import annotations

import time

import requests

DIRECTLINE_BASE = "https://directline.botframework.com/v3/directline"
DEFAULT_HTTP_TIMEOUT_SECONDS = 30
DEFAULT_POLL_INTERVAL_SECONDS = 1.0
DEFAULT_POLL_TIMEOUT_SECONDS = 60.0


class DirectLineError(RuntimeError):
    """A Direct Line call failed or timed out. Never includes the secret."""


def generate_token(secret: str) -> dict:
    """POST /tokens/generate — exchange a Direct Line secret for a
    short-lived token + a fresh conversationId."""
    resp = requests.post(
        f"{DIRECTLINE_BASE}/tokens/generate",
        headers={"Authorization": f"Bearer {secret}"},
        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise DirectLineError(f"Failed to generate Direct Line token (HTTP {resp.status_code})")
    return resp.json()


def post_message(token: str, conversation_id: str, text: str, from_id: str) -> None:
    resp = requests.post(
        f"{DIRECTLINE_BASE}/conversations/{conversation_id}/activities",
        headers={"Authorization": f"Bearer {token}"},
        json={"type": "message", "from": {"id": from_id}, "text": text},
        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise DirectLineError(f"Failed to post message (HTTP {resp.status_code})")


def get_activities(token: str, conversation_id: str, watermark: str | None = None) -> dict:
    params = {"watermark": watermark} if watermark else {}
    resp = requests.get(
        f"{DIRECTLINE_BASE}/conversations/{conversation_id}/activities",
        headers={"Authorization": f"Bearer {token}"},
        params=params,
        timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
    )
    if not resp.ok:
        raise DirectLineError(f"Failed to get activities (HTTP {resp.status_code})")
    return resp.json()


def wait_for_reply(
    token: str,
    conversation_id: str,
    after_watermark: str | None,
    exclude_from_id: str,
    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS,
    timeout: float = DEFAULT_POLL_TIMEOUT_SECONDS,
    sleep=time.sleep,
    now=time.monotonic,
) -> str:
    """Poll activities (Bot Framework's watermark pattern) until a message
    not sent by ``exclude_from_id`` arrives, returning its text."""
    deadline = now() + timeout
    watermark = after_watermark
    while now() < deadline:
        activity_set = get_activities(token, conversation_id, watermark)
        watermark = activity_set.get("watermark", watermark)
        for activity in activity_set.get("activities", []):
            if activity.get("type") == "message" and activity.get("from", {}).get("id") != exclude_from_id:
                return activity.get("text", "")
        sleep(poll_interval)
    raise DirectLineError("Timed out waiting for a reply from the agent")


def converse(secret: str, message: str, from_id: str = "ppdm-worker", timeout: float = DEFAULT_POLL_TIMEOUT_SECONDS) -> str:
    """High-level helper: get a token, capture the current watermark, send
    ``message``, and return the agent's first reply text.

    Capturing the watermark before sending (rather than passing
    ``watermark=None``) means only activities that arrive *after* our own
    message are considered — protects against matching a stale/prior
    activity in a reused conversation.
    """
    token_info = generate_token(secret)
    token = token_info["token"]
    conversation_id = token_info["conversationId"]
    initial = get_activities(token, conversation_id)
    watermark = initial.get("watermark")
    post_message(token, conversation_id, message, from_id=from_id)
    return wait_for_reply(token, conversation_id, watermark, exclude_from_id=from_id, timeout=timeout)
