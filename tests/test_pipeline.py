"""The whole pipeline as real processes talking real HTTP on loopback.

Nothing is imported from the application and nothing is faked: the tests
start ``server.main`` and ``launcher`` (which starts a
streamer and an agent per recording) the same way the container does, and
look only at what an outsider can see: ``GET /audit`` and exit codes.
"""

import json
import os
import subprocess
import sys
import time

import pytest
from helpers import (
    ROOT,
    expected_audit,
    fetch_json,
    free_ports,
    jsonl,
    make_tarball,
    summarize_audit,
    wait_until_healthy,
)

REPLAY_TIMEOUT_S = 120


def start_server(port: int, db_path) -> subprocess.Popen:
    env = {**os.environ, "HOST": "127.0.0.1", "PORT": str(port), "DB_PATH": str(db_path)}
    return subprocess.Popen(
        [sys.executable, "-m", "server.main"],
        cwd=ROOT / "src",
        env=env,
        stdout=subprocess.DEVNULL,
    )


def start_launcher(server_url: str, data_dir, rules_path=ROOT / "rules.json") -> subprocess.Popen:
    env = {
        **os.environ,
        "DATA_DIR": str(data_dir),
        "RULES_PATH": str(rules_path),
        "SERVER_URL": server_url,
        "TICK_MS": "0",
        "AGENT_BASE_PORT": str(free_ports(8)),
    }
    return subprocess.Popen(
        [sys.executable, "-m", "launcher"],
        cwd=ROOT / "src",
        env=env,
        stdout=subprocess.DEVNULL,
    )


def stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


@pytest.fixture
def server(tmp_path):
    port = free_ports(1)
    process = start_server(port, tmp_path / "popups.db")
    url = f"http://127.0.0.1:{port}"
    try:
        wait_until_healthy(url)
        yield url
    finally:
        stop(process)


@pytest.fixture
def one_email_recording(tmp_path):
    """A three-event recording that makes ``forwarded-email-opened`` fire once."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    metadata = {
        "employee_id": "emp-test",
        "session_id": "s1",
        "started_at": "2026-03-10T10:00:00.000Z",
        "ended_at": "2026-03-10T10:00:03.000Z",
        "machine": {"displays": [{"id": 0, "bounds": [0, 0, 1920, 1080]}]},
    }
    focus = {
        "ts": "2026-03-10T10:00:01.000Z",
        "event": "focus_change",
        "process_name": "OUTLOOK.EXE",
        "window_title": "Inbox - Outlook",
    }
    snapshot = {
        "ts": "2026-03-10T10:00:01.200Z",
        "filename": "a.jpg",
        "display_id": 0,
        "resolution": [1920, 1080],
        "ocr_text_blocks": [{"text": "FW: hello", "bounding_box": [100, 200, 300, 20]}],
    }
    click = {
        "ts": "2026-03-10T10:00:01.500Z",
        "event": "click",
        "button": "left",
        "mouse_x": 150,
        "mouse_y": 210,
        "click_count": "single",
    }
    make_tarball(
        data_dir / "emp-test.tar.gz",
        {
            "s1/metadata.json": json.dumps(metadata),
            "s1/events/windows.jsonl": jsonl(focus),
            "s1/events/ocr.jsonl": jsonl(snapshot),
            "s1/events/mouse.jsonl": jsonl(click),
        },
    )
    return data_dir


def test_provided_recordings_end_to_end(server):
    if not list((ROOT / "data").glob("*.tar.gz")):
        pytest.skip("the provided recordings are not available")

    launcher = start_launcher(server, ROOT / "data")
    assert launcher.wait(timeout=REPLAY_TIMEOUT_S) == 0

    audit = fetch_json(f"{server}/audit")
    assert summarize_audit(audit) == expected_audit()
    assert [p["ts"] for p in audit] == sorted(p["ts"] for p in audit)

    only_emp2 = fetch_json(f"{server}/audit?employee=emp-2")
    assert {p["employee"] for p in only_emp2} == {"emp-2"} and len(only_emp2) == 4
    forwarded = fetch_json(f"{server}/audit?rule=forwarded-email-opened")
    assert {p["rule"] for p in forwarded} == {"forwarded-email-opened"} and len(forwarded) == 7
    (deleted,) = fetch_json(f"{server}/audit?employee=emp-3&rule=salesforce-record-deleted")
    assert deleted["body"] == "Deleted in Salesforce: 00482913 | Case | Salesforce - Google Chrome"
    assert fetch_json(f"{server}/audit?employee=nobody") == []


def test_popups_are_delivered_when_the_server_comes_up_late(tmp_path, one_email_recording):
    port = free_ports(1)
    url = f"http://127.0.0.1:{port}"
    launcher = start_launcher(url, one_email_recording)
    time.sleep(2)  # the replay is long over; the agent is holding the popup
    assert launcher.poll() is None, "the agent must wait for the server, not give up"

    server_process = start_server(port, tmp_path / "popups.db")
    try:
        wait_until_healthy(url)
        assert launcher.wait(timeout=60) == 0
        (popup,) = fetch_json(f"{url}/audit")

        # Replaying the same recording into the same server changes nothing.
        again = start_launcher(url, one_email_recording)
        assert again.wait(timeout=60) == 0
        assert fetch_json(f"{url}/audit") == [popup]
    finally:
        stop(server_process)
        stop(launcher)
    assert popup == {
        "employee": "emp-test",
        "rule": "forwarded-email-opened",
        "ts": "2026-03-10T10:00:01.500Z",
        "title": "Forwarded email",
        "body": "You opened a forwarded email: FW: hello",
    }


def test_invalid_rules_fail_the_run(server, tmp_path, one_email_recording):
    rules = tmp_path / "rules.json"
    rules.write_text('{"rules": [{"id": "r", "when": {"clik": "x"}, "popup": {}}]}')
    launcher = start_launcher(server, one_email_recording, rules_path=rules)
    assert launcher.wait(timeout=60) != 0
    assert fetch_json(f"{server}/audit") == []


def test_unreadable_recording_fails_the_run(server, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "broken.tar.gz").write_bytes(b"this is not a tarball")
    launcher = start_launcher(server, data_dir)
    assert launcher.wait(timeout=60) != 0


def test_no_recordings_fail_the_run(server, tmp_path):
    launcher = start_launcher(server, tmp_path)
    assert launcher.wait(timeout=30) != 0
