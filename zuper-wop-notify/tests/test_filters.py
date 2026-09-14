"""Tests for WOP filters, secret normalization, SKU/GPS extract, notify payload."""

from __future__ import annotations

import filters


def test_normalize_secret_strips_all_whitespace():
    assert filters.normalize_secret("  ab  cd\t\ne ") == "abcde"
    assert filters.normalize_secret(None) == ""
    assert filters.normalize_secret("secret") == "secret"


def test_configured_webhook_secrets_comma_separated_and_stripped():
    raw = " alpha ,  be ta\n,gamma"
    assert filters.configured_webhook_secrets(raw) == ["alpha", "beta", "gamma"]


def test_webhook_secret_matches_x_webhook_secret_header():
    env = "s3cret"
    headers = {"x-webhook-secret": " s 3 cret "}
    assert filters.webhook_secret_is_valid(headers, env)


def test_webhook_secret_matches_secret_key_header_any_case():
    env = "s3cret,other"
    assert filters.webhook_secret_is_valid({"Secret-Key": "s3cret"}, env)
    assert filters.webhook_secret_is_valid({"secret-key": "other"}, env)


def test_webhook_secret_rejects_missing_or_unknown():
    env = "s3cret"
    assert filters.webhook_secret_is_valid({}, env) is False
    assert filters.webhook_secret_is_valid({"x-webhook-secret": "nope"}, env) is False
    assert filters.webhook_secret_is_valid({"x-webhook-secret": "s3cret"}, "") is False


def test_extract_job_uid_from_nested_data():
    assert filters.extract_job_uid({"data": {"job_uid": "abc-123"}}) == "abc-123"
    assert filters.extract_job_uid({"job_uid": "top"}) == "top"
    assert filters.extract_job_uid({"data": {"job": {"job_uid": "nested-job"}}}) == "nested-job"
    assert filters.extract_job_uid({"data": {"foo": 1}}) is None
    assert filters.extract_job_uid(None) is None


def test_event_allowlist_default_and_custom(monkeypatch):
    monkeypatch.delenv("ZUPER_EVENT_ALLOWLIST", raising=False)
    assert filters.event_is_allowed("job.update")
    assert filters.event_is_allowed("JOB.UPDATE_STATUS")
    assert filters.event_is_allowed("job.update_schedule")
    assert filters.event_is_allowed("job.status_update")
    assert filters.event_is_allowed("job.create") is False
    assert filters.event_is_allowed("job.update", env_value="custom.event") is False
    assert filters.event_is_allowed("custom.event", env_value="custom.event")


def test_is_waiting_on_parts_case_insensitive():
    assert filters.is_waiting_on_parts({"job_status": "Waiting on Parts"})
    assert filters.is_waiting_on_parts({"job_status": "waiting on parts"})
    assert filters.is_waiting_on_parts({"job_status": {"status_name": "WAITING ON PARTS"}})
    assert filters.is_waiting_on_parts({"status": "Waiting on Parts"})
    assert filters.is_waiting_on_parts({"job_status": "New Ticket"}) is False
    assert filters.is_waiting_on_parts({}) is False


def test_extract_module_skus_matches_prefix_only_found_items():
    job = {
        "products": [
            {"sku": "0000675", "qty": 1},
            {"product": {"product_sku": "0000675-RW"}, "quantity": 2},
            {"sku": "9999999", "qty": 9},
        ]
    }
    found = filters.extract_module_skus(job, prefixes=["0000675"])
    by_sku = {row["sku"]: row["qty"] for row in found}
    assert by_sku == {"0000675": 1, "0000675-RW": 2}
    assert "9999999" not in by_sku


def test_extract_module_skus_does_not_invent_qty_or_skus():
    job = {"products": [{"sku": "0000675"}]}
    found = filters.extract_module_skus(job, prefixes=["0000675"])
    assert found == [{"sku": "0000675", "qty": None}]
    assert filters.extract_module_skus({"products": []}, prefixes=["0000675"]) == []
    assert filters.extract_module_skus({}, prefixes=["0000675"]) == []


def test_extract_gps_from_zuper_geo_cordinates_typo():
    job = {"customer_address": {"geo_cordinates": [36.1, -119.2]}}
    assert filters.extract_gps(job) == (36.1, -119.2)


def test_extract_gps_missing():
    lat, lng = filters.extract_gps({"customer_address": {}})
    assert lat is None and lng is None


def test_build_notify_payload_shape():
    job = {
        "job_uid": "uid-1",
        "job_number": "12345",
        "job_title": "WM repair",
        "job_status": "Waiting on Parts",
        "job_priority": "High",
        "parent_job": {"job_number": "999"},
        "products": [{"sku": "0000675", "qty": 1}],
    }
    payload = filters.build_notify_payload(job, zuper_event="job.update_status")
    assert payload["source"] == "zuper-wop-notify"
    assert payload["zuper_event"] == "job.update_status"
    assert payload["received_at"].endswith("Z")
    assert payload["job_uid"] == "uid-1"
    assert payload["job_number"] == "12345"
    assert payload["title"] == "WM repair"
    assert payload["status"] == "Waiting on Parts"
    assert payload["job_priority"] == "High"
    assert payload["parent_job_number"] == "999"
    assert payload["is_frp_child"] is True
    assert payload["latitude"] is None
    assert payload["longitude"] is None
    assert payload["gps_missing"] is True
    assert payload["module_skus_found"] == [{"sku": "0000675", "qty": 1}]
    assert payload["freshness_note"] == filters.FRESHNESS_NOTE
    assert set(payload.keys()) == {
        "source",
        "zuper_event",
        "received_at",
        "job_uid",
        "job_number",
        "title",
        "status",
        "job_priority",
        "parent_job_number",
        "is_frp_child",
        "latitude",
        "longitude",
        "gps_missing",
        "module_skus_found",
        "freshness_note",
    }
