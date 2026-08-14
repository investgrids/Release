"""
Regression suite — app.services.ripple_service's global-event->India
transmission template (Phase 8, 2026-08 audit: the existing Ripple Engine's
fallback templates covered geopolitical/energy/monetary/fiscal/generic but
had no branch for a foreign-origin trigger — e.g. a Fed decision — modeling
the real USD/INR transmission mechanism into Indian markets).

Pure unit tests against the private template functions directly (no DB,
no network) — same white-box convention already used elsewhere in this
suite for private module-level helpers.
"""
from __future__ import annotations

from app.services import ripple_service


def test_detect_template_global_monetary_for_fed_keywords():
    assert ripple_service._detect_template("Fed rate decision looms", "FOMC meets this week") == "global_monetary"
    assert ripple_service._detect_template("Federal Reserve holds rates steady", "") == "global_monetary"
    assert ripple_service._detect_template("Fed Chair signals pause", "") == "global_monetary"


def test_detect_template_global_monetary_for_ecb_boj_pboc():
    assert ripple_service._detect_template("ECB rate decision due Thursday", "") == "global_monetary"
    assert ripple_service._detect_template("European Central Bank cuts rates", "") == "global_monetary"
    assert ripple_service._detect_template("Bank of Japan surprises markets", "") == "global_monetary"
    assert ripple_service._detect_template("China GDP data disappoints", "") == "global_monetary"
    assert ripple_service._detect_template("China PMI contracts further", "") == "global_monetary"


def test_detect_template_domestic_monetary_unaffected_by_global_branch():
    # A domestic RBI decision must still route to the existing "monetary"
    # template — the new global_monetary check must not accidentally
    # swallow domestic-policy headlines.
    assert ripple_service._detect_template("RBI cuts repo rate by 25 bps", "") == "monetary"
    assert ripple_service._detect_template("RBI holds interest rate steady", "monetary policy review") == "monetary"


def test_global_monetary_template_has_well_formed_structure():
    graph = ripple_service._global_monetary_template("Fed holds rates steady", 6.5)
    assert "nodes" in graph and "edges" in graph and "insights" in graph
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "event_center" in node_ids

    event_center = next(n for n in graph["nodes"] if n["id"] == "event_center")
    assert event_center["depth"] == 0

    # Every edge must reference real node ids — a dangling edge would be a
    # broken graph in the frontend's ripple visualization.
    for edge in graph["edges"]:
        assert edge["source"] in node_ids, f"edge source {edge['source']} has no matching node"
        assert edge["target"] in node_ids, f"edge target {edge['target']} has no matching node"

    # The actual India transmission mechanism the spec asked for must be
    # present as real nodes, not just claimed in prose.
    assert "inr_usd" in node_ids
    assert "it_exporters" in node_ids
    assert "oil_import_bill" in node_ids


def test_global_monetary_template_transmission_is_two_sided():
    # Confirms the specific example from the spec: IT/pharma exporters and
    # oil-import/import-heavy companies must move in OPPOSITE directions
    # from the same rupee move — never uniformly positive or negative.
    graph = ripple_service._global_monetary_template("Fed signals more hikes", 8.0)  # pos=True (hawkish)
    by_id = {n["id"]: n for n in graph["nodes"]}
    assert by_id["it_exporters"]["change_direction"] == "up"
    assert by_id["oil_import_bill"]["change_direction"] == "up"  # cost UP is bad, not a currency-tailwind win
    assert by_id["it_exporters"]["impact"] == "positive"
    assert by_id["oil_import_bill"]["impact"] == "negative"
    assert by_id["import_heavy"]["impact"] == "negative"


def test_global_monetary_template_direction_flips_with_impact_score():
    hawkish = ripple_service._global_monetary_template("Fed hikes rates", 8.0)
    dovish = ripple_service._global_monetary_template("Fed signals rate cuts ahead", 3.0)
    hawkish_it = next(n for n in hawkish["nodes"] if n["id"] == "it_exporters")
    dovish_it = next(n for n in dovish["nodes"] if n["id"] == "it_exporters")
    assert hawkish_it["impact"] == "positive"   # weaker rupee -> IT revenue tailwind
    assert dovish_it["impact"] == "negative"    # stronger rupee -> IT revenue headwind


def test_build_fallback_graph_routes_global_monetary_events_correctly():
    graph = ripple_service._build_fallback_graph(
        "Fed holds interest rates steady", "FOMC statement release", "macro", 6.0, [], [],
    )
    node_ids = {n["id"] for n in graph["nodes"]}
    # A domestic-monetary-template graph would have "repo_rate" instead —
    # confirms routing actually reached the new template, not a fallback
    # to the generic/domestic one.
    assert "repo_rate" not in node_ids
    assert "inr_usd" in node_ids
    assert "usd_index" in node_ids
