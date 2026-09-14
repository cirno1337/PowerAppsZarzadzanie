"""Tests for the Direct Line REST client — requests is monkeypatched so
these run without a real Copilot Studio agent or secret."""

from __future__ import annotations

import pytest
import requests

from worker.adapters.copilot import direct_line


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


def test_generate_token_sends_secret_as_bearer(monkeypatch):
    captured = {}

    def fake_post(url, headers, timeout, **kwargs):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse(json_data={"token": "tok", "conversationId": "conv1", "expires_in": 3600})

    monkeypatch.setattr(requests, "post", fake_post)
    result = direct_line.generate_token("my-secret")

    assert result == {"token": "tok", "conversationId": "conv1", "expires_in": 3600}
    assert captured["headers"]["Authorization"] == "Bearer my-secret"
    assert captured["url"] == f"{direct_line.DIRECTLINE_BASE}/tokens/generate"


def test_generate_token_raises_on_failure(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **k: _FakeResponse(status_code=401))
    with pytest.raises(direct_line.DirectLineError):
        direct_line.generate_token("bad-secret")


def test_post_message_builds_expected_payload(monkeypatch):
    captured = {}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    direct_line.post_message("tok", "conv1", "hello", from_id="worker")

    assert captured["url"] == f"{direct_line.DIRECTLINE_BASE}/conversations/conv1/activities"
    assert captured["json"] == {"type": "message", "from": {"id": "worker"}, "text": "hello"}


def test_wait_for_reply_returns_first_non_self_message(monkeypatch):
    call_count = {"n": 0}

    def fake_get_activities(token, conversation_id, watermark=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"watermark": "1", "activities": [{"type": "message", "from": {"id": "worker"}, "text": "hello"}]}
        return {
            "watermark": "2",
            "activities": [{"type": "message", "from": {"id": "the-agent"}, "text": "here is the doc"}],
        }

    monkeypatch.setattr(direct_line, "get_activities", fake_get_activities)
    result = direct_line.wait_for_reply(
        "tok", "conv1", after_watermark=None, exclude_from_id="worker", poll_interval=0, sleep=lambda s: None
    )
    assert result == "here is the doc"


def test_wait_for_reply_times_out(monkeypatch):
    times = iter([0, 0, 100])  # first call establishes the deadline, later calls exceed it

    def fake_now():
        return next(times, 100)

    def fake_get_activities(token, conversation_id, watermark=None):
        return {"watermark": watermark, "activities": []}

    monkeypatch.setattr(direct_line, "get_activities", fake_get_activities)
    with pytest.raises(direct_line.DirectLineError, match="Timed out"):
        direct_line.wait_for_reply(
            "tok", "conv1", after_watermark=None, exclude_from_id="worker",
            poll_interval=0, timeout=1, sleep=lambda s: None, now=fake_now,
        )


def test_converse_end_to_end(monkeypatch):
    posted = {}

    def fake_generate_token(secret):
        assert secret == "the-secret"
        return {"token": "tok", "conversationId": "conv1"}

    def fake_get_activities(token, conversation_id, watermark=None):
        if "posted" not in posted:
            return {"watermark": "0", "activities": []}
        return {"watermark": "1", "activities": [{"type": "message", "from": {"id": "the-agent"}, "text": "the reply"}]}

    def fake_post_message(token, conversation_id, text, from_id):
        posted["posted"] = text

    monkeypatch.setattr(direct_line, "generate_token", fake_generate_token)
    monkeypatch.setattr(direct_line, "get_activities", fake_get_activities)
    monkeypatch.setattr(direct_line, "post_message", fake_post_message)

    result = direct_line.converse("the-secret", "hello agent", timeout=5)
    assert result == "the reply"
    assert posted["posted"] == "hello agent"
