"""Fan-out JSON notifies to Shop Manager Bot and optional Parts Bot.

Fan-out HTTP failures are returned to the caller as structured results.
The webhook receiver must still 200 back to Zuper to avoid retry storms.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10
SHOP_TARGET = "shop_manager"
PARTS_TARGET = "parts_bot"


def _timeout_seconds() -> float:
    raw = os.environ.get("NOTIFY_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT_SECONDS))
    try:
        return float(raw)
    except (TypeError, ValueError):
        return float(DEFAULT_TIMEOUT_SECONDS)


def _notify_token() -> str | None:
    token = os.environ.get("NOTIFY_TOKEN") or os.environ.get("X_NOTIFY_TOKEN")
    if token and str(token).strip():
        return str(token).strip()
    return None


def post_notify(
    url: str,
    payload: dict[str, Any],
    *,
    token: str | None = None,
    timeout_seconds: float | None = None,
    target: str = "webhook",
) -> dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["X-Notify-Token"] = token
    timeout = timeout_seconds if timeout_seconds is not None else _timeout_seconds()
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    except requests.Timeout as exc:
        logger.error("Fan-out timeout target=%s url=%s error=%s", target, url, exc)
        return {"ok": False, "target": target, "error": f"timeout: {exc}"}
    except requests.RequestException as exc:
        logger.error("Fan-out request failed target=%s url=%s error=%s", target, url, exc)
        return {"ok": False, "target": target, "error": str(exc)}

    ok = 200 <= response.status_code < 300
    if not ok:
        logger.error(
            "Fan-out HTTP %s target=%s body=%s",
            response.status_code,
            target,
            response.text[:500],
        )
    else:
        logger.info("Fan-out ok target=%s status=%s", target, response.status_code)
    return {
        "ok": ok,
        "target": target,
        "status_code": response.status_code,
        "body": response.text[:500],
    }


def fanout(payload: dict[str, Any]) -> dict[str, Any]:
    """POST to Shop Manager (required URL) and Parts Bot (optional URL)."""
    token = _notify_token()
    timeout = _timeout_seconds()
    results: dict[str, Any] = {}

    shop_url = (os.environ.get("SHOP_MANAGER_WEBHOOK_URL") or "").strip()
    if not shop_url:
        logger.error("SHOP_MANAGER_WEBHOOK_URL is not set; cannot notify Shop Manager Bot")
        results[SHOP_TARGET] = {
            "ok": False,
            "target": SHOP_TARGET,
            "error": "SHOP_MANAGER_WEBHOOK_URL is not set",
        }
    else:
        results[SHOP_TARGET] = post_notify(
            shop_url,
            payload,
            token=token,
            timeout_seconds=timeout,
            target=SHOP_TARGET,
        )

    parts_url = (os.environ.get("PARTS_BOT_WEBHOOK_URL") or "").strip()
    if not parts_url:
        results[PARTS_TARGET] = {
            "ok": True,
            "target": PARTS_TARGET,
            "skipped": True,
            "reason": "PARTS_BOT_WEBHOOK_URL not set",
        }
    else:
        results[PARTS_TARGET] = post_notify(
            parts_url,
            payload,
            token=token,
            timeout_seconds=timeout,
            target=PARTS_TARGET,
        )

    logger.info("Fan-out results: %s", results)
    return results
