"""Replay one recording to one agent, one tick per recorded second.

Environment: RECORDING (path to a .tar.gz), AGENT_URL, TICK_MS (real
milliseconds per tick, default 20).
"""

import logging
import os
import time

import httpx

from streamer.recording import iter_ticks, load_recording

log = logging.getLogger("streamer")

AGENT_STARTUP_S = 30
# A tick can take long when the agent is waiting for the server to come back.
TICK_TIMEOUT_S = 120


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    tick_s = float(os.environ.get("TICK_MS", "20")) / 1000

    metadata, events = load_recording(os.environ["RECORDING"])
    session = {
        "employee_id": metadata["employee_id"],
        "displays": [
            {"id": display["id"], "bounds": display["bounds"]}
            for display in metadata["machine"]["displays"]
        ],
    }
    log.info("%s: replaying %d events", session["employee_id"], len(events))

    with httpx.Client(base_url=os.environ["AGENT_URL"], timeout=TICK_TIMEOUT_S) as agent:
        wait_until_ready(agent)
        agent.post("/session", json=session).raise_for_status()
        started = time.monotonic()
        for number, tick in enumerate(iter_ticks(events)):
            # Pace against the start time, so that slow ticks do not add up.
            pause = started + number * tick_s - time.monotonic()
            if pause > 0:
                time.sleep(pause)
            agent.post("/ticks", json=tick).raise_for_status()

    log.info("%s: done in %.1f s", session["employee_id"], time.monotonic() - started)


def wait_until_ready(agent: httpx.Client) -> None:
    """The agent is started at the same moment as the streamer and needs a second."""
    deadline = time.monotonic() + AGENT_STARTUP_S
    while True:
        try:
            agent.get("/healthz").raise_for_status()
            return
        except httpx.HTTPError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


if __name__ == "__main__":
    main()
