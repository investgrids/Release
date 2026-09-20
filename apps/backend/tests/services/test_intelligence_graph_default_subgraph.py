"""
app/services/intelligence_graph_service.py::get_default_subgraph (2026-09-20)
-- real production egress finding: the /graph page fetched the ENTIRE
intelligence graph (8.34MB) client-side purely to pick a "center" node,
then discarded it in ~97% of real cases in favor of a 232KB bounded
subgraph. This computes the same center choice server-side against the
already-cached full graph and returns only the bounded result.

Covers: deterministic center selection (including tie-breaking, which
the prior frontend-side Array.sort had none of), the node/edge/byte
ceiling enforced DURING traversal (not just checked after), the 2-hop
-> 1-hop fallback, and connectivity of any truncated result.
"""
from __future__ import annotations

import json

import pytest

import app.services.intelligence_graph_service as graph_service
from app.services.intelligence_graph_service import get_default_subgraph


def _node(id_, node_type="company", **kw):
    return {"id": id_, "node_type": node_type, "label": id_, "ticker": None, "description": None, "extra": {}, "auto_added": False, **kw}


def _edge(id_, source, target, edge_type="influences", **kw):
    return {"id": id_, "source": source, "target": target, "edge_type": edge_type, "weight": 0.5, "confidence": 0.5, "lag_days": 0, "description": None, "source_event": None, "auto_added": False, **kw}


def _star_graph(n_leaves: int, center_type: str = "company", leaf_type: str = "company"):
    """One center node directly connected to n_leaves distinct leaves --
    exercises the ceiling/truncation path deterministically."""
    center = _node("center", center_type)
    leaves = [_node(f"leaf{i:04d}", leaf_type) for i in range(n_leaves)]
    edges = [_edge(f"e{i:04d}", "center", f"leaf{i:04d}") for i in range(n_leaves)]
    return {"nodes": [center] + leaves, "edges": edges}


def _fake_get_full_graph_factory(graph):
    async def _f():
        return graph
    return _f


@pytest.mark.asyncio
async def test_picks_highest_ranked_highest_degree_node_as_center(monkeypatch):
    graph = {
        "nodes": [_node("event:e1", "event"), _node("company:c1", "company"), _node("company:c2", "company"), _node("company:c3", "company")],
        "edges": [
            _edge("e1", "event:e1", "company:c1"), _edge("e2", "event:e1", "company:c2"),
            _edge("e3", "company:c1", "company:c2"), _edge("e4", "company:c1", "company:c3"),
        ],
    }
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph()

    # event:e1 has degree 2 and the highest TYPE_RANK (4) -- 4*12+2=50,
    # beats company:c1's degree-3-but-rank-0 score of 3.
    assert result["center_id"] == "event:e1"


@pytest.mark.asyncio
async def test_center_selection_tie_break_is_deterministic_by_node_id(monkeypatch):
    # Two "company" nodes (rank 0) with identical degree 1 -- a real tie
    # on (type_rank*12 + degree). Must always resolve to the lexically
    # smaller id, not whatever order the graph happened to list them in.
    graph = {
        "nodes": [_node("company:zzz"), _node("company:aaa"), _node("company:mid")],
        "edges": [_edge("e1", "company:zzz", "company:mid"), _edge("e2", "company:aaa", "company:mid")],
    }
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph()
    # company:mid has degree 2 (highest), so it should always win regardless
    # of tie-break -- confirms real scoring picks it, not an accidental tie.
    assert result["center_id"] == "company:mid"

    # Now force a genuine tie: zzz and aaa both directly connected only to
    # each other (each degree 1, both rank 0) -- pool requires degree>=2,
    # so neither qualifies for the pool and the full candidate set (all 3
    # nodes) is used; mid still wins on degree. To truly exercise a tie,
    # build a graph where the top two candidates are exactly equal.
    tie_graph = {
        "nodes": [_node("company:zzz"), _node("company:aaa")],
        "edges": [_edge("e1", "company:zzz", "company:aaa")],
    }
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(tie_graph))
    result2 = await get_default_subgraph()
    # Both have degree 1, identical rank 0 -- exact tie. Deterministic
    # tiebreak must pick the lexically smaller id every time.
    assert result2["center_id"] == "company:aaa"
    # Re-run to prove it's not incidentally stable -- must be the same every time.
    for _ in range(5):
        r = await get_default_subgraph()
        assert r["center_id"] == "company:aaa"


@pytest.mark.asyncio
async def test_result_stays_within_node_and_edge_ceiling_for_an_oversized_hub(monkeypatch):
    graph = _star_graph(n_leaves=2000)  # far beyond _DEFAULT_MAX_NODES/_EDGES
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph()

    assert len(result["nodes"]) <= graph_service._DEFAULT_MAX_NODES
    assert len(result["edges"]) <= graph_service._DEFAULT_MAX_EDGES
    assert len(json.dumps(result)) <= graph_service._DEFAULT_MAX_BYTES


@pytest.mark.asyncio
async def test_truncated_result_is_always_connected_to_center(monkeypatch):
    graph = _star_graph(n_leaves=2000)
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph()

    node_ids = {n["id"] for n in result["nodes"]}
    assert result["center_id"] in node_ids
    for e in result["edges"]:
        assert e["source"] in node_ids and e["target"] in node_ids
    # every non-center node must have a direct edge to the center in this
    # star topology -- proves the truncation didn't strand a node whose
    # only connecting edge got dropped.
    connected_to_center = {e["target"] for e in result["edges"] if e["source"] == result["center_id"]} | \
                           {e["source"] for e in result["edges"] if e["target"] == result["center_id"]}
    assert connected_to_center == (node_ids - {result["center_id"]})


@pytest.mark.asyncio
async def test_truncation_is_deterministic_across_repeated_calls(monkeypatch):
    graph = _star_graph(n_leaves=2000)
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    r1 = await get_default_subgraph()
    r2 = await get_default_subgraph()
    assert [n["id"] for n in r1["nodes"]] == [n["id"] for n in r2["nodes"]]
    assert [e["id"] for e in r1["edges"]] == [e["id"] for e in r2["edges"]]


@pytest.mark.asyncio
async def test_small_graph_returns_everything_reachable_no_unnecessary_truncation(monkeypatch):
    graph = {
        "nodes": [_node("company:a"), _node("company:b"), _node("company:c")],
        "edges": [_edge("e1", "company:a", "company:b"), _edge("e2", "company:b", "company:c")],
    }
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph()

    assert len(result["nodes"]) == 3
    assert len(result["edges"]) == 2


@pytest.mark.asyncio
async def test_empty_graph_returns_empty_result_without_error(monkeypatch):
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory({"nodes": [], "edges": []}))

    result = await get_default_subgraph()

    assert result == {"nodes": [], "edges": [], "center_id": None}


@pytest.mark.asyncio
async def test_two_hop_falls_back_to_complete_one_hop_when_two_hop_exceeds_ceiling(monkeypatch):
    # Center -> 50 first-hop neighbors, each with 50 of their OWN second-hop
    # neighbors (2500 total second-hop nodes) -- 1-hop alone (51 nodes)
    # comfortably fits the ceiling, but the full 2-hop expansion (2551
    # nodes) does not. Must return the complete, untruncated 1-hop view
    # rather than an arbitrarily-cut-off partial 2-hop one.
    #
    # "center" is typed "event" (TYPE_RANK 4) specifically so it always
    # wins center-selection over a first-hop node -- a first-hop node's
    # own degree (1 back-edge + 50 to its children = 51) would otherwise
    # legitimately outscore center's degree-50 "company" (rank 0), which
    # is real, correct behavior of _pick_default_center, just not what
    # this particular test needs to exercise.
    nodes = [_node("center", "event")]
    edges = []
    for i in range(50):
        first = f"first{i:03d}"
        nodes.append(_node(first))
        edges.append(_edge(f"c-{i}", "center", first))
        for j in range(50):
            second = f"second{i:03d}-{j:03d}"
            nodes.append(_node(second))
            edges.append(_edge(f"{i}-{j}", first, second))
    graph = {"nodes": nodes, "edges": edges}
    monkeypatch.setattr(graph_service, "get_full_graph", _fake_get_full_graph_factory(graph))

    result = await get_default_subgraph(max_hops=2)

    assert len(result["nodes"]) == 51  # center + 50 first-hop, complete and untruncated
    assert len(result["edges"]) == 50
