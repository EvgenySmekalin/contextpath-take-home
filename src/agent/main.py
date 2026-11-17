"""The agent process: receives ticks from its streamer, sends popups to the server.

Environment: AGENT_PORT, SERVER_URL, RULES_PATH (default rules.json).
"""

import logging
import os
import time
from collections.abc import Callable
from dataclasses import asdict

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.engine import Engine, Popup
from agent.rules import Rule, load_rules
from agent.screen import Screen

log = logging.getLogger("agent")

# How long a popup is retried while the server is unreachable.
DELIVERY_ATTEMPTS = 60
DELIVERY_PAUSE_S = 1


class Display(BaseModel):
    id: int
    bounds: tuple[float, float, float, float]  # left, top, width, height


class Session(BaseModel):
    employee_id: str
    displays: list[Display]


class Event(BaseModel):
    kind: str
    ts: str
    data: dict


def create_app(rules: list[Rule], deliver: Callable[[Popup], None]) -> FastAPI:
    app = FastAPI()
    engines: list[Engine] = []  # empty until the streamer has sent the session

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/session")
    def start_session(session: Session) -> dict:
        screen = Screen({display.id: display.bounds for display in session.displays})
        engines[:] = [Engine(rules, session.employee_id, screen)]
        return {"status": "ok"}

    @app.post("/ticks")
    def handle_tick(events: list[Event]) -> dict:
        if not engines:
            raise HTTPException(409, "no session: POST /session first")
        popups = [
            popup for event in events for popup in engines[0].feed(event.kind, event.ts, event.data)
        ]
        for popup in popups:
            deliver(popup)
            # The body is not logged: it contains what was on the employee's screen.
            log.info("%s: popup %s at %s", popup.employee, popup.rule, popup.ts)
        return {"popups": len(popups)}

    return app


def send_to_server(server_url: str, popup: Popup) -> None:
    """POST the popup until the server takes it. The server ignores repeats."""
    for _ in range(DELIVERY_ATTEMPTS):
        try:
            httpx.post(f"{server_url}/popups", json=asdict(popup), timeout=10).raise_for_status()
            return
        except httpx.HTTPError:
            time.sleep(DELIVERY_PAUSE_S)
    raise RuntimeError("the server did not accept the popup")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    rules = load_rules(os.environ.get("RULES_PATH", "rules.json"))
    server_url = os.environ["SERVER_URL"].rstrip("/")
    app = create_app(rules, deliver=lambda popup: send_to_server(server_url, popup))
    # Loopback only: nobody but the streamer on the same machine talks to the agent.
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ["AGENT_PORT"]), log_level="warning")


if __name__ == "__main__":
    main()
