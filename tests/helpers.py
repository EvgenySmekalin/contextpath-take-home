"""Shared by several test modules."""

import io
import json
import socket
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Popups expected from the provided recordings and rules: (rule, event time
# truncated to milliseconds), in time order. Established by inspecting the
# recordings by hand.
EXPECTED_POPUPS = {
    "emp-1": [
        ("forwarded-email-opened", "2026-03-10T23:15:21.309"),
        ("forwarded-email-opened", "2026-03-10T23:15:27.323"),
        ("urgent-email-opened", "2026-03-10T23:15:27.323"),
        # The same email clicked again one second later: a separate click.
        ("forwarded-email-opened", "2026-03-10T23:15:28.334"),
        ("urgent-email-opened", "2026-03-10T23:15:28.334"),
        # Followed 160 ms later by the second half of a double click: no repeat.
        ("forwarded-email-opened", "2026-03-10T23:15:47.740"),
        ("forwarded-email-opened", "2026-03-10T23:52:37.267"),
    ],
    "emp-2": [
        ("forwarded-email-opened", "2026-03-10T16:05:25.058"),
        ("jira-ticket-done", "2026-03-10T16:09:47.594"),
        ("invoice-ready-to-attach", "2026-03-10T16:38:31.825"),
        ("invoice-ready-to-attach", "2026-03-10T16:39:13.828"),
    ],
    "emp-3": [
        ("invoice-ready-to-attach", "2026-03-10T21:21:32.004"),
        ("forwarded-email-opened", "2026-03-10T21:21:32.491"),
        ("salesforce-record-deleted", "2026-03-10T22:12:35.415"),
    ],
}

POPUP_FIELDS = {"employee", "rule", "ts", "title", "body"}


def expected_audit() -> list[tuple[str, str, str]]:
    return sorted(
        (employee, rule, ts) for employee, popups in EXPECTED_POPUPS.items() for rule, ts in popups
    )


def summarize_audit(popups: list[dict]) -> list[tuple[str, str, str]]:
    """Reduce an /audit answer to what ``expected_audit`` describes."""
    assert all(set(p) == POPUP_FIELDS for p in popups), "a popup must have exactly five fields"
    return sorted((p["employee"], p["rule"], p["ts"][:23]) for p in popups)


def fetch_json(url: str, timeout_s: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout_s) as response:
        return json.load(response)


def wait_until_healthy(base_url: str, timeout_s: float = 20.0) -> None:
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            fetch_json(f"{base_url}/healthz", timeout_s=1.0)
            return
        except OSError:
            if time.monotonic() > deadline:
                raise TimeoutError(f"{base_url} did not become healthy") from None
            time.sleep(0.1)


def free_ports(count: int) -> int:
    """First port of a run of ``count`` consecutive free loopback ports."""
    for _ in range(50):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            first = probe.getsockname()[1]
        try:
            for port in range(first, first + count):
                with socket.socket() as check:
                    check.bind(("127.0.0.1", port))
        except OSError:
            continue
        return first
    raise RuntimeError("no free ports")


def make_tarball(path, files: dict[str, str]) -> str:
    with tarfile.open(path, "w:gz") as tar:
        for name, content in files.items():
            raw = content.encode()
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))
    return str(path)


def jsonl(*rows: dict) -> str:
    return "\n".join(json.dumps(r) for r in rows) + "\n"
