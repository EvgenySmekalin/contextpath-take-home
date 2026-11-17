import pytest
from fastapi.testclient import TestClient

from server.main import create_app
from server.store import PopupStore


def popup(employee="emp-1", rule="r1", ts="2026-03-10T10:00:00.500Z", body="b"):
    return {"employee": employee, "rule": rule, "ts": ts, "title": "t", "body": body}


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(PopupStore(str(tmp_path / "popups.db"))))


def test_audit_is_empty_before_anything_arrives(client):
    assert client.get("/audit").json() == []


def test_audit_returns_exactly_the_five_fields(client):
    client.post("/popups", json=popup())
    assert client.get("/audit").json() == [popup()]


def test_filters_are_optional_and_combine(client):
    for employee, rule in [("emp-1", "r1"), ("emp-1", "r2"), ("emp-2", "r1")]:
        client.post("/popups", json=popup(employee, rule))

    def pairs(query=""):
        return sorted((p["employee"], p["rule"]) for p in client.get(f"/audit{query}").json())

    assert len(pairs()) == 3
    assert pairs("?employee=emp-1") == [("emp-1", "r1"), ("emp-1", "r2")]
    assert pairs("?rule=r1") == [("emp-1", "r1"), ("emp-2", "r1")]
    assert pairs("?employee=emp-2&rule=r1") == [("emp-2", "r1")]
    assert pairs("?employee=nobody") == []


def test_sorted_by_event_time_not_by_arrival_or_string_order(client):
    late, early = "2026-03-10T10:00:05.9Z", "2026-03-10T10:00:05.123456789Z"
    client.post("/popups", json=popup(ts=late))
    client.post("/popups", json=popup(ts=early))
    assert [p["ts"] for p in client.get("/audit").json()] == [early, late]


def test_redelivery_is_stored_once(client):
    client.post("/popups", json=popup())
    client.post("/popups", json=popup())
    assert len(client.get("/audit").json()) == 1


def test_same_moment_different_content_are_different_popups(client):
    for different in (popup(body="a"), popup(body="b"), popup(rule="r2")):
        client.post("/popups", json=different)
    assert len(client.get("/audit").json()) == 3


@pytest.mark.parametrize("bad", [{"employee": "emp-1"}, popup(ts="yesterday")])
def test_invalid_popup_is_rejected(client, bad):
    assert client.post("/popups", json=bad).status_code == 422
    assert client.get("/audit").json() == []


def test_popups_survive_a_restart(tmp_path):
    path = str(tmp_path / "popups.db")
    TestClient(create_app(PopupStore(path))).post("/popups", json=popup())
    assert TestClient(create_app(PopupStore(path))).get("/audit").json() == [popup()]


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
