import json

import pytest
from helpers import jsonl, make_tarball

from streamer.recording import iter_ticks, load_recording

METADATA = json.dumps({"employee_id": "emp-9", "machine": {"displays": []}})


@pytest.fixture
def tarball(tmp_path):
    return make_tarball(
        tmp_path / "emp-9.tar.gz",
        {
            "s1/metadata.json": METADATA,
            "s1/._metadata.json": "macOS junk",
            "s1/events/mouse.jsonl": jsonl(
                {"ts": "2026-03-10T10:00:01.500Z", "event": "click"},
                {"ts": "2026-03-10T10:00:03.000Z", "event": "click"},
            ),
            "s1/events/ocr.jsonl": jsonl(
                {"ts": "2026-03-10T10:00:00.300Z", "filename": "early.jpg"},
                {"ts": "2026-03-10T10:00:01.100200300Z", "filename": "a.jpg"},
            ),
            "s1/notes.txt": "ignored",
        },
    )


def test_loads_metadata_and_merges_event_files_by_time(tarball):
    metadata, events = load_recording(tarball)
    assert metadata["employee_id"] == "emp-9"
    assert [(e["kind"], e["ts"][17:]) for e in events] == [
        ("ocr", "00.300Z"),
        ("ocr", "01.100200300Z"),
        ("mouse", "01.500Z"),
        ("mouse", "03.000Z"),
    ]
    assert events[0]["data"]["filename"] == "early.jpg"


def test_one_tick_per_second_including_empty_ones(tarball):
    _, events = load_recording(tarball)
    assert [[e["kind"] for e in tick] for tick in iter_ticks(events)] == [
        ["ocr"],
        ["ocr", "mouse"],
        [],
        ["mouse"],
    ]


def test_no_events_no_ticks():
    assert list(iter_ticks([])) == []


def test_missing_metadata_is_an_error(tmp_path):
    path = make_tarball(tmp_path / "x.tar.gz", {"s/events/mouse.jsonl": ""})
    with pytest.raises(ValueError, match="metadata"):
        load_recording(path)


def test_unreadable_event_line_is_an_error(tmp_path):
    files = {"s/metadata.json": METADATA, "s/events/mouse.jsonl": "not json\n"}
    with pytest.raises(ValueError):
        load_recording(make_tarball(tmp_path / "x.tar.gz", files))
