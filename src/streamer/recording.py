"""Read one recording tarball and cut it into one-second ticks."""

import json
import tarfile
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import PurePosixPath


def load_recording(path: str) -> tuple[dict, list[dict]]:
    """Return ``metadata.json`` and the events of every ``events/*.jsonl``, oldest first.

    An event is ``{"kind": <name of its file>, "ts": ..., "data": <the recorded row>}``.
    The tarball is read in place and never extracted to disk.
    """
    metadata = None
    events = []
    with tarfile.open(path) as tar:
        for member in tar:
            name = PurePosixPath(member.name)
            # "._name" files are metadata that macOS tar adds next to every real file.
            if not member.isfile() or name.name.startswith("._"):
                continue
            if name.name == "metadata.json":
                metadata = json.load(tar.extractfile(member))
            elif name.parent.name == "events" and name.suffix == ".jsonl":
                for line in tar.extractfile(member):
                    if line.strip():
                        row = json.loads(line)
                        events.append({"kind": name.stem, "ts": row["ts"], "data": row})
    if metadata is None:
        raise ValueError(f"{path}: metadata.json not found")
    # The sort is stable: events with the same timestamp keep their file order.
    events.sort(key=_time)
    return metadata, events


def iter_ticks(events: list[dict]) -> Iterator[list[dict]]:
    """Yield the events of each second, from the first event to the last.

    Seconds in which nothing happened are yielded as empty ticks, so the
    replay keeps the rhythm of the recording.
    """
    if not events:
        return
    tick_end = _time(events[0]).replace(microsecond=0)
    position = 0
    while position < len(events):
        tick_end += timedelta(seconds=1)
        tick = []
        while position < len(events) and _time(events[position]) < tick_end:
            tick.append(events[position])
            position += 1
        yield tick


def _time(event: dict) -> datetime:
    # Timestamps have 3, 6 or 9 fractional digits, so they cannot be compared as text.
    return datetime.fromisoformat(event["ts"])
