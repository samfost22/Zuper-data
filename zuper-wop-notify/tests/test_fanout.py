"""Fan-out tests for downstream Grok routine posts."""

from __future__ import annotations

import fanout


class _Response:
    status_code = 204
    text = ""


def test_fanout_posts_to_both_grok_webhooks_with_notify_token(monkeypatch):
    calls = []

    def fake_post(url, *, json, headers, timeout):
        calls.append(
            {
                "url": url,
                "json": json,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return _Response()

    monkeypatch.setenv("SHOP_MANAGER_WEBHOOK_URL", "https://grok.example/shop")
    monkeypatch.setenv("PARTS_BOT_WEBHOOK_URL", "https://grok.example/parts")
    monkeypatch.setenv("NOTIFY_TOKEN", "notify-secret")
    monkeypatch.setenv("NOTIFY_TIMEOUT_SECONDS", "3.5")
    monkeypatch.delenv("X_NOTIFY_TOKEN", raising=False)
    monkeypatch.setattr(fanout.requests, "post", fake_post)

    payload = {"source": "zuper-wop-notify", "job_uid": "job-1"}
    results = fanout.fanout(payload)

    assert results["shop_manager"]["ok"] is True
    assert results["parts_bot"]["ok"] is True
    assert [call["url"] for call in calls] == [
        "https://grok.example/shop",
        "https://grok.example/parts",
    ]
    for call in calls:
        assert call["json"] == payload
        assert call["headers"]["X-Notify-Token"] == "notify-secret"
        assert call["headers"]["Content-Type"] == "application/json"
        assert call["timeout"] == 3.5
