"""The stack exactly as a reviewer starts it: ``docker compose up``.

Checks the packaging that the process-level tests cannot see: the image
builds, the compose file mounts ./data and ./rules.json where the code looks
for them, and the server answers on localhost:8080.

Slow and needs Docker, so it is opt-in: ``pytest -m docker``.
"""

import os
import subprocess

import pytest
from helpers import ROOT, expected_audit, fetch_json, summarize_audit

pytestmark = pytest.mark.docker


def compose(*args: str, check: bool = True, timeout_s: float = 600) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=ROOT,
        env={**os.environ, "TICK_MS": "2"},
        check=check,
        timeout=timeout_s,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def stack():
    compose("down", check=False)
    try:
        compose("up", "--build", "-d")
        yield
    finally:
        compose("down", check=False)


def test_docker_compose_up_serves_the_expected_audit(stack):
    # `wait` prints the exit code of the container and returns it.
    finished = compose("wait", "employees", check=False)
    assert finished.returncode == 0, compose("logs", "employees", check=False).stdout[-2000:]

    assert summarize_audit(fetch_json("http://localhost:8080/audit")) == expected_audit()

    states = compose("ps", "--format", "{{.Service}}={{.State}}").stdout.split()
    assert "server=running" in states, "the server must outlive the replay"
