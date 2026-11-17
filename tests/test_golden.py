"""Replay the real recordings through the real rules.

The expected popups were established by inspecting the recordings by hand
(see README); this test pins them so that a
change in matching or ordering semantics cannot go unnoticed.
"""

import pytest
from helpers import EXPECTED_POPUPS, ROOT

from agent.engine import Engine
from agent.rules import load_rules
from agent.screen import Screen
from streamer.recording import iter_ticks, load_recording


@pytest.mark.parametrize("employee", sorted(EXPECTED_POPUPS))
def test_recording_produces_the_expected_popups(employee):
    archive = ROOT / "data" / f"{employee}.tar.gz"
    if not archive.exists():
        pytest.skip(f"{archive} is not available")
    metadata, events = load_recording(str(archive))
    assert metadata["employee_id"] == employee

    displays = {d["id"]: tuple(d["bounds"]) for d in metadata["machine"]["displays"]}
    engine = Engine(load_rules(str(ROOT / "rules.json")), employee, Screen(displays))
    popups = [
        popup
        for tick in iter_ticks(events)
        for event in tick
        for popup in engine.feed(event["kind"], event["ts"], event["data"])
    ]

    assert [(p.rule, p.ts[:23]) for p in popups] == EXPECTED_POPUPS[employee]
    assert all(p.employee == employee for p in popups)
