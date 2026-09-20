"""
app/api/graph.py::/full -- admin-key gate (2026-09-20, step 4/4 of the
egress remediation). A full grep audit + production HTTP logs confirmed
no real public consumer remained once the two frontend callers moved to
the bounded /default-subgraph and /subgraph/{id} endpoints -- this locks
the route down rather than leaving an unused, expensive public endpoint
reachable.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)
HEADERS = {"X-Admin-Key": settings.admin_api_key} if getattr(settings, "admin_api_key", None) else {}


def test_full_graph_rejects_a_request_with_no_admin_key():
    resp = client.get("/api/graph/full")
    assert resp.status_code in (401, 403)


def test_full_graph_rejects_an_incorrect_admin_key():
    resp = client.get("/api/graph/full", headers={"X-Admin-Key": "definitely-wrong"})
    assert resp.status_code in (401, 403)


def test_full_graph_succeeds_with_the_correct_admin_key():
    resp = client.get("/api/graph/full", headers=HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert "nodes" in body and "edges" in body


def test_default_subgraph_remains_public_no_admin_key_required():
    # The bounded replacement endpoint must stay reachable by the
    # frontend without any credential -- only /full itself is gated.
    resp = client.get("/api/graph/default-subgraph")
    assert resp.status_code == 200


def test_subgraph_endpoint_remains_public_no_admin_key_required():
    resp = client.get("/api/graph/subgraph/some-node-id")
    assert resp.status_code == 200
