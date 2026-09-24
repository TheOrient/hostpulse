# HostPulse

A tiny HTTP health checker for the kinds of websites and game-community services I used to host. I wanted a single command that could answer: **is the page reachable, is the status what I expect, and did it return the expected text?**

This is deliberately a small tool, not a monitoring platform. It uses only the Python standard library, runs once, and returns exit code `0` when all checks pass, `1` when at least one fails, and `2` for invalid configuration. That makes it easy to use from a scheduled job or deployment script.

## Quick start

Python 3.10+ is enough. Put your own endpoints in a JSON file based on [checks.example.json](checks.example.json), then run:

```sh
python3 hostpulse.py checks.example.json
python3 hostpulse.py checks.example.json --json
python3 -m unittest discover -s tests -v
```

The example points at `127.0.0.1:8000`; it will report a failure unless you have a local service running there. For each endpoint, `name` and `url` are required. `expected_status` defaults to `200`. Optional `contains` looks for literal text in the first 1 MiB of the response.

Example output:

```text
OK    local website: HTTP 200, 19 ms
FAIL  staging API: HTTP 503, 41 ms — expected HTTP 200
```

## Design choices and limits

- Only `http` and `https` URLs are accepted. Credentials in URLs are rejected; keep configuration files free of secrets.
- Checks run sequentially, with a configurable per-request timeout (default five seconds). This keeps the tool understandable for a small list of services.
- The tool does not store response bodies, send alerts, or collect uptime history. It reports a status, rough elapsed time, and a short failure reason.
- The optional text match is literal and case-sensitive; it is not an HTML parser. A mismatch cannot tell you *why* a site is unhealthy.
- Use only endpoints you own or are authorized to check. A configuration file is treated as trusted input.

The project grew from my hosting and server-support experience. AI-assisted coding helped with implementation and tests; I reviewed the behavior and kept the scope intentionally modest. See the tests for local HTTP server examples, including expected 404 responses and failure exit codes.

## License

MIT — see [LICENSE](LICENSE).
