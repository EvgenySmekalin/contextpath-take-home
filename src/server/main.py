"""The server process: takes popups from agents, answers GET /audit.

Environment: PORT (default 8080), HOST (default 0.0.0.0), DB_PATH (default popups.db).
"""

import os
from datetime import datetime

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, field_validator

from server.store import PopupStore


class Popup(BaseModel):
    employee: str
    rule: str
    ts: str
    title: str
    body: str

    @field_validator("ts")
    @classmethod
    def _is_a_timestamp(cls, value: str) -> str:
        datetime.fromisoformat(value)  # raises ValueError, which becomes a 422 answer
        return value


def create_app(store: PopupStore) -> FastAPI:
    app = FastAPI(
        title="ContextPath server",
        description="Stores the popups that agents send and gives them back.",
    )

    @app.get("/healthz", summary="Is the server up?")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.post("/popups", summary="Store one popup")
    def add_popup(popup: Popup) -> dict:
        """Called by agents. A popup that is already stored is ignored, so repeating is safe."""
        store.add(popup.model_dump())
        return {"status": "ok"}

    @app.get("/audit", summary="List stored popups")
    def audit(employee: str | None = None, rule: str | None = None) -> list[Popup]:
        """All popups, oldest first. Both filters are optional and can be combined."""
        return store.find(employee, rule)

    return app


def main() -> None:
    store = PopupStore(os.environ.get("DB_PATH", "popups.db"))
    uvicorn.run(
        create_app(store),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
