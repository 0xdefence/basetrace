from fastapi.testclient import TestClient

from api.main import app
from api.routes import dashboard as dashboard_route
from api.routes import graph as graph_route
from api.routes import labels as labels_route
from api.routes import runbook as runbook_route


client = TestClient(app)


def test_dashboard_summary_contract(monkeypatch):
    monkeypatch.setattr(dashboard_route, "dashboard_summary", lambda hot_limit=5: {
        "compact": {"ingest_lag_blocks": 1, "alerts_24h": 2, "queue_new": 3, "queue_ack": 1, "queue_resolved": 0, "backlog_pressure": "low", "dead_letter_open": 0},
        "summary": {"metrics": {}, "queue": {}, "dead_letter": {}, "top_alert_types_24h": [], "top_alert_addresses_24h": [], "hot_alerts": []},
    })
    r = client.get("/dashboard/summary")
    assert r.status_code == 200
    data = r.json()
    assert "compact" in data and "summary" in data


def test_labels_taxonomy_contract():
    r = client.get("/labels/taxonomy")
    assert r.status_code == 200
    data = r.json()
    assert "labels" in data
    assert all(k in data["labels"] for k in ["deployer", "router", "bridge", "treasury", "exchange-facing"])


def test_graph_neighbors_contract(monkeypatch):
    monkeypatch.setattr(graph_route, "get_neighbors", lambda address, limit=25: {
        "nodes": [{"id": address}, {"id": "0xabc"}],
        "edges": [{"src": address, "dst": "0xabc", "tx_count": 2, "total_value_wei": "1"}],
    })
    r = client.get("/graph/neighbors/0x123?limit=10")
    assert r.status_code == 200
    data = r.json()
    assert set(["address", "depth", "limit", "nodes", "edges"]).issubset(data.keys())


def test_runbook_failures_contract(monkeypatch):
    monkeypatch.setattr(runbook_route, "failures_runbook", lambda limit=100: {"limit": limit, "summary": {"open": 1, "resolved": 0, "other": 0}, "failures": []})
    r = client.get("/runbook/failures")
    assert r.status_code == 200
    data = r.json()
    assert set(["limit", "summary", "failures"]).issubset(data.keys())
