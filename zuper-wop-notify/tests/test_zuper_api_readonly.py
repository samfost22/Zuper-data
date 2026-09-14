"""Guard: this package must stay GET-only toward Zuper."""

from __future__ import annotations

from pathlib import Path

import zuper_api

ROOT = Path(__file__).resolve().parents[1]


def test_zuper_api_exposes_get_job_detail_only():
    assert hasattr(zuper_api.ZuperReadOnlyClient, "get_job_detail")
    write_names = [
        name
        for name in dir(zuper_api.ZuperReadOnlyClient)
        if name.startswith(("put", "patch", "post", "create", "update", "delete", "schedule"))
    ]
    assert write_names == []


def test_zuper_api_source_has_no_write_helpers():
    source = (ROOT / "zuper_api.py").read_text()
    for needle in (
        "requests.put",
        "requests.patch",
        "requests.post",
        "session.put",
        "session.patch",
        "session.post",
        ".put(",
        ".patch(",
    ):
        assert needle not in source
    assert "requests.get" in source
    assert "def get_job_detail" in source
