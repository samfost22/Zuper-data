"""Read-only Zuper client.

Hard constraint: GET job details only. Never PATCH/PUT/POST to Zuper.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

DEFAULT_ZUPER_BASE_URL = "https://us-east-1.zuperpro.com"
DEFAULT_TIMEOUT_SECONDS = 20


class ZuperAPIError(RuntimeError):
    """Raised when a Zuper GET fails or returns an unexpected body."""


class ZuperReadOnlyClient:
    """Thin GET-only client for job detail."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("ZUPER_API_KEY", "")
        raw_base = (
            base_url
            if base_url is not None
            else os.environ.get("ZUPER_BASE_URL", DEFAULT_ZUPER_BASE_URL)
        )
        self.base_url = (raw_base or DEFAULT_ZUPER_BASE_URL).rstrip("/")
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else float(os.environ.get("ZUPER_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
        )

    def get_job_detail(self, job_uid: str) -> dict[str, Any]:
        """GET /api/jobs/{job_uid} and unwrap a nested ``data`` object.

        Fail loud: missing key, non-200, or non-object body raises.
        """
        if not job_uid or not str(job_uid).strip():
            raise ZuperAPIError("job_uid is required")
        if not self.api_key:
            raise ZuperAPIError("ZUPER_API_KEY is not set")

        url = f"{self.base_url}/api/jobs/{job_uid}"
        headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json",
        }
        logger.info("Zuper GET job detail job_uid=%s", job_uid)
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        except requests.RequestException as exc:
            raise ZuperAPIError(f"Zuper GET failed: {exc}") from exc

        if response.status_code != 200:
            raise ZuperAPIError(
                f"Zuper GET {url} returned HTTP {response.status_code}: {response.text[:500]}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise ZuperAPIError("Zuper GET returned non-JSON body") from exc

        return unwrap_job_payload(body)


def unwrap_job_payload(body: Any) -> dict[str, Any]:
    """Return the job object, unwrapping a nested ``data`` dict when present."""
    if not isinstance(body, dict):
        raise ZuperAPIError(f"Zuper job payload is not an object: {type(body).__name__}")
    data = body.get("data")
    if isinstance(data, dict):
        return data
    if "job_uid" in body or "job_number" in body or "job_status" in body:
        return body
    raise ZuperAPIError("Zuper job payload missing data object and job fields")


def get_job_detail(job_uid: str) -> dict[str, Any]:
    """Module-level helper used by the webhook receiver."""
    return ZuperReadOnlyClient().get_job_detail(job_uid)
