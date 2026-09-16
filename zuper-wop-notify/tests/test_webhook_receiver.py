"""Webhook receiver tests: auth, skip reasons, dry-run, fan-out 200-on-failure."""

from __future__ import annotations

import fanout as fanout_mod
from webhook_receiver import create_app
from zuper_api import ZuperAPIError


SECRET = "s3cret"


def _client(monkeypatch):
    monkeypatch.setenv("ZUPER_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("SHOP_MANAGER_WEBHOOK_URL", "https://example.test/shop")
    monkeypatch.setenv("PARTS_BOT_WEBHOOK_URL", "https://example.test/parts")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _headers():
    return {"x-webhook-secret": SECRET, "Content-Type": "application/json"}


def test_health():
    app = create_app()
    app.config["TESTING"] = True
    resp = app.test_client().get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["service"] == "zuper-wop-notify"


def test_webhook_unauthorized_without_secret(monkeypatch):
    client = _client(monkeypatch)
    resp = client.post("/zuper-webhook", json={"event": "job.status_changed", "job_uid": "x"})
    assert resp.status_code == 401


def test_webhook_skips_non_allowlisted_event(monkeypatch):
    client = _client(monkeypatch)
    called = {"get": 0}

    def fake_get(_job_uid):
        called["get"] += 1
        return {}

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.created", "data": {"job_uid": "abc"}},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["skipped"] is True
    assert body["reason"] == "event_not_allowed"
    assert called["get"] == 0


def test_webhook_missing_or_null_event_still_fetches_and_wop_filters(monkeypatch):
    """Regression: blank event must not skip on allowlist; still GET + WOP."""
    client = _client(monkeypatch)
    called = {"get": 0}

    def fake_get(job_uid):
        called["get"] += 1
        return {
            "job_uid": job_uid,
            "job_status": "Waiting on Parts",
            "products": [{"sku": "0000675", "qty": 1}],
        }

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(
        fanout_mod,
        "fanout",
        lambda payload: {"shop_manager": {"ok": True}, "parts_bot": {"ok": True}},
    )

    for payload in (
        {"event": None, "data": {"job_uid": "abc"}},
        {"job_uid": "abc"},
    ):
        called["get"] = 0
        resp = client.post("/zuper-webhook", headers=_headers(), json=payload)
        assert resp.status_code == 200
        body = resp.get_json()
        assert body.get("reason") != "event_not_allowed"
        assert called["get"] == 1
        assert body["notified"] is True


def test_webhook_accepts_job_status_changed_event(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {
            "job_uid": job_uid,
            "job_status": "Waiting on Parts",
            "products": [{"sku": "0000675", "qty": 1}],
        }

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(
        fanout_mod,
        "fanout",
        lambda payload: {"shop_manager": {"ok": True}, "parts_bot": {"ok": True}},
    )
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "data": {"job_uid": "abc"}},
    )
    assert resp.status_code == 200
    assert resp.get_json()["notified"] is True


def test_webhook_missing_job_uid_fails_loud(monkeypatch):
    client = _client(monkeypatch)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed"},
    )
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "missing_job_uid"


def test_webhook_notifies_live_get_job_details_shape(monkeypatch):
    """CoS: current_job_status + job_status history list must notify, not not_wop."""
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {
            "job_uid": job_uid,
            "work_order_number": "WO-42",
            "current_job_status": {"status_name": "Waiting on Parts"},
            "job_status": [
                {"status_name": "New Ticket"},
                {"status_name": "Scheduled"},
            ],
            "products": [{"product_id": "0000675", "qty": 1}],
        }

    def fake_fanout(payload):
        assert payload["status"] == "Waiting on Parts"
        assert payload["job_number"] == "WO-42"
        assert payload["module_skus_found"] == [{"sku": "0000675", "qty": 1}]
        return {
            "shop_manager": {"ok": True, "status_code": 200},
            "parts_bot": {"ok": True, "status_code": 200},
        }

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(fanout_mod, "fanout", fake_fanout)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "data": {"job_uid": "abc"}},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body.get("reason") != "not_wop"
    assert body["notified"] is True
    assert body["payload"]["status"] == "Waiting on Parts"
    assert body["payload"]["job_number"] == "WO-42"


def test_webhook_notifies_nested_product_id_module(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {
            "job_uid": job_uid,
            "current_job_status": {"status_name": "waiting on parts"},
            "job_status": [{"status_name": "New Ticket"}],
            "products": [{"product": {"product_id": "0000675"}}],
        }

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(
        fanout_mod,
        "fanout",
        lambda payload: {"shop_manager": {"ok": True}, "parts_bot": {"ok": True}},
    )
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "job_uid": "abc"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["notified"] is True
    assert body["payload"]["module_skus_found"] == [{"sku": "0000675", "qty": None}]


def test_webhook_skips_not_wop(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {"job_uid": job_uid, "job_status": "New Ticket", "products": [{"sku": "0000675", "qty": 1}]}

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "data": {"job_uid": "abc"}},
    )
    assert resp.status_code == 200
    assert resp.get_json()["reason"] == "not_wop"


def test_webhook_skips_not_module(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {"job_uid": job_uid, "job_status": "Waiting on Parts", "products": [{"sku": "1111111"}]}

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "job_uid": "abc"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["reason"] == "not_module"


def test_dry_run_returns_payload_without_fanout(monkeypatch):
    client = _client(monkeypatch)
    called = {"fanout": 0}

    def fake_get(job_uid):
        return {
            "job_uid": job_uid,
            "job_number": "42",
            "job_title": "module",
            "job_status": "Waiting on Parts",
            "products": [{"sku": "0000675", "qty": 1}],
        }

    def fake_fanout(_payload):
        called["fanout"] += 1
        return {}

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(fanout_mod, "fanout", fake_fanout)
    resp = client.post(
        "/dry-run",
        headers=_headers(),
        json={"event": "job.status_changed", "job_uid": "abc"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["dry_run"] is True
    assert body["notified"] is False
    assert body["payload"]["module_skus_found"] == [{"sku": "0000675", "qty": 1}]
    assert called["fanout"] == 0


def test_match_fans_out_and_returns_200_even_if_fanout_fails(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(job_uid):
        return {
            "job_uid": job_uid,
            "job_number": "42",
            "job_status": "Waiting on Parts",
            "products": [{"sku": "0000675", "qty": 1}],
        }

    def fake_fanout(payload):
        assert payload["source"] == "zuper-wop-notify"
        return {
            "shop_manager": {"ok": False, "error": "timeout"},
            "parts_bot": {"ok": False, "error": "500"},
        }

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    monkeypatch.setattr(fanout_mod, "fanout", fake_fanout)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "job_uid": "abc"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["notified"] is True
    assert body["fanout"]["shop_manager"]["ok"] is False


def test_zuper_get_failure_is_loud(monkeypatch):
    client = _client(monkeypatch)

    def fake_get(_job_uid):
        raise ZuperAPIError("boom")

    monkeypatch.setattr("webhook_receiver.get_job_detail", fake_get)
    resp = client.post(
        "/zuper-webhook",
        headers=_headers(),
        json={"event": "job.status_changed", "job_uid": "abc"},
    )
    assert resp.status_code == 502
    assert resp.get_json()["error"] == "zuper_get_failed"
