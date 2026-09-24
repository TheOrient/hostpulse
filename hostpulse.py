"""A small, dependency-free HTTP health checker for hosting projects."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def load_checks(path: Path) -> list[dict]:
    """Read and validate a list of trusted endpoint checks."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Configuration must be a non-empty JSON list")

    names = set()
    checks = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Check {index} must be an object")
        name = item.get("name")
        url = item.get("url")
        expected_status = item.get("expected_status", 200)
        contains = item.get("contains")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError(f"Check {index} needs a unique, non-empty name")
        if not isinstance(url, str):
            raise ValueError(f"{name}: url must be a string")
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError(f"{name}: url must start with http:// or https://")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError(f"{name}: do not put credentials or fragments in the URL")
        if type(expected_status) is not int or not 100 <= expected_status <= 599:
            raise ValueError(f"{name}: expected_status must be an HTTP status code")
        if contains is not None and (not isinstance(contains, str) or not contains):
            raise ValueError(f"{name}: contains must be a non-empty string")
        names.add(name)
        checks.append({"name": name, "url": url, "expected_status": expected_status, "contains": contains})
    return checks


def check_endpoint(check: dict, timeout: float) -> dict:
    """Return a compact result without storing response bodies or secrets."""
    started = time.monotonic()
    result = {"name": check["name"], "ok": False, "status": None, "latency_ms": None, "reason": ""}
    try:
        request = Request(check["url"], headers={"User-Agent": "HostPulse/1.0"})
        try:
            response = urlopen(request, timeout=timeout)
        except HTTPError as error:
            response = error
        with response:
            result["status"] = response.status
            if response.status != check["expected_status"]:
                result["reason"] = f"expected HTTP {check['expected_status']}"
            elif check["contains"] is not None:
                # Cap reads so a health check never downloads an arbitrarily large page.
                body = response.read(1024 * 1024).decode("utf-8", errors="replace")
                if check["contains"] not in body:
                    result["reason"] = "expected text missing from first 1 MiB"
                else:
                    result["ok"] = True
            else:
                result["ok"] = True
    except (URLError, TimeoutError, OSError) as error:
        result["reason"] = f"request failed: {type(error).__name__}"
    finally:
        result["latency_ms"] = round((time.monotonic() - started) * 1000)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a few trusted HTTP endpoints and exit nonzero if any fail.")
    parser.add_argument("config", type=Path, help="JSON list of named endpoints")
    parser.add_argument("--timeout", type=float, default=5.0, help="per-request timeout in seconds (default: 5)")
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    args = parser.parse_args(argv)
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than 0 and at most 60")
    try:
        checks = load_checks(args.config)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    results = [check_endpoint(check, args.timeout) for check in checks]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for result in results:
            state = "OK" if result["ok"] else "FAIL"
            status = result["status"] if result["status"] is not None else "-"
            detail = f" — {result['reason']}" if result["reason"] else ""
            print(f"{state:4}  {result['name']}: HTTP {status}, {result['latency_ms']} ms{detail}")
    return 0 if all(result["ok"] for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
