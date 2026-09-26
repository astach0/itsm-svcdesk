# ai-generated: 100% - generated as Lab 2 Stretch 3 coverage for the svcdesk API
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.environ.get("BASE_URL", "http://svcdesk:8080")
FIXTURE = Path("/fixtures/events-practice.jsonl")
EXPECTED = Path("/fixtures/metrics-practice.json")


def request_json(method, path, payload=None, headers=None):
    data = None
    hdrs = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        hdrs["Content-Type"] = "application/json"
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return exc.code, parsed


def load_fixture():
    events = [json.loads(line) for line in FIXTURE.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    return events, expected


def test_01_health():
    status, body = request_json("GET", "/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["service"] == "svcdesk"


def test_02_unknown_route():
    status, body = request_json("GET", "/definitely-not-a-real-route")
    assert status == 404
    assert isinstance(body, dict)
    assert "error" in body


def test_03_dora_empty_log():
    payload = {
        "window": {
            "from": "2026-09-01T00:00:00Z",
            "to": "2026-09-30T00:00:00Z",
        },
        "events": [],
    }
    status, body = request_json("POST", "/dora/metrics", payload)
    assert status == 200
    assert body["window"] == payload["window"]
    for key in (
        "deployment_frequency_per_day",
        "change_lead_time_seconds_p50",
        "failed_deployment_recovery_time_seconds_p50",
        "change_fail_rate",
        "deployment_rework_rate",
        "counts",
        "anomalies",
        "ground_truth",
    ):
        assert key in body


def test_04_dora_missing_window_rejected():
    status, body = request_json("POST", "/dora/metrics", {"events": []})
    assert status in (400, 422)
    assert "error" in body


def test_05_dora_non_array_events_rejected():
    payload = {
        "window": {
            "from": "2026-09-01T00:00:00Z",
            "to": "2026-09-30T00:00:00Z",
        },
        "events": {},
    }
    status, body = request_json("POST", "/dora/metrics", payload)
    assert status in (400, 422)
    assert "error" in body


def test_06_practice_fixture_matches_published_metrics():
    events, expected = load_fixture()
    payload = {"window": expected["window"], "events": events}
    status, body = request_json("POST", "/dora/metrics", payload)
    assert status == 200
    assert body == expected


def test_07_duplicate_events_are_ignored():
    events, _ = load_fixture()
    window = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-30T00:00:00Z"}
    s1, b1 = request_json("POST", "/dora/metrics", {"window": window, "events": events})
    s2, b2 = request_json("POST", "/dora/metrics", {"window": window, "events": events + events[:10]})
    assert s1 == 200 and s2 == 200
    assert b1 == b2


def test_08_event_order_does_not_change_result():
    events, _ = load_fixture()
    window = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-30T00:00:00Z"}
    s1, b1 = request_json("POST", "/dora/metrics", {"window": window, "events": events})
    s2, b2 = request_json("POST", "/dora/metrics", {"window": window, "events": list(reversed(events))})
    assert s1 == 200 and s2 == 200
    assert b1 == b2


def test_09_create_ticket():
    payload = {
        "title": "Stretch 3 create test",
        "reporter": {"name": "Stretch Tester", "email": "tests@example.invalid", "vip": False},
        "impact": 2,
        "urgency": 2,
    }
    status, body = request_json(
        "POST",
        "/tickets",
        payload,
        {"X-Test-Clock": "2026-09-26T10:00:00Z"},
    )
    assert status == 201
    assert body["state"] == "new"
    assert body["priority"] == "P3"
    assert body["created_at"] == "2026-09-26T10:00:00Z"


def test_10_ticket_lifecycle():
    payload = {
        "title": "Stretch 3 lifecycle test",
        "reporter": {"name": "Lifecycle Tester"},
        "impact": 1,
        "urgency": 1,
    }
    status, ticket = request_json(
        "POST",
        "/tickets",
        payload,
        {"X-Test-Clock": "2026-09-26T10:00:00Z"},
    )
    assert status == 201
    ticket_id = ticket["id"]

    status, _ = request_json("POST", f"/tickets/{ticket_id}/ack", None,
                             {"X-Test-Clock": "2026-09-26T10:05:00Z"})
    assert status == 200
    status, _ = request_json("POST", f"/tickets/{ticket_id}/start", None,
                             {"X-Test-Clock": "2026-09-26T10:06:00Z"})
    assert status == 200
    status, resolved = request_json("POST", f"/tickets/{ticket_id}/resolve", None,
                                    {"X-Test-Clock": "2026-09-26T11:00:00Z"})
    assert status == 200
    assert resolved["state"] == "resolved"


def test_11_invalid_ticket_transition_is_rejected():
    payload = {
        "title": "Stretch 3 invalid transition",
        "reporter": {"name": "Transition Tester"},
        "impact": 2,
        "urgency": 2,
    }
    status, ticket = request_json(
        "POST",
        "/tickets",
        payload,
        {"X-Test-Clock": "2026-09-26T10:30:00Z"},
    )
    assert status == 201
    status, body = request_json(
        "POST",
        f"/tickets/{ticket['id']}/close",
        None,
        {"X-Test-Clock": "2026-09-26T10:31:00Z"},
    )
    assert status == 409
    assert body["error"]["code"] == "invalid_transition"


def test_12_ticket_events_endpoint():
    payload = {
        "title": "Stretch 3 event stream",
        "reporter": {"name": "Event Tester"},
        "impact": 1,
        "urgency": 1,
    }
    status, ticket = request_json(
        "POST",
        "/tickets",
        payload,
        {"X-Test-Clock": "2026-09-26T12:00:00Z"},
    )
    assert status == 201

    status, events = request_json("GET", "/dora/ticket-events")
    assert status == 200
    assert isinstance(events, list)
    assert any(
        e["ticket_id"] == ticket["id"] and e["phase"] == "created"
        for e in events
    )
