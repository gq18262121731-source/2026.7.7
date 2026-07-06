"""Smoke test for the local Phone RiceLeafDiseaseBD weak class review app."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the phone weak class review app.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8787")
    return parser.parse_args()


def fetch(method: str, url: str, body: bytes | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = response.read(256)
            return {
                "status": response.status,
                "content_type": response.headers.get("Content-Type", ""),
                "content_length": response.headers.get("Content-Length", ""),
                "body_prefix": payload.decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        payload = exc.read(256)
        return {
            "status": exc.code,
            "content_type": exc.headers.get("Content-Type", ""),
            "content_length": exc.headers.get("Content-Length", ""),
            "body_prefix": payload.decode("utf-8", errors="replace"),
        }


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    checks = [
        ("GET", "/", None),
        ("GET", "/healthz", None),
        ("GET", "/api/items", None),
        ("GET", "/api/summary", None),
        ("GET", "/api/preview-status/leaf_smut_001", None),
        ("GET", "/api/preview/leaf_smut_001", None),
        ("GET", "/media/preview/leaf_smut_001", None),
        ("GET", "/app.js", None),
        ("GET", "/style.css", None),
        ("GET", "/styles.css", None),
        ("GET", "/favicon.ico", None),
        ("GET", "/not-found-test", None),
        (
            "POST",
            "/api/decision",
            json.dumps(
                {
                    "review_id": "leaf_smut_001",
                    "issue_type": "ok",
                    "review_status": "reviewed",
                    "reviewer_notes": "smoke test",
                }
            ).encode("utf-8"),
        ),
        ("POST", "/api/reset", b"{}"),
    ]

    results: list[dict[str, Any]] = []
    for method, path, body in checks:
        result = fetch(method, base_url + path, body)
        result["method"] = method
        result["path"] = path
        results.append(result)

    sys.stdout.buffer.write((json.dumps(results, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
