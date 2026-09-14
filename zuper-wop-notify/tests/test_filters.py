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
    assert filters.event_allowlist() == [
        "job.status_changed",
        "job.updated",
        "job.update",
        "job.update_status",
        "job.status_update",
        "job.update_schedule",
    ]
    assert filters.event_is_allowed("job.status_changed")
    assert filters.event_is_allowed("job.updated")
    assert filters.event_is_allowed("job.update")
    assert filters.event_is_allowed("JOB.UPDATE_STATUS")
    assert filters.event_is_allowed("job.update_schedule")
    assert filters.event_is_allowed("job.status_update")
    assert filters.event_is_allowed("job.create") is False
    assert filters.event_is_allowed("job.update", env_value="custom.event") is False
    assert filters.event_is_allowed("custom.event", env_value="custom.event")


def test_event_is_allowed_when_event_missing_or_null(monkeypatch):
    """Missing/null event must not skip on allowlist; GET+WOP still applies."""
    monkeypatch.delenv("ZUPER_EVENT_ALLOWLIST", raising=False)
    assert filters.event_is_allowed("")
    assert filters.event_is_allowed(None)
    assert filters.event_is_allowed("   ")
    assert filters.extract_event_name({"event": None, "job_uid": "abc"}) == ""
    assert filters.extract_event_name({"job_uid": "abc"}) == ""
    assert filters.event_is_allowed(filters.extract_event_name({"event": None}))


def test_is_waiting_on_parts_case_insensitive():
    assert filters.is_waiting_on_parts({"job_status": "Waiting on Parts"})
    assert filters.is_waiting_on_parts({"job_status": "waiting on parts"})
    assert filters.is_waiting_on_parts({"job_status": {"status_name": "WAITING ON PARTS"}})
    assert filters.is_waiting_on_parts({"status": "Waiting on Parts"})
    assert filters.is_waiting_on_parts({"job_status": "New Ticket"}) is False
    assert filters.is_waiting_on_parts({}) is False


def test_is_waiting_on_parts_uses_current_job_status_not_history_array():
    """Live Get Job Details: current status is nested; job_status is history."""
    job = {
        "current_job_status": {"status_name": "Waiting on Parts"},
        "job_status": [
            {"status_name": "New Ticket"},
            {"status_name": "Scheduled"},
        ],
    }
    assert filters.is_waiting_on_parts(job)
    assert filters._status_text(job) == "Waiting on Parts"
    assert filters.is_waiting_on_parts(
        {"current_job_status": {"status_name": "waiting on parts"}, "job_status": []}
    )


def test_is_waiting_on_parts_ignores_wop_only_in_job_status_history():
    job = {
        "current_job_status": {"status_name": "New Ticket"},
        "job_status": [
            {"status_name": "New Ticket"},
            {"status_name": "Waiting on Parts"},
        ],
    }
    assert filters.is_waiting_on_parts(job) is False
    assert filters._status_text({"job_status": [{"status_name": "Waiting on Parts"}]}) == ""


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


def test_extract_module_skus_from_product_id_and_nested_product():
    """Carbon modules use product_id, not only sku / item_sku."""
    by_top = filters.extract_module_skus(
        {"products": [{"product_id": "0000675", "qty": 1}]},
        prefixes=["0000675"],
    )
    assert by_top == [{"sku": "0000675", "qty": 1}]

    by_nested = filters.extract_module_skus(
        {"products": [{"product": {"product_id": "0000675"}, "quantity": 2}]},
        prefixes=["0000675"],
    )
    assert by_nested == [{"sku": "0000675", "qty": 2}]

    mixed = filters.extract_module_skus(
        {
            "products": [
                {"product_id": "0000675-RW", "qty": 1},
                {"product": {"product_id": "9999999"}, "qty": 9},
            ]
        },
        prefixes=["0000675"],
    )
    assert mixed == [{"sku": "0000675-RW", "qty": 1}]


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


def test_build_notify_payload_falls_back_to_work_order_number():
    job = {
        "job_uid": "uid-2",
        "work_order_number": "WO-7788",
        "current_job_status": {"status_name": "Waiting on Parts"},
        "job_status": [{"status_name": "New Ticket"}],
        "products": [{"product_id": "0000675", "qty": 1}],
    }
    payload = filters.build_notify_payload(job, zuper_event="job.update")
    assert payload["job_number"] == "WO-7788"
    assert payload["status"] == "Waiting on Parts"

    both = {
        "job_uid": "uid-3",
        "job_number": "12345",
        "work_order_number": "WO-7788",
    }
    assert filters.build_notify_payload(both, zuper_event="job.update")["job_number"] == "12345"
