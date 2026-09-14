"""WOP filters, SKU/GPS extractors, webhook secret helpers, notify payload.

Never invent stock/SKUs — only emit SKUs actually found on the Zuper job.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Iterable

DEFAULT_WOP_STATUS = "Waiting on Parts"
DEFAULT_MODULE_SKU_PREFIXES = ("0000675",)
DEFAULT_EVENT_ALLOWLIST = (
    "job.status_changed",
    "job.updated",
    "job.update",
    "job.update_status",
    "job.status_update",
    "job.update_schedule",
)
FRESHNESS_NOTE = "live Zuper API pull at notify time; NS→Zuper lag unknown"
SOURCE_NAME = "zuper-wop-notify"

WEBHOOK_SECRET_HEADERS = (
    "x-webhook-secret",
    "secret-key",
    "Secret-Key",
)


def normalize_secret(value: str | None) -> str:
    """Strip ALL whitespace (spaces, tabs, newlines, commas-adjacent padding)."""
    if value is None:
        return ""
    return re.sub(r"\s+", "", str(value))


def parse_csv_env(value: str | None) -> list[str]:
    """Split a comma-separated env value, dropping empty segments."""
    if not value:
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def configured_webhook_secrets(env_value: str | None = None) -> list[str]:
    """Allowed secrets from ``ZUPER_WEBHOOK_SECRET`` (comma-separated, whitespace-stripped)."""
    raw = env_value if env_value is not None else os.environ.get("ZUPER_WEBHOOK_SECRET", "")
    return [normalize_secret(part) for part in parse_csv_env(raw) if normalize_secret(part)]


def extract_presented_secret(headers: Any) -> str:
    """Read webhook secret from x-webhook-secret or secret-key / Secret-Key."""
    getter = getattr(headers, "get", None)
    if callable(getter):
        for name in WEBHOOK_SECRET_HEADERS:
            presented = getter(name)
            if presented:
                return str(presented)
        # Mapping-style fallback (plain dicts are case-sensitive).
        if hasattr(headers, "items"):
            lowered = {str(k).lower(): v for k, v in headers.items()}
            for name in ("x-webhook-secret", "secret-key"):
                if lowered.get(name):
                    return str(lowered[name])
        return ""
    if isinstance(headers, dict):
        lowered = {str(k).lower(): v for k, v in headers.items()}
        for name in ("x-webhook-secret", "secret-key"):
            if lowered.get(name):
                return str(lowered[name])
    return ""


def webhook_secret_is_valid(headers: Any, env_value: str | None = None) -> bool:
    """True when a presented header secret matches a configured (normalized) secret."""
    allowed = configured_webhook_secrets(env_value)
    if not allowed:
        return False
    presented = normalize_secret(extract_presented_secret(headers))
    if not presented:
        return False
    return presented in allowed


def event_allowlist(env_value: str | None = None) -> list[str]:
    raw = env_value if env_value is not None else os.environ.get("ZUPER_EVENT_ALLOWLIST")
    if raw is None or str(raw).strip() == "":
        return list(DEFAULT_EVENT_ALLOWLIST)
    return [item.casefold() for item in parse_csv_env(raw)]


def extract_event_name(payload: dict[str, Any] | None) -> str:
    if not isinstance(payload, dict):
        return ""
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for candidate in (
        payload.get("event"),
        payload.get("event_name"),
        payload.get("event_type"),
        payload.get("type"),
        nested.get("event"),
        nested.get("event_name"),
        nested.get("event_type"),
    ):
        if candidate:
            return str(candidate).strip()
    return ""


def event_is_allowed(event_name: str | None, env_value: str | None = None) -> bool:
    """Skip only when an event name is present and not on the allowlist.

    Missing/null/blank events are allowed through so GET + WOP status
    filtering can still run. Zuper's UI uses human labels; ``payload.event``
    may be a code form — we accept whatever is in the allowlist as-is.
    """
    if event_name is None or str(event_name).strip() == "":
        return True
    allowed = event_allowlist(env_value)
    return event_name.strip().casefold() in {item.casefold() for item in allowed}


def extract_job_uid(payload: dict[str, Any] | None) -> str | None:
    """Require job_uid. Payload often nests under ``data``."""
    if not isinstance(payload, dict):
        return None
    nested = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    nested_job = nested.get("job") if isinstance(nested.get("job"), dict) else {}
    payload_job = payload.get("job") if isinstance(payload.get("job"), dict) else {}
    for candidate in (
        payload.get("job_uid"),
        nested.get("job_uid"),
        nested_job.get("job_uid"),
        payload_job.get("job_uid"),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def unwrap_data(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    if isinstance(payload, dict):
        return payload
    return {}


# Live Get Job Details: current status is nested; job_status is a history array.
_CURRENT_STATUS_KEYS = (
    "current_job_status",
    "current_status",
    "job_current_status",
)
_STATUS_NAME_KEYS = ("status_name", "name", "job_status", "label", "value")


def _status_from_value(value: Any) -> str:
    """Extract a status name from a scalar or nested dict. History lists are ignored."""
    if isinstance(value, dict):
        for key in _STATUS_NAME_KEYS:
            nested = value.get(key)
            if nested is None or nested == "" or isinstance(nested, (dict, list)):
                continue
            text = str(nested).strip()
            if text:
                return text
        for key in ("status", "current_job_status", "current_status"):
            nested = value.get(key)
            if isinstance(nested, dict):
                text = _status_from_value(nested)
                if text:
                    return text
        return ""
    if isinstance(value, list):
        return ""
    if value is None:
        return ""
    return str(value).strip()


def _status_text(job: dict[str, Any]) -> str:
    """Current job status from live Get Job Details (not the job_status history array)."""
    for key in _CURRENT_STATUS_KEYS:
        if key not in job:
            continue
        text = _status_from_value(job.get(key))
        if text:
            return text
    for key in ("job_status", "status"):
        value = job.get(key)
        if isinstance(value, list):
            continue
        text = _status_from_value(value)
        if text:
            return text
    return ""


def wop_status_name() -> str:
    return os.environ.get("WOP_STATUS_NAME", DEFAULT_WOP_STATUS).strip() or DEFAULT_WOP_STATUS


def is_waiting_on_parts(job: dict[str, Any], status_name: str | None = None) -> bool:
    expected = (status_name or wop_status_name()).casefold()
    return _status_text(job).casefold() == expected


def module_sku_prefixes(env_value: str | None = None) -> list[str]:
    raw = env_value if env_value is not None else os.environ.get("MODULE_SKU_PREFIXES")
    if raw is None or str(raw).strip() == "":
        return list(DEFAULT_MODULE_SKU_PREFIXES)
    prefixes = parse_csv_env(raw)
    return prefixes or list(DEFAULT_MODULE_SKU_PREFIXES)


def _sku_matches_prefix(sku: str, prefixes: Iterable[str]) -> bool:
    folded = sku.strip().casefold()
    if not folded:
        return False
    return any(folded.startswith(prefix.strip().casefold()) for prefix in prefixes if prefix.strip())


def _iter_line_items(job: dict[str, Any]) -> list[Any]:
    """Collect candidate product/line-item collections without inventing rows."""
    items: list[Any] = []
    for key in (
        "products",
        "job_products",
        "line_items",
        "job_items",
        "parts",
        "product_details",
        "job_parts",
        "items",
    ):
        value = job.get(key)
        if isinstance(value, list):
            items.extend(value)
    return items


def _sku_from_item(item: Any) -> str | None:
    if isinstance(item, str) and item.strip():
        return item.strip()
    if not isinstance(item, dict):
        return None
    nested_product = item.get("product") if isinstance(item.get("product"), dict) else {}
    nested_part = item.get("part") if isinstance(item.get("part"), dict) else {}
    for candidate in (
        item.get("sku"),
        item.get("product_sku"),
        item.get("item_sku"),
        item.get("part_sku"),
        item.get("product_code"),
        item.get("product_id"),
        nested_product.get("product_sku"),
        nested_product.get("sku"),
        nested_product.get("product_id"),
        nested_part.get("sku"),
        nested_part.get("part_sku"),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def _qty_from_item(item: Any) -> int | float | None:
    """Return a numeric qty only when present. Never invent a quantity."""
    if not isinstance(item, dict):
        return None
    for key in ("qty", "quantity", "product_quantity", "count", "ordered_qty"):
        value = item.get(key)
        if value is None or value == "":
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
        try:
            as_str = str(value).strip()
            if as_str == "":
                continue
            if "." in as_str:
                return float(as_str)
            return int(as_str)
        except (TypeError, ValueError):
            return None
    return None


def extract_module_skus(
    job: dict[str, Any], prefixes: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """Return module SKUs found on the job that match configured prefixes.

    Fail honest: if a matching SKU has no qty, qty is null (not invented as 1).
    """
    prefix_list = list(prefixes) if prefixes is not None else module_sku_prefixes()
    found: dict[str, dict[str, Any]] = {}
    for item in _iter_line_items(job):
        sku = _sku_from_item(item)
        if not sku or not _sku_matches_prefix(sku, prefix_list):
            continue
        qty = _qty_from_item(item)
        existing = found.get(sku)
        if existing is None:
            found[sku] = {"sku": sku, "qty": qty}
            continue
        if existing["qty"] is None or qty is None:
            # Cannot sum unknown quantities — keep what we know, do not invent.
            if existing["qty"] is None and qty is not None:
                existing["qty"] = qty
            continue
        existing["qty"] = existing["qty"] + qty
    return list(found.values())


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def extract_gps(job: dict[str, Any]) -> tuple[float | None, float | None]:
    """Pull lat/lng from common Zuper job location shapes (incl. geo_cordinates typo)."""
    candidates: list[Any] = [
        job.get("customer_address"),
        job.get("job_address"),
        job.get("service_address"),
        job.get("job_location"),
        job.get("location"),
        job,
    ]
    for blob in candidates:
        if not isinstance(blob, dict):
            continue
        for coord_key in ("geo_cordinates", "geo_coordinates", "coordinates", "latlng"):
            coords = blob.get(coord_key)
            if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                lat = _as_float(coords[0])
                lng = _as_float(coords[1])
                if lat is not None and lng is not None:
                    return lat, lng
            if isinstance(coords, dict):
                lat = _as_float(coords.get("lat", coords.get("latitude")))
                lng = _as_float(coords.get("lng", coords.get("lon", coords.get("longitude"))))
                if lat is not None and lng is not None:
                    return lat, lng
        lat = _as_float(blob.get("latitude", blob.get("lat")))
        lng = _as_float(blob.get("longitude", blob.get("lng", blob.get("lon"))))
        if lat is not None and lng is not None:
            return lat, lng
    return None, None


def _parent_job_number(job: dict[str, Any]) -> str | None:
    parent = job.get("parent_job") or job.get("parent")
    if isinstance(parent, dict):
        for key in ("job_number", "work_order_number", "parent_job_number"):
            if parent.get(key):
                return str(parent[key])
    for key in ("parent_job_number", "parent_work_order", "parent_work_order_number"):
        if job.get(key):
            return str(job[key])
    return None


def _is_frp_child(job: dict[str, Any], parent_job_number: str | None) -> bool:
    if parent_job_number:
        return True
    if job.get("parent_job_uid") or job.get("parent_job_id"):
        return True
    if isinstance(job.get("parent_job"), dict) and job.get("parent_job"):
        return True
    category = job.get("job_category") or job.get("category") or ""
    if isinstance(category, dict):
        category = category.get("category_name") or category.get("name") or ""
    category_text = str(category).casefold()
    if "field requires parts" in category_text and (
        job.get("is_child") or job.get("is_child_job") or job.get("parent_job")
    ):
        return True
    return bool(job.get("is_frp_child"))


def _job_number(job: dict[str, Any]) -> str | None:
    """Prefer job_number; fall back to work_order_number (live Get Job Details)."""
    for key in ("job_number", "work_order_number"):
        value = job.get(key)
        if value is None or value == "":
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _job_title(job: dict[str, Any]) -> str | None:
    for key in ("job_title", "title", "work_order_title", "job_name"):
        if job.get(key):
            return str(job[key])
    return None


def _job_priority(job: dict[str, Any]) -> str | None:
    priority = job.get("job_priority", job.get("priority"))
    if isinstance(priority, dict):
        for key in ("priority_name", "name", "label", "value"):
            if priority.get(key):
                return str(priority[key])
        return None
    if priority is None or priority == "":
        return None
    return str(priority)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_notify_payload(
    job: dict[str, Any],
    *,
    zuper_event: str,
    received_at: str | None = None,
    job_uid: str | None = None,
    module_skus: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the downstream JSON notify body from a live Zuper job object."""
    lat, lng = extract_gps(job)
    parent_number = _parent_job_number(job)
    skus = module_skus if module_skus is not None else extract_module_skus(job)
    uid = job_uid or job.get("job_uid")
    if not uid:
        raise ValueError("job_uid is required to build a notify payload")
    return {
        "source": SOURCE_NAME,
        "zuper_event": zuper_event,
        "received_at": received_at or utc_now_iso(),
        "job_uid": str(uid),
        "job_number": _job_number(job),
        "title": _job_title(job),
        "status": _status_text(job) or wop_status_name(),
        "job_priority": _job_priority(job),
        "parent_job_number": parent_number,
        "is_frp_child": _is_frp_child(job, parent_number),
        "latitude": lat,
        "longitude": lng,
        "gps_missing": lat is None or lng is None,
        "module_skus_found": skus,
        "freshness_note": FRESHNESS_NOTE,
    }
