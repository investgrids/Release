"""
Translate real, source-attributed industry labels (app/data/
company_industry_sources.json, collected by
scripts/backfill_company_industries.py) into the site's own sector names
for directory companies that NSE's EQ master file gives no sector.

Every mapping follows an existing precedent in the hand-curated
_NSE_UNIVERSE (e.g. CONCOR/DELHIVERY/ports -> Infrastructure, IGL/MGL ->
Energy, CHAMBLFERT/UPL -> Chemicals, DIXON/KAYNES -> Technology,
TRENT/INDHOTEL -> Consumer), not a fresh judgment. A label with no clear
precedent or that spans several site sectors (e.g. NSE "Services",
"Utilities", Yahoo "Building Materials", "Packaging & Containers") maps to
None — the company keeps an honest blank sector rather than a guess.

Display only: MarketRipple Score peer universes are derived from the
static _NSE_UNIVERSE (sector_universe.sector_peer_universe), so filling a
sector here never changes which companies are scored or ranked together.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_SOURCES_PATH = Path(__file__).resolve().parents[2] / "data" / "company_industry_sources.json"

# NSE index-constituent "Industry" (the exchange's own macro classification).
_NSE_INDUSTRY: dict[str, str | None] = {
    "Automobile and Auto Components": "Automotive",
    "Capital Goods": "Infrastructure",          # L&T, SIEMENS, CUMMINSIND precedent
    "Chemicals": "Chemicals",
    "Construction": "Infrastructure",
    "Consumer Durables": "Consumer",
    "Consumer Services": "Consumer",            # INDHOTEL, JUBLFOOD, TRENT, DMART precedent
    "Fast Moving Consumer Goods": "FMCG",
    "Financial Services": "Finance",            # can't distinguish banks here; "Finance" is broad but true
    "Healthcare": "Healthcare",
    "Information Technology": "Technology",
    "Media Entertainment & Publication": "Media",
    "Metals & Mining": "Metals",
    "Oil Gas & Consumable Fuels": "Energy",
    "Power": "Power",
    "Realty": "Real Estate",
    "Telecommunication": "Telecom",
    "Textiles": "Textiles",
    # Deliberately unmapped (span several site sectors / no precedent):
    "Construction Materials": None, "Diversified": None, "Forest Materials": None,
    "Services": None, "Utilities": None,
}

# Yahoo Finance "industry" (granular) -> site sector.
_YAHOO_INDUSTRY: dict[str, str | None] = {
    # Materials
    "Agricultural Inputs": "Chemicals",         # CHAMBLFERT/COROMANDEL precedent
    "Chemicals": "Chemicals", "Specialty Chemicals": "Chemicals",
    "Aluminum": "Metals", "Steel": "Metals", "Copper": "Metals",
    "Other Industrial Metals & Mining": "Metals", "Other Precious Metals & Mining": "Metals",
    "Coking Coal": "Energy", "Thermal Coal": "Energy",   # COALINDIA precedent
    # Energy
    "Oil & Gas Drilling": "Energy", "Oil & Gas E&P": "Energy", "Oil & Gas Integrated": "Energy",
    "Oil & Gas Equipment & Services": "Energy", "Oil & Gas Midstream": "Energy",
    "Oil & Gas Refining & Marketing": "Energy", "Utilities - Regulated Gas": "Energy",  # IGL/MGL
    # Power
    "Utilities - Regulated Electric": "Power", "Utilities - Independent Power Producers": "Power",
    "Utilities - Renewable": "Power", "Utilities - Diversified": "Power",
    # Financials
    "Banks - Regional": "Banking", "Banks - Diversified": "Banking",
    "Asset Management": "Finance", "Capital Markets": "Finance", "Credit Services": "Finance",
    "Mortgage Finance": "Finance", "Financial Conglomerates": "Finance",
    "Financial Data & Stock Exchanges": "Finance",
    "Insurance - Life": "Finance", "Insurance - Diversified": "Finance",   # SBILIFE precedent
    "Insurance - Property & Casualty": "Finance", "Insurance - Specialty": "Finance",
    "Insurance Brokers": "Finance",
    # Healthcare
    "Biotechnology": "Pharmaceuticals", "Drug Manufacturers - General": "Pharmaceuticals",
    "Drug Manufacturers - Specialty & Generic": "Pharmaceuticals",
    "Medical Care Facilities": "Healthcare", "Medical Devices": "Healthcare",
    "Medical Instruments & Supplies": "Healthcare", "Diagnostics & Research": "Healthcare",
    "Health Information Services": "Healthcare", "Healthcare Plans": "Healthcare",
    "Pharmaceutical Retailers": "Healthcare", "Medical Distribution": "Healthcare",
    # Industrials (site convention: capital goods, engineering, logistics -> Infrastructure)
    "Aerospace & Defense": "Defence",
    "Building Products & Equipment": "Infrastructure",   # ASTRAL precedent
    "Electrical Equipment & Parts": "Infrastructure",    # POLYCAB precedent
    "Engineering & Construction": "Infrastructure",
    "Farm & Heavy Construction Machinery": "Infrastructure",
    "Infrastructure Operations": "Infrastructure",
    "Integrated Freight & Logistics": "Infrastructure",  # CONCOR/DELHIVERY precedent
    "Marine Shipping": "Infrastructure",                  # GESHIP precedent
    "Metal Fabrication": "Infrastructure",
    "Specialty Industrial Machinery": "Infrastructure",
    "Tools & Accessories": "Infrastructure",
    "Railroads": "Infrastructure", "Trucking": "Infrastructure",
    "Airlines": "Aviation", "Airports & Air Services": "Infrastructure",
    # Consumer
    "Auto Manufacturers": "Automotive", "Auto Parts": "Automotive",
    "Auto & Truck Dealerships": "Automotive", "Recreational Vehicles": "Automotive",
    "Apparel Manufacturing": "Textiles", "Textile Manufacturing": "Textiles",
    "Apparel Retail": "Consumer",                         # TRENT precedent
    "Footwear & Accessories": "Consumer",                 # BATAINDIA precedent
    "Furnishings, Fixtures & Appliances": "Consumer",
    "Luxury Goods": "Consumer", "Lodging": "Consumer", "Restaurants": "Consumer",
    "Travel Services": "Consumer", "Leisure": "Consumer", "Resorts & Casinos": "Consumer",
    "Home Improvement Retail": "Consumer", "Department Stores": "Consumer",
    "Specialty Retail": "Consumer", "Internet Retail": "Consumer",
    "Grocery Stores": "Consumer", "Personal Services": "Consumer",
    "Beverages - Non-Alcoholic": "FMCG", "Beverages - Wineries & Distilleries": "FMCG",
    "Beverages - Brewers": "FMCG", "Confectioners": "FMCG", "Farm Products": "FMCG",
    "Household & Personal Products": "FMCG", "Packaged Foods": "FMCG", "Tobacco": "FMCG",
    # Communication / Technology
    "Broadcasting": "Media", "Entertainment": "Media", "Publishing": "Media",
    "Advertising Agencies": "Media",
    "Telecom Services": "Telecom",
    "Internet Content & Information": "Technology",       # NAUKRI precedent
    "Information Technology Services": "Technology",
    "Software - Application": "Technology", "Software - Infrastructure": "Technology",
    "Communication Equipment": "Technology", "Electronic Components": "Technology",  # DIXON/KAYNES
    "Scientific & Technical Instruments": "Technology",
    "Computer Hardware": "Technology", "Consumer Electronics": "Technology",
    "Semiconductors": "Technology", "Semiconductor Equipment & Materials": "Technology",
    "Electronics & Computer Distribution": "Technology",
    "Solar": "Infrastructure",                            # WAAREEENER/PREMIERENE precedent
    # Real estate
    "Real Estate - Development": "Real Estate", "Real Estate Services": "Real Estate",
    "Real Estate - Diversified": "Real Estate",
    "Food Distribution": "FMCG",
    # Deliberately unmapped — no site sector fits without guessing:
    "Packaging & Containers": None, "Conglomerates": None, "Specialty Business Services": None,
    "Education & Training Services": None, "Building Materials": None,  # cement AND tiles/pipes
    "Paper & Paper Products": None, "Lumber & Wood Production": None,
    "Rental & Leasing Services": None, "Waste Management": None, "Staffing & Employment Services": None,
    "Shell Companies": None, "Utilities - Regulated Water": None, "Industrial Distribution": None,
    "Business Equipment & Supplies": None, "Security & Protection Services": None,
    "Consulting Services": None, "Pollution & Treatment Controls": None,
}


@lru_cache(maxsize=1)
def _sources() -> dict[str, dict]:
    if not _SOURCES_PATH.exists():
        return {}
    return json.loads(_SOURCES_PATH.read_text(encoding="utf-8"))


def site_sector_for(symbol: str) -> str | None:
    """The site sector for a symbol, from its recorded source label, or
    None when there's no source label or it has no clear site-sector
    precedent."""
    entry = _sources().get(symbol)
    if not entry:
        return None
    label = entry.get("industry")
    if entry.get("source") == "NSE":
        return _NSE_INDUSTRY.get(label)
    return _YAHOO_INDUSTRY.get(label)


def source_industry_for(symbol: str) -> str | None:
    """The raw industry label as the source published it (shown as-is)."""
    entry = _sources().get(symbol)
    return entry.get("industry") if entry else None
