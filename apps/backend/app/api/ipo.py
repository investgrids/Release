"""
IPO Hub — PLACEHOLDER/MOCK data.

Every record in `_IPOS` below (prices, GMP, subscription numbers, dates,
"AI" ratings/summaries) is hand-written example data, not sourced from any
live IPO feed. There is no real NSE/BSE IPO integration wired up yet. Every
response is marked `is_mock: True` / `data_source: "placeholder"` so
frontend consumers can — and must — surface that honestly instead of
presenting it as live market data.

Replace with a real IPO data provider before treating this endpoint as
production-accurate.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()

_MOCK_DATE_FIELDS = ("openDate", "closeDate", "allotmentDate", "refundDate", "creditDate", "listingDate")


def _mark_mock(ipo: dict) -> dict:
    """Attach the is_mock flag and replace the stale hardcoded 2025 dates
    with an explicit placeholder label rather than letting them silently
    drift further out of date."""
    out = {**ipo, "is_mock": True}
    for field in _MOCK_DATE_FIELDS:
        if field in out:
            out[field] = "Example date — placeholder"
    return out

_IPOS = [
    {
        "id": "vikram-solar",
        "name": "Vikram Solar Ltd.",
        "sector": "Solar Solutions",
        "type": "Mainboard",
        "priceMin": 315, "priceMax": 332,
        "issueSize": "₹2,079 Cr", "freshIssue": "₹1,500 Cr", "offerForSale": "₹579 Cr",
        "lotSize": 45, "listingOn": "NSE, BSE",
        "openDate": "May 19, 2025", "closeDate": "May 21, 2025",
        "allotmentDate": "May 22, 2025", "refundDate": "May 23, 2025",
        "creditDate": "May 23, 2025", "listingDate": "May 26, 2025",
        "status": "Upcoming", "gmp": 48, "gmpPct": 14.46,
        "gmpTrend": [
            {"label": "May 12", "value": 30}, {"label": "May 13", "value": 33},
            {"label": "May 14", "value": 36}, {"label": "May 15", "value": 40},
            {"label": "May 16", "value": 42}, {"label": "May 17", "value": 45},
            {"label": "May 18", "value": 48},
        ],
        "description": "Vikram Solar Ltd. is one of India's leading solar PV module manufacturers with a strong presence in domestic and international markets. The company offers high efficiency solar modules and EPC solutions.",
        "founded": "2006", "headquarters": "Kolkata, India",
        "promoters": "Gyanesh Chaudhary", "website": "vikramsolar.com",
        "highlights": [
            "India's top 3 solar module manufacturers",
            "Capacity of 3.5 GW as of FY24",
            "Strong global presence in 30+ countries",
            "Long-term contracts with reputed clients",
            "Backward integrated manufacturing",
        ],
        "aiSummary": "Vikram Solar shows strong fundamentals with improving financials, high industry growth and strong order book.",
        "aiRating": "Bullish",
        "subscriptionRetail": None, "subscriptionHNI": None, "subscriptionQIB": None,
    },
    {
        "id": "ather-energy",
        "name": "Ather Energy Ltd.",
        "sector": "Electric Vehicles",
        "type": "Mainboard",
        "priceMin": 304, "priceMax": 321,
        "issueSize": "₹2,981 Cr", "freshIssue": "₹2,626 Cr", "offerForSale": "₹355 Cr",
        "lotSize": 46, "listingOn": "NSE, BSE",
        "openDate": "May 20, 2025", "closeDate": "May 22, 2025",
        "allotmentDate": "May 23, 2025", "refundDate": "May 24, 2025",
        "creditDate": "May 24, 2025", "listingDate": "May 27, 2025",
        "status": "Upcoming", "gmp": 35, "gmpPct": 10.90,
        "gmpTrend": [
            {"label": "May 12", "value": 20}, {"label": "May 13", "value": 22},
            {"label": "May 14", "value": 28}, {"label": "May 15", "value": 30},
            {"label": "May 16", "value": 32}, {"label": "May 17", "value": 34},
            {"label": "May 18", "value": 35},
        ],
        "description": "Ather Energy is India's leading electric two-wheeler company, known for its Ather 450 series. The company operates its own manufacturing facility in Hosur and has built a comprehensive charging infrastructure across India.",
        "founded": "2013", "headquarters": "Bengaluru, India",
        "promoters": "Tarun Mehta, Swapnil Jain",
        "website": "atherenergy.com",
        "highlights": [
            "Pioneer in premium EV segment in India",
            "40+ cities with Ather Grid fast-charging",
            "Strong R&D team with 500+ engineers",
            "Hero MotoCorp as strategic investor",
        ],
        "aiSummary": "Ather Energy is well-positioned in India's fast-growing EV market with differentiated tech platform and strong brand.",
        "aiRating": "Bullish",
        "subscriptionRetail": None, "subscriptionHNI": None, "subscriptionQIB": None,
    },
    {
        "id": "nextgen-cloud",
        "name": "NextGen Cloud Tech",
        "sector": "Cloud & IT Services",
        "type": "SME",
        "priceMin": 102, "priceMax": 108,
        "issueSize": "₹180 Cr", "freshIssue": "₹150 Cr", "offerForSale": "₹30 Cr",
        "lotSize": 1200, "listingOn": "NSE SME",
        "openDate": "May 21, 2025", "closeDate": "May 23, 2025",
        "allotmentDate": "May 26, 2025", "refundDate": "May 27, 2025",
        "creditDate": "May 27, 2025", "listingDate": "May 28, 2025",
        "status": "Upcoming", "gmp": 12, "gmpPct": 11.11,
        "gmpTrend": [
            {"label": "May 14", "value": 6}, {"label": "May 15", "value": 8},
            {"label": "May 16", "value": 9}, {"label": "May 17", "value": 10},
            {"label": "May 18", "value": 12},
        ],
        "description": "NextGen Cloud Technologies provides cloud infrastructure solutions, managed services and digital transformation for mid-market enterprises across India and Southeast Asia.",
        "founded": "2015", "headquarters": "Pune, India",
        "promoters": "Rajesh Kumar, Anita Sharma",
        "website": "nextgencloud.in",
        "highlights": [
            "200+ enterprise clients across 5 countries",
            "AWS and Azure certified partner",
            "35% revenue CAGR over last 3 years",
        ],
        "aiSummary": "NextGen Cloud offers exposure to India's growing cloud adoption theme. Small cap with above-average growth but moderate risk.",
        "aiRating": "Neutral",
        "subscriptionRetail": None, "subscriptionHNI": None, "subscriptionQIB": None,
    },
    {
        "id": "transrail-lighting",
        "name": "Transrail Lighting Ltd.",
        "sector": "Lighting Solutions",
        "type": "Mainboard",
        "priceMin": 410, "priceMax": 432,
        "issueSize": "₹838 Cr", "freshIssue": "₹400 Cr", "offerForSale": "₹438 Cr",
        "lotSize": 34, "listingOn": "NSE, BSE",
        "openDate": "May 22, 2025", "closeDate": "May 26, 2025",
        "allotmentDate": "May 27, 2025", "refundDate": "May 28, 2025",
        "creditDate": "May 28, 2025", "listingDate": "May 29, 2025",
        "status": "Upcoming", "gmp": 28, "gmpPct": 6.48,
        "gmpTrend": [
            {"label": "May 15", "value": 18}, {"label": "May 16", "value": 20},
            {"label": "May 17", "value": 23}, {"label": "May 18", "value": 28},
        ],
        "description": "Transrail Lighting is a leading manufacturer of transmission line towers, substation structures, solar modules and LED lighting for power infrastructure projects across India.",
        "founded": "1989", "headquarters": "Nagpur, India",
        "promoters": "S.K. Agarwal", "website": "transrail.in",
        "highlights": [
            "35+ years in power infrastructure",
            "Order book of ₹8,200 Cr as of Q3 FY25",
            "Pan-India presence with 12 manufacturing plants",
        ],
        "aiSummary": "Transrail benefits from India's ongoing power sector capex cycle. Established player with strong order book and government tailwinds.",
        "aiRating": "Bullish",
        "subscriptionRetail": None, "subscriptionHNI": None, "subscriptionQIB": None,
    },
    {
        "id": "le-travenues",
        "name": "Le Travenues Tech Ltd.",
        "sector": "Travel Tech",
        "type": "Mainboard",
        "priceMin": 136, "priceMax": 143,
        "issueSize": "₹1,048 Cr", "freshIssue": "₹750 Cr", "offerForSale": "₹298 Cr",
        "lotSize": 104, "listingOn": "NSE, BSE",
        "openDate": "May 15, 2025", "closeDate": "May 19, 2025",
        "allotmentDate": "May 20, 2025", "refundDate": "May 21, 2025",
        "creditDate": "May 21, 2025", "listingDate": "May 22, 2025",
        "status": "Ongoing", "gmp": 21, "gmpPct": 14.69,
        "gmpTrend": [
            {"label": "May 10", "value": 12}, {"label": "May 12", "value": 15},
            {"label": "May 14", "value": 18}, {"label": "May 15", "value": 19},
            {"label": "May 16", "value": 20}, {"label": "May 17", "value": 21},
            {"label": "May 18", "value": 21},
        ],
        "description": "Le Travenues Tech (ixigo) is India's leading travel super-app with over 100 million users. The platform serves price-sensitive Bharat travellers for train, bus, flight, and hotel bookings.",
        "founded": "2007", "headquarters": "Gurugram, India",
        "promoters": "Aloke Bajpai, Rajnish Kumar", "website": "ixigo.com",
        "highlights": [
            "100M+ registered users, 65M MAU",
            "Market leader in tier-2/3 cities",
            "First travel-tech company to achieve EBITDA profitability",
            "IRCTC authorized agent",
        ],
        "aiSummary": "ixigo is a profitable travel platform riding India's travel boom. Strong Bharat moat with attractive growth trajectory.",
        "aiRating": "Bullish",
        "subscriptionRetail": 2.34, "subscriptionHNI": 5.12, "subscriptionQIB": 1.87,
    },
    {
        "id": "quality-power",
        "name": "Quality Power Elec.",
        "sector": "Power Products",
        "type": "SME",
        "priceMin": 401, "priceMax": 425,
        "issueSize": "₹225 Cr", "freshIssue": "₹180 Cr", "offerForSale": "₹45 Cr",
        "lotSize": 35, "listingOn": "NSE SME",
        "openDate": "May 16, 2025", "closeDate": "May 20, 2025",
        "allotmentDate": "May 21, 2025", "refundDate": "May 22, 2025",
        "creditDate": "May 22, 2025", "listingDate": "May 23, 2025",
        "status": "Ongoing", "gmp": 18, "gmpPct": 4.24,
        "gmpTrend": [
            {"label": "May 13", "value": 10}, {"label": "May 15", "value": 13},
            {"label": "May 16", "value": 15}, {"label": "May 17", "value": 17},
            {"label": "May 18", "value": 18},
        ],
        "description": "Quality Power Electrical Equipments is a manufacturer of specialized electrical transformers and equipment for utilities, railways, and industrial segments.",
        "founded": "2002", "headquarters": "Vadodara, India",
        "promoters": "Mehul Patel", "website": "qualitypower.in",
        "highlights": [
            "Specialized in high-voltage transformers",
            "RDSO-approved vendor for Indian Railways",
            "Exports to 8 countries",
        ],
        "aiSummary": "Quality Power benefits from India's power sector capex but limited scale. Moderate conviction, better for risk-tolerant investors.",
        "aiRating": "Neutral",
        "subscriptionRetail": 1.82, "subscriptionHNI": 3.45, "subscriptionQIB": 0.98,
    },
    {
        "id": "inventurus-knowledge",
        "name": "Inventurus Knowledge",
        "sector": "Healthcare IT",
        "type": "Mainboard",
        "priceMin": 1265, "priceMax": 1329,
        "issueSize": "₹2,497 Cr", "freshIssue": "₹0 Cr", "offerForSale": "₹2,497 Cr",
        "lotSize": 11, "listingOn": "NSE, BSE",
        "openDate": "May 17, 2025", "closeDate": "May 21, 2025",
        "allotmentDate": "May 22, 2025", "refundDate": "May 23, 2025",
        "creditDate": "May 23, 2025", "listingDate": "May 24, 2025",
        "status": "Ongoing", "gmp": 150, "gmpPct": 11.29,
        "gmpTrend": [
            {"label": "May 12", "value": 80}, {"label": "May 13", "value": 95},
            {"label": "May 14", "value": 110}, {"label": "May 15", "value": 125},
            {"label": "May 16", "value": 135}, {"label": "May 17", "value": 145},
            {"label": "May 18", "value": 150},
        ],
        "description": "Inventurus Knowledge Solutions provides AI-powered clinical documentation and healthcare workflow automation solutions to physician groups across the US.",
        "founded": "2006", "headquarters": "Mumbai, India",
        "promoters": "Sachin Gupta", "website": "inventurus.com",
        "highlights": [
            "Serves 30,000+ physicians in the US",
            "AI-powered ambient scribe technology",
            "Revenue from USD-denominated long-term contracts",
            "100% OFS — no dilution, existing investors exiting",
        ],
        "aiSummary": "Inventurus is a niche healthcare IT play with US revenue streams and AI tailwinds. High valuations reflect premium growth expectations.",
        "aiRating": "Neutral",
        "subscriptionRetail": 4.56, "subscriptionHNI": 12.78, "subscriptionQIB": 8.34,
    },
    {
        "id": "emcure-pharma",
        "name": "Emcure Pharma Ltd.",
        "sector": "Pharmaceuticals",
        "type": "Mainboard",
        "priceMin": 960, "priceMax": 1008,
        "issueSize": "₹1,952 Cr", "freshIssue": "₹800 Cr", "offerForSale": "₹1,152 Cr",
        "lotSize": 14, "listingOn": "NSE, BSE",
        "openDate": "May 18, 2025", "closeDate": "May 22, 2025",
        "allotmentDate": "May 23, 2025", "refundDate": "May 24, 2025",
        "creditDate": "May 24, 2025", "listingDate": "May 27, 2025",
        "status": "Ongoing", "gmp": 82, "gmpPct": 8.13,
        "gmpTrend": [
            {"label": "May 13", "value": 45}, {"label": "May 14", "value": 55},
            {"label": "May 15", "value": 65}, {"label": "May 16", "value": 70},
            {"label": "May 17", "value": 78}, {"label": "May 18", "value": 82},
        ],
        "description": "Emcure Pharmaceuticals is one of India's largest pharmaceutical companies with a strong domestic and international presence, focusing on gynaecology, cardiology, HIV antivirals, and injectable segments.",
        "founded": "1981", "headquarters": "Pune, India",
        "promoters": "Satish Mehta", "website": "emcure.co.in",
        "highlights": [
            "Top-5 pharma company in Indian market",
            "Presence in 70+ countries",
            "Strong branded generics portfolio",
            "Strategic focus on complex injectables",
        ],
        "aiSummary": "Emcure is a proven pharma player with diversified revenue streams. Reasonable valuations and strong brand make this an attractive listing candidate.",
        "aiRating": "Bullish",
        "subscriptionRetail": 3.12, "subscriptionHNI": 8.90, "subscriptionQIB": 6.45,
    },
]

_SECTOR_TRENDS = [
    {"name": "Manufacturing", "count": 4, "pct": 28.6, "color": "#818cf8"},
    {"name": "Technology",    "count": 3, "pct": 21.4, "color": "#38bdf8"},
    {"name": "Energy",        "count": 2, "pct": 14.3, "color": "#fbbf24"},
    {"name": "Healthcare",    "count": 2, "pct": 14.3, "color": "#34d399"},
    {"name": "Consumer",      "count": 2, "pct": 14.3, "color": "#f97316"},
    {"name": "Others",        "count": 1, "pct": 7.1,  "color": "#94a3b8"},
]


@router.get("/")
async def list_ipos(status: str | None = None):
    ipos = _IPOS
    if status and status.lower() in ("upcoming", "ongoing", "listed"):
        ipos = [i for i in ipos if i["status"].lower() == status.lower()]
    upcoming = sum(1 for i in _IPOS if i["status"] == "Upcoming")
    ongoing  = sum(1 for i in _IPOS if i["status"] == "Ongoing")
    listed   = sum(1 for i in _IPOS if i["status"] == "Listed")
    return {
        "ipos":          [_mark_mock(i) for i in ipos],
        "stats":         {"upcoming": upcoming, "ongoing": ongoing, "listed": listed, "avg_listing_gain": 18.6},
        "sector_trends": _SECTOR_TRENDS,
        "sentiment":     {"score": 78, "label": "Bullish", "retail": "High", "hni": "High", "volatility": "Moderate", "overall": "Bullish"},
        "ai_insight":    "High IPO activity this quarter driven by manufacturing, tech & renewable energy sectors. Investor sentiment is strong.",
        "is_mock":       True,
        "data_source":   "placeholder",
    }


@router.get("/{ipo_id}")
async def get_ipo(ipo_id: str):
    ipo = next((i for i in _IPOS if i["id"] == ipo_id), None)
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO not found")
    return _mark_mock(ipo)
