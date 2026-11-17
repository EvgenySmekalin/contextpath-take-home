"""Popups in a SQLite file."""

import sqlite3
from contextlib import closing
from datetime import datetime

FIELDS = ("employee", "rule", "ts", "title", "body")


class PopupStore:
    def __init__(self, path: str):
        self._path = path
        with self._connect() as db, db:
            # Agents repeat a popup when they are not sure it arrived, so the
            # same popup must be stored once.
            db.execute(
                "CREATE TABLE IF NOT EXISTS popups ("
                " employee TEXT, rule TEXT, ts TEXT, title TEXT, body TEXT,"
                " UNIQUE (employee, rule, ts, title, body))"
            )

    def add(self, popup: dict) -> None:
        with self._connect() as db, db:
            db.execute(
                "INSERT OR IGNORE INTO popups VALUES (:employee, :rule, :ts, :title, :body)",
                popup,
            )

    def find(self, employee: str | None = None, rule: str | None = None) -> list[dict]:
        """Popups of one employee and/or one rule (all if not given), oldest first."""
        with self._connect() as db:
            rows = db.execute(
                "SELECT employee, rule, ts, title, body FROM popups"
                " WHERE (:employee IS NULL OR employee = :employee)"
                " AND (:rule IS NULL OR rule = :rule)",
                {"employee": employee, "rule": rule},
            ).fetchall()
        popups = [dict(zip(FIELDS, row, strict=True)) for row in rows]
        # Timestamps differ in the number of fractional digits, so the order
        # comes from the parsed time, not from the text.
        return sorted(popups, key=lambda p: (datetime.fromisoformat(p["ts"]), p["employee"]))

    def _connect(self):
        # One short-lived connection per call: requests are handled on several threads.
        return closing(sqlite3.connect(self._path))
