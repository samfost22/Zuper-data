"""Flask receiver for Zuper webhooks → WOP filter → JSON fan-out.

READ-ONLY toward Zuper. Fan-out failures return 200 so Zuper does not retry-storm.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request

import fanout as fanout_mod
import filters
from zuper_api import ZuperAPIError, get_job_detail

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("zuper-wop-notify")


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok", "service": "zuper-wop-notify"}), 200

    @app.post("/zuper-webhook")
    def zuper_webhook():
        return _handle_webhook(dry_run=False)

    @app.post("/dry-run")
    def dry_run():
        return _handle_webhook(dry_run=True)

    return app


def _unauthorized():
    return jsonify({"ok": False, "error": "unauthorized"}), 401


def _handle_webhook(dry_run: bool) -> tuple[Any, int]:
    if not filters.webhook_secret_is_valid(request.headers):
        logger.warning("Rejected webhook: bad or missing secret")
        return _unauthorized()

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        logger.error("Rejected webhook: body is not a JSON object")
        return jsonify({"ok": False, "error": "invalid_json"}), 400

    event_name = filters.extract_event_name(payload)
    if not filters.event_is_allowed(event_name):
        logger.info("Skipped webhook: event_not_allowed event=%s", event_name)
        return (
            jsonify(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "event_not_allowed",
                    "event": event_name,
                    "dry_run": dry_run,
                }
            ),
            200,
        )

    job_uid = filters.extract_job_uid(payload)
    if not job_uid:
        logger.error("Rejected webhook: missing job_uid event=%s", event_name)
        return jsonify({"ok": False, "error": "missing_job_uid", "event": event_name}), 400

    try:
        job = get_job_detail(job_uid)
    except ZuperAPIError as exc:
        logger.exception("Zuper GET failed job_uid=%s", job_uid)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "zuper_get_failed",
                    "job_uid": job_uid,
                    "detail": str(exc),
                }
            ),
            502,
        )

    if not filters.is_waiting_on_parts(job):
        logger.info(
            "Skipped webhook: not_wop job_uid=%s status=%s",
            job_uid,
            filters._status_text(job),
        )
        return (
            jsonify(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "not_wop",
                    "job_uid": job_uid,
                    "event": event_name,
                    "dry_run": dry_run,
                }
            ),
            200,
        )

    module_skus = filters.extract_module_skus(job)
    if not module_skus:
        logger.info("Skipped webhook: not_module job_uid=%s", job_uid)
        return (
            jsonify(
                {
                    "ok": True,
                    "skipped": True,
                    "reason": "not_module",
                    "job_uid": job_uid,
                    "event": event_name,
                    "dry_run": dry_run,
                }
            ),
            200,
        )

    notify_payload = filters.build_notify_payload(
        job,
        zuper_event=event_name,
        job_uid=job_uid,
        module_skus=module_skus,
    )

    if dry_run:
        logger.info("Dry-run match job_uid=%s skus=%s", job_uid, module_skus)
        return (
            jsonify(
                {
                    "ok": True,
                    "notified": False,
                    "dry_run": True,
                    "job_uid": job_uid,
                    "payload": notify_payload,
                }
            ),
            200,
        )

    fanout_results = fanout_mod.fanout(notify_payload)
    logger.info(
        "Notified job_uid=%s fanout=%s",
        job_uid,
        fanout_results,
    )
    return (
        jsonify(
            {
                "ok": True,
                "notified": True,
                "dry_run": False,
                "job_uid": job_uid,
                "payload": notify_payload,
                "fanout": fanout_results,
            }
        ),
        200,
    )


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
