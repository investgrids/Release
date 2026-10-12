"""A graph context shaped like the production knowledge graph's macro edges (read on 2026-10-12): weights, confidences, lags and rationales as stored.
Used by the Daily Brief tests so exposure is always read from graph edges, never from a table in the code under test."""
from __future__ import annotations

from app.services.daily_brief_graph import Edge, GraphContext


def _e(sector_id: str, sector: str, edge_type: str, weight: float, confidence: float, lag: int, why: str) -> Edge:
    return Edge(sector_id, sector, edge_type, weight, confidence, lag, why)


def fake_graph() -> GraphContext:
    return GraphContext(
        edges={
            "commodity:crude-oil": [
                _e("sector:airlines", "Airlines", "hurts", 0.9, 0.95, 0, "Jet fuel = 35-45% of airline operating costs; direct pass-through"),
                _e("sector:oil-gas", "Oil & Gas", "benefits", 0.85, 0.92, 0, "Upstream producers realise higher prices"),
                _e("sector:paint", "Paint", "hurts", 0.8, 0.9, 14, "TiO2 and solvents are crude derivatives"),
                _e("sector:chemical", "Chemical", "hurts", 0.75, 0.88, 7, "Petrochemical feedstocks = crude derivatives"),
                _e("sector:cement", "Cement", "hurts", 0.55, 0.82, 7, "Pet coke is key cement kiln fuel"),
                _e("sector:fmcg", "FMCG", "hurts", 0.5, 0.78, 14, "Packaging and logistics costs track crude"),
                _e("sector:auto", "Auto", "hurts", 0.45, 0.78, 30, "Higher running costs dampen demand"),
            ],
            "currency:usd-inr": [
                _e("sector:it", "IT", "benefits", 0.85, 0.95, 0, "IT earns USD; INR depreciation inflates INR revenues"),
                _e("sector:pharma", "Pharma", "benefits", 0.75, 0.9, 7, "Generic pharma exports USD"),
                _e("sector:airlines", "Airlines", "hurts", 0.7, 0.88, 0, "Aircraft leases and fuel costs rise in INR terms"),
                _e("sector:textiles", "Textiles", "benefits", 0.65, 0.85, 7, "Exports become price-competitive on weak INR"),
                _e("sector:auto", "Auto", "hurts", 0.55, 0.8, 14, "Auto imports components priced in USD"),
                _e("sector:chemical", "Chemical", "hurts", 0.5, 0.75, 7, "Imported inputs"),
                _e("sector:nbfc", "NBFC", "hurts", 0.4, 0.7, 0, "Foreign borrowing costs"),
            ],
            "policy:rbi-rate-hike": [
                _e("sector:nbfc", "NBFC", "hurts", 0.9, 0.95, 0, "NBFCs borrow at market rates; hikes compress NIMs"),
                _e("sector:real-estate", "Real Estate", "hurts", 0.85, 0.92, 30, "Higher home loan rates reduce affordability"),
                _e("sector:auto", "Auto", "hurts", 0.7, 0.88, 30, "Higher auto loan EMIs depress purchases"),
                _e("sector:infrastructure", "Infrastructure", "hurts", 0.65, 0.82, 30, "Higher project financing costs"),
            ],
            "policy:rbi-rate-cut": [
                _e("sector:real-estate", "Real Estate", "benefits", 0.85, 0.92, 30, "Lower home loan rates raise affordability"),
                _e("sector:nbfc", "NBFC", "benefits", 0.8, 0.9, 0, "Cheaper funding"),
                _e("sector:auto", "Auto", "benefits", 0.75, 0.88, 30, "Lower EMIs"),
                _e("sector:infrastructure", "Infrastructure", "benefits", 0.7, 0.82, 30, "Lower financing costs"),
            ],
        },
        node_labels={"commodity:crude-oil": "Crude Oil", "currency:usd-inr": "USD/INR", "policy:rbi-rate-hike": "RBI Rate Hike", "policy:rbi-rate-cut": "RBI Rate Cut"},
        sector_vocabulary=["Airlines", "Auto", "Banking", "Cement", "Chemical", "Financial Services", "FMCG", "Infrastructure", "IT", "NBFC", "Oil & Gas",
                           "Paint", "Pharma", "Real Estate", "Telecom", "Textiles"],
    )
