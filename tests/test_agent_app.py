import pytest
from fastapi.testclient import TestClient

from agent.main import create_app
from agent.rules import Rule

RULES = [
    Rule.model_validate(
        {
            "id": "forwarded",
            "when": {"click": "FW:*", "process": "olk.exe"},
            "popup": {"title": "Forwarded", "body": "{click}"},
        }
    )
]
SESSION = {"employee_id": "emp-1", "displays": [{"id": 0, "bounds": [0, 0, 1920, 1080]}]}

FOCUS = {
    "kind": "windows",
    "ts": "2026-03-10T10:00:01.100Z",
    "data": {"process_name": "olk.exe", "window_title": "Inbox"},
}
OCR = {
    "kind": "ocr",
    "ts": "2026-03-10T10:00:01.200Z",
    "data": {
        "filename": "a.jpg",
        "display_id": 0,
        "resolution": [1920, 1080],
        "ocr_text_blocks": [{"text": "FW: hello", "bounding_box": [100, 200, 300, 20]}],
    },
}
CLICK = {
    "kind": "mouse",
    "ts": "2026-03-10T10:00:01.300Z",
    "data": {
        "event": "click",
        "button": "left",
        "click_count": "single",
        "mouse_x": 150,
        "mouse_y": 210,
    },
}


@pytest.fixture
def delivered():
    return []


@pytest.fixture
def client(delivered):
    return TestClient(create_app(RULES, deliver=delivered.append))


def test_tick_before_session_is_refused(client):
    assert client.post("/ticks", json=[]).status_code == 409


def test_popup_is_delivered_with_the_time_of_the_click(client, delivered):
    client.post("/session", json=SESSION)
    assert client.post("/ticks", json=[FOCUS, OCR, CLICK]).json() == {"popups": 1}
    assert [(p.employee, p.rule, p.ts, p.body) for p in delivered] == [
        ("emp-1", "forwarded", CLICK["ts"], "FW: hello")
    ]


def test_state_carries_over_between_ticks(client, delivered):
    client.post("/session", json=SESSION)
    client.post("/ticks", json=[FOCUS, OCR])
    client.post("/ticks", json=[])
    client.post("/ticks", json=[{**CLICK, "ts": "2026-03-10T10:00:03.000Z"}])
    assert len(delivered) == 1


def test_failed_delivery_fails_the_tick():
    def unreachable(popup):
        raise RuntimeError("the server did not accept the popup")

    client = TestClient(create_app(RULES, deliver=unreachable), raise_server_exceptions=False)
    client.post("/session", json=SESSION)
    assert client.post("/ticks", json=[FOCUS, OCR, CLICK]).status_code == 500
