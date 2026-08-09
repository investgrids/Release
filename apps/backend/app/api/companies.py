"""
Companies API — searchable, filterable, paginated directory of NSE companies.

GET /api/companies/        — paginated list with live prices for the current page
GET /api/companies/search  — instant metadata-only typeahead (no live prices)
GET /api/companies/sectors — distinct sector list for filter UI

Live prices are fetched via yfinance batch download for the current page only
(never for the full universe at once). Static metadata is resolved in-memory
so search and filter are always sub-millisecond.
"""
from __future__ import annotations

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter()

# ── Company Universe ──────────────────────────────────────────────────────────
# 512 NSE-listed companies with static metadata (2026-08-09 — 510 originally,
# minus 3 delisted/unresolvable symbols dropped, minus 2 accidental
# duplicates found and removed (ETERNAL/LTM each had a second, incomplete
# entry already sitting further down the list from an earlier partial
# rename that never removed the old row), plus 7 from the Tier 1 sectoral-
# index-verified expansion; see the "Tier 1 universe expansion" comment near
# the end of this list for sourcing detail). Previously said "~260" here,
# already stale by the time it said that — kept falling out of sync with the
# actual list below it every time an entry was added; nobody owns re-syncing
# a comment nobody's told to check.
# Cap categories:  large = approx Nifty 100 universe
#                  mid   = approx Nifty 150 midcap
#                  small = below that
# aliases: common abbreviations / alternative search terms

_NSE_UNIVERSE: list[dict] = [
    # ── Technology / IT ───────────────────────────────────────────────────────
    {"symbol":"TCS",        "name":"Tata Consultancy Services Ltd",  "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["tcs","tata consultancy"]},
    {"symbol":"INFY",       "name":"Infosys Ltd",                    "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["infosys"]},
    {"symbol":"WIPRO",      "name":"Wipro Ltd",                      "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["wipro"]},
    {"symbol":"HCLTECH",    "name":"HCL Technologies Ltd",           "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["hcl","hcltech"]},
    {"symbol":"TECHM",      "name":"Tech Mahindra Ltd",              "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["tech mahindra"]},
    {"symbol":"LTM",        "name":"LTIMindtree Ltd",                "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["ltimindtree","mindtree","ltim"]},
    {"symbol":"PERSISTENT", "name":"Persistent Systems Ltd",         "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["persistent"]},
    {"symbol":"MPHASIS",    "name":"Mphasis Ltd",                    "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["mphasis"]},
    {"symbol":"COFORGE",    "name":"Coforge Ltd",                    "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["coforge","niit tech"]},
    {"symbol":"KPITTECH",   "name":"KPIT Technologies Ltd",          "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["kpit"]},
    {"symbol":"LTTS",       "name":"L&T Technology Services Ltd",    "sector":"Technology",     "industry":"Engineering IT",        "cap":"mid",   "aliases":["l&t tech","ltts"]},
    {"symbol":"OFSS",       "name":"Oracle Financial Services Software","sector":"Technology",  "industry":"IT Software",           "cap":"large", "aliases":["oracle financial","ofss"]},
    {"symbol":"TATAELXSI",  "name":"Tata Elxsi Ltd",                 "sector":"Technology",     "industry":"Design Services",       "cap":"mid",   "aliases":["tata elxsi"]},
    {"symbol":"CYIENT",     "name":"Cyient Ltd",                     "sector":"Technology",     "industry":"Engineering IT",        "cap":"mid",   "aliases":["cyient"]},
    {"symbol":"NAUKRI",     "name":"Info Edge India Ltd",            "sector":"Technology",     "industry":"Internet Platform",     "cap":"large", "aliases":["info edge","naukri","jeevansathi"]},
    {"symbol":"INDIAMART",  "name":"IndiaMart InterMesh Ltd",        "sector":"Technology",     "industry":"B2B Marketplace",       "cap":"mid",   "aliases":["indiamart"]},
    {"symbol":"HONAUT",     "name":"Honeywell Automation India Ltd", "sector":"Technology",     "industry":"Industrial Automation", "cap":"large", "aliases":["honeywell"]},
    {"symbol":"DIXON",      "name":"Dixon Technologies India Ltd",   "sector":"Technology",     "industry":"Electronics Mfg",       "cap":"mid",   "aliases":["dixon"]},
    {"symbol":"KAYNES",     "name":"Kaynes Technology India Ltd",    "sector":"Technology",     "industry":"Electronics Mfg",       "cap":"mid",   "aliases":["kaynes"]},
    {"symbol":"POLICYBZR",  "name":"PB Fintech Ltd",                 "sector":"Technology",     "industry":"Insurtech",             "cap":"mid",   "aliases":["policybazaar","pb fintech"]},

    # ── Banking ───────────────────────────────────────────────────────────────
    {"symbol":"HDFCBANK",   "name":"HDFC Bank Ltd",                  "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["hdfc bank","hdfc"]},
    {"symbol":"ICICIBANK",  "name":"ICICI Bank Ltd",                 "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["icici bank","icici"]},
    {"symbol":"KOTAKBANK",  "name":"Kotak Mahindra Bank Ltd",        "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["kotak bank","kotak"]},
    {"symbol":"SBIN",       "name":"State Bank of India",            "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["sbi","state bank"]},
    {"symbol":"AXISBANK",   "name":"Axis Bank Ltd",                  "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["axis bank","axis"]},
    {"symbol":"INDUSINDBK", "name":"IndusInd Bank Ltd",              "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["indusind bank","indusind"]},
    {"symbol":"PNB",        "name":"Punjab National Bank",           "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["pnb","punjab national"]},
    {"symbol":"BANKBARODA", "name":"Bank of Baroda",                 "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["bob","bank of baroda"]},
    {"symbol":"UNIONBANK",  "name":"Union Bank of India",            "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["union bank"]},
    {"symbol":"FEDERALBNK", "name":"The Federal Bank Ltd",           "sector":"Banking",        "industry":"Banks",                 "cap":"mid",   "aliases":["federal bank"]},
    {"symbol":"IDFCFIRSTB", "name":"IDFC First Bank Ltd",            "sector":"Banking",        "industry":"Banks",                 "cap":"mid",   "aliases":["idfc first","idfc"]},
    {"symbol":"BANDHANBNK", "name":"Bandhan Bank Ltd",               "sector":"Banking",        "industry":"Banks",                 "cap":"mid",   "aliases":["bandhan bank","bandhan"]},
    {"symbol":"RBLBANK",    "name":"RBL Bank Ltd",                   "sector":"Banking",        "industry":"Banks",                 "cap":"small", "aliases":["rbl bank","rbl"]},

    # ── Finance / NBFC ────────────────────────────────────────────────────────
    {"symbol":"BAJFINANCE", "name":"Bajaj Finance Ltd",              "sector":"Finance",        "industry":"NBFC",                  "cap":"large", "aliases":["bajaj finance","bfl"]},
    {"symbol":"BAJAJFINSV", "name":"Bajaj Finserv Ltd",              "sector":"Finance",        "industry":"Diversified Financial", "cap":"large", "aliases":["bajaj finserv"]},
    {"symbol":"MUTHOOTFIN", "name":"Muthoot Finance Ltd",            "sector":"Finance",        "industry":"Gold Finance",          "cap":"mid",   "aliases":["muthoot finance","muthoot"]},
    {"symbol":"MANAPPURAM", "name":"Manappuram Finance Ltd",         "sector":"Finance",        "industry":"Gold Finance",          "cap":"mid",   "aliases":["manappuram"]},
    {"symbol":"CHOLAFIN",   "name":"Cholamandalam Investment & Finance","sector":"Finance",     "industry":"NBFC",                  "cap":"mid",   "aliases":["chola","cholamandalam"]},
    {"symbol":"SHRIRAMFIN", "name":"Shriram Finance Ltd",            "sector":"Finance",        "industry":"Vehicle Finance",       "cap":"large", "aliases":["shriram finance","shriram"]},
    {"symbol":"HDFCLIFE",   "name":"HDFC Life Insurance Company Ltd","sector":"Finance",        "industry":"Life Insurance",        "cap":"large", "aliases":["hdfc life"]},
    {"symbol":"SBILIFE",    "name":"SBI Life Insurance Company Ltd", "sector":"Finance",        "industry":"Life Insurance",        "cap":"large", "aliases":["sbi life"]},
    {"symbol":"LICI",       "name":"Life Insurance Corporation of India","sector":"Finance",    "industry":"Life Insurance",        "cap":"large", "aliases":["lic","lici"]},
    {"symbol":"ICICIPRULI", "name":"ICICI Prudential Life Insurance Co","sector":"Finance",     "industry":"Life Insurance",        "cap":"large", "aliases":["icici pru life","icici prudential"]},
    {"symbol":"ICICIGI",    "name":"ICICI Lombard General Insurance","sector":"Finance",        "industry":"General Insurance",     "cap":"large", "aliases":["icici lombard"]},
    {"symbol":"PFC",        "name":"Power Finance Corporation Ltd",  "sector":"Finance",        "industry":"Power Finance",         "cap":"large", "aliases":["power finance","pfc"]},
    {"symbol":"RECLTD",     "name":"REC Ltd",                        "sector":"Finance",        "industry":"Power Finance",         "cap":"large", "aliases":["rec","rural electrification"]},
    {"symbol":"IRFC",       "name":"Indian Railway Finance Corporation","sector":"Finance",     "industry":"Railway Finance",       "cap":"large", "aliases":["irfc"]},
    {"symbol":"IREDA",      "name":"Indian Renewable Energy Development Agency","sector":"Finance","industry":"Green Finance",      "cap":"mid",   "aliases":["ireda"]},
    {"symbol":"PNBHOUSING", "name":"PNB Housing Finance Ltd",        "sector":"Finance",        "industry":"Housing Finance",       "cap":"mid",   "aliases":["pnb housing"]},
    {"symbol":"ANGELONE",   "name":"Angel One Ltd",                  "sector":"Finance",        "industry":"Broking",               "cap":"mid",   "aliases":["angel one","angel broking"]},
    {"symbol":"CDSL",       "name":"Central Depository Services Ltd","sector":"Finance",        "industry":"Depositories",          "cap":"mid",   "aliases":["cdsl"]},
    {"symbol":"CAMS",       "name":"Computer Age Management Services","sector":"Finance",       "industry":"Mutual Fund Services",  "cap":"mid",   "aliases":["cams"]},
    {"symbol":"360ONE",     "name":"360 One WAM Ltd",                "sector":"Finance",        "industry":"Wealth Management",     "cap":"mid",   "aliases":["360 one","iifl wealth"]},
    {"symbol":"MCX",        "name":"Multi Commodity Exchange of India","sector":"Finance",      "industry":"Commodity Exchange",    "cap":"mid",   "aliases":["mcx"]},
    {"symbol":"M&MFIN",     "name":"Mahindra & Mahindra Financial Services","sector":"Finance", "industry":"Vehicle Finance",       "cap":"mid",   "aliases":["mahindra finance","m&m financial"]},

    # ── Energy / Oil & Gas ────────────────────────────────────────────────────
    {"symbol":"RELIANCE",   "name":"Reliance Industries Ltd",        "sector":"Energy",         "industry":"Oil & Gas Conglomerate","cap":"large", "aliases":["reliance","ril"]},
    {"symbol":"ONGC",       "name":"Oil & Natural Gas Corporation",  "sector":"Energy",         "industry":"Oil & Gas E&P",         "cap":"large", "aliases":["ongc"]},
    {"symbol":"BPCL",       "name":"Bharat Petroleum Corporation",   "sector":"Energy",         "industry":"Oil Refining",          "cap":"large", "aliases":["bpcl","bharat petroleum"]},
    {"symbol":"IOC",        "name":"Indian Oil Corporation Ltd",     "sector":"Energy",         "industry":"Oil Refining",          "cap":"large", "aliases":["ioc","indian oil"]},
    {"symbol":"GAIL",       "name":"GAIL India Ltd",                 "sector":"Energy",         "industry":"Natural Gas",           "cap":"large", "aliases":["gail"]},
    {"symbol":"PETRONET",   "name":"Petronet LNG Ltd",               "sector":"Energy",         "industry":"LNG",                   "cap":"large", "aliases":["petronet"]},
    {"symbol":"COALINDIA",  "name":"Coal India Ltd",                 "sector":"Energy",         "industry":"Coal Mining",           "cap":"large", "aliases":["coal india"]},
    {"symbol":"IGL",        "name":"Indraprastha Gas Ltd",           "sector":"Energy",         "industry":"City Gas Distribution", "cap":"mid",   "aliases":["igl","indraprastha gas"]},
    {"symbol":"MGL",        "name":"Mahanagar Gas Ltd",              "sector":"Energy",         "industry":"City Gas Distribution", "cap":"mid",   "aliases":["mgl","mahanagar gas"]},

    # ── Power ─────────────────────────────────────────────────────────────────
    {"symbol":"NTPC",       "name":"NTPC Ltd",                       "sector":"Power",          "industry":"Power Generation",      "cap":"large", "aliases":["ntpc","national thermal"]},
    {"symbol":"POWERGRID",  "name":"Power Grid Corporation of India","sector":"Power",          "industry":"Power Transmission",    "cap":"large", "aliases":["power grid","pgcil"]},
    {"symbol":"TATAPOWER",  "name":"Tata Power Company Ltd",         "sector":"Power",          "industry":"Power Utilities",       "cap":"large", "aliases":["tata power"]},
    {"symbol":"ADANIGREEN", "name":"Adani Green Energy Ltd",         "sector":"Power",          "industry":"Renewable Energy",      "cap":"large", "aliases":["adani green"]},
    {"symbol":"ADANIPOWER", "name":"Adani Power Ltd",                "sector":"Power",          "industry":"Power Generation",      "cap":"large", "aliases":["adani power"]},
    {"symbol":"NHPC",       "name":"NHPC Ltd",                       "sector":"Power",          "industry":"Hydro Power",           "cap":"large", "aliases":["nhpc"]},
    {"symbol":"SJVN",       "name":"SJVN Ltd",                       "sector":"Power",          "industry":"Hydro Power",           "cap":"mid",   "aliases":["sjvn"]},
    {"symbol":"TORNTPOWER", "name":"Torrent Power Ltd",              "sector":"Power",          "industry":"Power Utilities",       "cap":"mid",   "aliases":["torrent power"]},
    {"symbol":"SUZLON",     "name":"Suzlon Energy Ltd",              "sector":"Power",          "industry":"Wind Energy",           "cap":"mid",   "aliases":["suzlon"]},
    {"symbol":"CESC",       "name":"CESC Ltd",                       "sector":"Power",          "industry":"Power Utilities",       "cap":"mid",   "aliases":["cesc"]},
    {"symbol":"JSWENERGY",  "name":"JSW Energy Ltd",                 "sector":"Power",          "industry":"Power Generation",      "cap":"large", "aliases":["jsw energy"]},

    # ── Infrastructure / Construction ─────────────────────────────────────────
    {"symbol":"LT",         "name":"Larsen & Toubro Ltd",            "sector":"Infrastructure", "industry":"Construction EPC",      "cap":"large", "aliases":["l&t","larsen","toubro","lt"]},
    {"symbol":"BHEL",       "name":"Bharat Heavy Electricals Ltd",   "sector":"Infrastructure", "industry":"Heavy Engineering",     "cap":"large", "aliases":["bhel","bharat heavy"]},
    {"symbol":"ADANIENT",   "name":"Adani Enterprises Ltd",          "sector":"Infrastructure", "industry":"Diversified",           "cap":"large", "aliases":["adani enterprises","adani"]},
    {"symbol":"ADANIPORTS", "name":"Adani Ports & SEZ Ltd",          "sector":"Infrastructure", "industry":"Ports",                 "cap":"large", "aliases":["adani ports","apsez"]},
    {"symbol":"SIEMENS",    "name":"Siemens Ltd",                    "sector":"Infrastructure", "industry":"Electrical Equipment",  "cap":"large", "aliases":["siemens"]},
    {"symbol":"ABB",        "name":"ABB India Ltd",                  "sector":"Infrastructure", "industry":"Power Transmission",    "cap":"large", "aliases":["abb india","abb"]},
    {"symbol":"THERMAX",    "name":"Thermax Ltd",                    "sector":"Infrastructure", "industry":"Industrial Boilers",    "cap":"mid",   "aliases":["thermax"]},
    {"symbol":"CUMMINSIND", "name":"Cummins India Ltd",              "sector":"Infrastructure", "industry":"Industrial Engines",    "cap":"mid",   "aliases":["cummins india","cummins"]},
    {"symbol":"CGPOWER",    "name":"CG Power and Industrial Solutions","sector":"Infrastructure","industry":"Electrical Equipment", "cap":"mid",   "aliases":["cg power"]},
    {"symbol":"POLYCAB",    "name":"Polycab India Ltd",              "sector":"Infrastructure", "industry":"Cables & Wires",        "cap":"large", "aliases":["polycab"]},
    {"symbol":"KEI",        "name":"KEI Industries Ltd",             "sector":"Infrastructure", "industry":"Cables & Wires",        "cap":"mid",   "aliases":["kei industries"]},
    {"symbol":"NBCC",       "name":"NBCC India Ltd",                 "sector":"Infrastructure", "industry":"Govt Construction",     "cap":"mid",   "aliases":["nbcc"]},
    {"symbol":"NCC",        "name":"NCC Ltd",                        "sector":"Infrastructure", "industry":"Construction",          "cap":"small", "aliases":["ncc construction"]},
    {"symbol":"ASTRAL",     "name":"Astral Ltd",                     "sector":"Infrastructure", "industry":"PVC Pipes",             "cap":"mid",   "aliases":["astral pipes","astral"]},
    {"symbol":"SUPREMEIND", "name":"Supreme Industries Ltd",         "sector":"Infrastructure", "industry":"Plastic Products",      "cap":"mid",   "aliases":["supreme industries"]},
    {"symbol":"CONCOR",     "name":"Container Corporation of India", "sector":"Infrastructure", "industry":"Logistics",             "cap":"large", "aliases":["concor","container corporation"]},
    {"symbol":"DELHIVERY",  "name":"Delhivery Ltd",                  "sector":"Infrastructure", "industry":"Logistics",             "cap":"mid",   "aliases":["delhivery"]},

    # ── Defence & Aerospace ───────────────────────────────────────────────────
    {"symbol":"HAL",        "name":"Hindustan Aeronautics Ltd",      "sector":"Defence",        "industry":"Aerospace & Defence",   "cap":"large", "aliases":["hal","hindustan aeronautics"]},
    {"symbol":"BEL",        "name":"Bharat Electronics Ltd",         "sector":"Defence",        "industry":"Defence Electronics",   "cap":"large", "aliases":["bel","bharat electronics"]},
    {"symbol":"RVNL",       "name":"Rail Vikas Nigam Ltd",           "sector":"Defence",        "industry":"Railway Infrastructure","cap":"mid",   "aliases":["rvnl","rail vikas"]},
    {"symbol":"IRCON",      "name":"IRCON International Ltd",        "sector":"Defence",        "industry":"Railway Construction",  "cap":"mid",   "aliases":["ircon"]},
    {"symbol":"MAZDOCK",    "name":"Mazagon Dock Shipbuilders Ltd",  "sector":"Defence",        "industry":"Shipbuilding",          "cap":"mid",   "aliases":["mazagon dock","mazagaon"]},
    {"symbol":"GRSE",       "name":"Garden Reach Shipbuilders & Engineers","sector":"Defence",  "industry":"Shipbuilding",          "cap":"mid",   "aliases":["grse","garden reach"]},
    {"symbol":"COCHINSHIP", "name":"Cochin Shipyard Ltd",            "sector":"Defence",        "industry":"Shipbuilding",          "cap":"mid",   "aliases":["cochin shipyard"]},

    # ── Pharmaceuticals & Healthcare ──────────────────────────────────────────
    {"symbol":"SUNPHARMA",  "name":"Sun Pharmaceutical Industries",  "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["sun pharma","sun pharmaceutical"]},
    {"symbol":"DRREDDY",    "name":"Dr Reddy's Laboratories Ltd",    "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["dr reddys","dr reddy"]},
    {"symbol":"CIPLA",      "name":"Cipla Ltd",                      "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["cipla"]},
    {"symbol":"DIVISLAB",   "name":"Divi's Laboratories Ltd",        "sector":"Pharmaceuticals","industry":"APIs",                  "cap":"large", "aliases":["divis labs","divi"]},
    {"symbol":"AUROPHARMA", "name":"Aurobindo Pharma Ltd",           "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["aurobindo"]},
    {"symbol":"LUPIN",      "name":"Lupin Ltd",                      "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["lupin"]},
    {"symbol":"BIOCON",     "name":"Biocon Ltd",                     "sector":"Pharmaceuticals","industry":"Biotechnology",         "cap":"large", "aliases":["biocon"]},
    {"symbol":"TORNTPHARM", "name":"Torrent Pharmaceuticals Ltd",    "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["torrent pharma","torrent"]},
    {"symbol":"ALKEM",      "name":"Alkem Laboratories Ltd",         "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["alkem"]},
    {"symbol":"GLENMARK",   "name":"Glenmark Pharmaceuticals Ltd",   "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["glenmark"]},
    {"symbol":"IPCALAB",    "name":"IPCA Laboratories Ltd",          "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["ipca"]},
    {"symbol":"GRANULES",   "name":"Granules India Ltd",             "sector":"Pharmaceuticals","industry":"APIs",                  "cap":"mid",   "aliases":["granules india","granules"]},
    {"symbol":"NATCOPHARM", "name":"Natco Pharma Ltd",               "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["natco pharma","natco"]},
    # JBCHEPHARM removed (2026-08-09) — absent from bhavcopy's EQ series on
    # 4 consecutive trading days (04-07 Aug 2026) and from every other series
    # too; yfinance's fast_info returns a stale-looking price but its
    # historical-bars fetch also fails for the same window. No successor
    # symbol found under any name/fragment search — dropped rather than
    # guessed at, per this investigation's own "do not guess" standard.
    {"symbol":"ZYDUSLIFE",  "name":"Zydus Lifesciences Ltd",         "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["zydus","cadila"]},
    {"symbol":"ABBOTINDIA", "name":"Abbott India Ltd",               "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"large", "aliases":["abbott india","abbott"]},
    {"symbol":"APOLLOHOSP", "name":"Apollo Hospitals Enterprise Ltd","sector":"Healthcare",     "industry":"Hospitals",             "cap":"large", "aliases":["apollo hospitals","apollo"]},
    {"symbol":"FORTIS",     "name":"Fortis Healthcare Ltd",          "sector":"Healthcare",     "industry":"Hospitals",             "cap":"mid",   "aliases":["fortis healthcare","fortis"]},
    {"symbol":"MAXHEALTH",  "name":"Max Healthcare Institute Ltd",   "sector":"Healthcare",     "industry":"Hospitals",             "cap":"mid",   "aliases":["max healthcare","max hospital"]},
    {"symbol":"LALPATHLAB", "name":"Dr Lal PathLabs Ltd",            "sector":"Healthcare",     "industry":"Diagnostics",           "cap":"mid",   "aliases":["lal pathlabs","dr lal"]},
    {"symbol":"NH",         "name":"Narayana Hrudayalaya Ltd",       "sector":"Healthcare",     "industry":"Hospitals",             "cap":"mid",   "aliases":["narayana hrudayalaya","nh"]},
    {"symbol":"KIMS",       "name":"Krishna Institute of Medical Sciences","sector":"Healthcare","industry":"Hospitals",            "cap":"mid",   "aliases":["kims"]},
    {"symbol":"MEDANTA",    "name":"Global Health Ltd",              "sector":"Healthcare",     "industry":"Hospitals",             "cap":"mid",   "aliases":["medanta","global health"]},

    # ── FMCG ──────────────────────────────────────────────────────────────────
    {"symbol":"HINDUNILVR", "name":"Hindustan Unilever Ltd",         "sector":"FMCG",           "industry":"Personal Products",     "cap":"large", "aliases":["hul","hindustan unilever","hindustan lever"]},
    {"symbol":"ITC",        "name":"ITC Ltd",                        "sector":"FMCG",           "industry":"Tobacco & FMCG",        "cap":"large", "aliases":["itc"]},
    {"symbol":"NESTLEIND",  "name":"Nestle India Ltd",               "sector":"FMCG",           "industry":"Packaged Foods",        "cap":"large", "aliases":["nestle india","nestle","maggi"]},
    {"symbol":"BRITANNIA",  "name":"Britannia Industries Ltd",       "sector":"FMCG",           "industry":"Biscuits & Bakery",     "cap":"large", "aliases":["britannia"]},
    {"symbol":"DABUR",      "name":"Dabur India Ltd",                "sector":"FMCG",           "industry":"Personal Care",         "cap":"large", "aliases":["dabur"]},
    {"symbol":"MARICO",     "name":"Marico Ltd",                     "sector":"FMCG",           "industry":"Personal Care",         "cap":"large", "aliases":["marico","parachute"]},
    {"symbol":"COLPAL",     "name":"Colgate Palmolive India Ltd",    "sector":"FMCG",           "industry":"Oral Care",             "cap":"large", "aliases":["colgate palmolive","colgate"]},
    {"symbol":"GODREJCP",   "name":"Godrej Consumer Products Ltd",   "sector":"FMCG",           "industry":"Personal Products",     "cap":"large", "aliases":["godrej consumer","gcpl","godrej"]},
    {"symbol":"EMAMILTD",   "name":"Emami Ltd",                      "sector":"FMCG",           "industry":"Personal Care",         "cap":"mid",   "aliases":["emami"]},
    {"symbol":"BIKAJI",     "name":"Bikaji Foods International Ltd", "sector":"FMCG",           "industry":"Packaged Snacks",       "cap":"mid",   "aliases":["bikaji"]},

    # ── Consumer / Retail ─────────────────────────────────────────────────────
    {"symbol":"TITAN",      "name":"Titan Company Ltd",              "sector":"Consumer",       "industry":"Jewellery & Watches",   "cap":"large", "aliases":["titan","tanishq","fastrack"]},
    {"symbol":"DMART",      "name":"Avenue Supermarts Ltd",          "sector":"Consumer",       "industry":"Supermarkets",          "cap":"large", "aliases":["dmart","avenue supermarts","d-mart"]},
    {"symbol":"ETERNAL",    "name":"Eternal Ltd",                    "sector":"Consumer",       "industry":"Food Delivery",         "cap":"large", "aliases":["zomato","blinkit","eternal"]},
    {"symbol":"NYKAA",      "name":"FSN E-Commerce Ventures Ltd",    "sector":"Consumer",       "industry":"Beauty E-Commerce",     "cap":"mid",   "aliases":["nykaa","fsn"]},
    {"symbol":"IRCTC",      "name":"Indian Railway Catering and Tourism","sector":"Consumer",   "industry":"Rail Tourism",          "cap":"large", "aliases":["irctc"]},
    {"symbol":"TRENT",      "name":"Trent Ltd",                      "sector":"Consumer",       "industry":"Fashion Retail",        "cap":"mid",   "aliases":["trent","westside","zudio"]},
    {"symbol":"HAVELLS",    "name":"Havells India Ltd",              "sector":"Consumer",       "industry":"Electrical Equipment",  "cap":"mid",   "aliases":["havells"]},
    {"symbol":"VOLTAS",     "name":"Voltas Ltd",                     "sector":"Consumer",       "industry":"HVAC",                  "cap":"mid",   "aliases":["voltas"]},
    {"symbol":"KALYANKJIL", "name":"Kalyan Jewellers India Ltd",     "sector":"Consumer",       "industry":"Jewellery",             "cap":"mid",   "aliases":["kalyan jewellers","kalyan"]},
    {"symbol":"PAGEIND",    "name":"Page Industries Ltd",            "sector":"Consumer",       "industry":"Innerwear",             "cap":"large", "aliases":["page industries","jockey"]},
    {"symbol":"JUBLFOOD",   "name":"Jubilant FoodWorks Ltd",         "sector":"Consumer",       "industry":"QSR",                   "cap":"mid",   "aliases":["jubilant foodworks","dominos","jubilant"]},
    {"symbol":"BATAINDIA",  "name":"Bata India Ltd",                 "sector":"Consumer",       "industry":"Footwear",              "cap":"mid",   "aliases":["bata india","bata"]},
    {"symbol":"BLUEDART",   "name":"Blue Dart Express Ltd",          "sector":"Consumer",       "industry":"Express Logistics",     "cap":"mid",   "aliases":["blue dart"]},

    # ── Automotive ────────────────────────────────────────────────────────────
    {"symbol":"MARUTI",     "name":"Maruti Suzuki India Ltd",        "sector":"Automotive",     "industry":"Passenger Vehicles",    "cap":"large", "aliases":["maruti suzuki","maruti","suzuki"]},
    {"symbol":"TATAMOTORS", "name":"Tata Motors Ltd",                "sector":"Automotive",     "industry":"Automobiles",           "cap":"large", "aliases":["tata motors"]},
    {"symbol":"M&M",        "name":"Mahindra & Mahindra Ltd",        "sector":"Automotive",     "industry":"Automobiles",           "cap":"large", "aliases":["mahindra","m&m"]},
    {"symbol":"BAJAJ-AUTO", "name":"Bajaj Auto Ltd",                 "sector":"Automotive",     "industry":"Two-Wheelers",          "cap":"large", "aliases":["bajaj auto","bajaj"]},
    {"symbol":"HEROMOTOCO", "name":"Hero MotoCorp Ltd",              "sector":"Automotive",     "industry":"Two-Wheelers",          "cap":"large", "aliases":["hero motocorp","hero honda","hero"]},
    {"symbol":"EICHERMOT",  "name":"Eicher Motors Ltd",              "sector":"Automotive",     "industry":"Two-Wheelers",          "cap":"large", "aliases":["eicher motors","royal enfield"]},
    {"symbol":"TVSMOTOR",   "name":"TVS Motor Company Ltd",          "sector":"Automotive",     "industry":"Two-Wheelers",          "cap":"large", "aliases":["tvs motor","tvs"]},
    {"symbol":"ESCORTS",    "name":"Escorts Kubota Ltd",             "sector":"Automotive",     "industry":"Tractors",              "cap":"mid",   "aliases":["escorts kubota","escorts"]},
    {"symbol":"BOSCHLTD",   "name":"Bosch Ltd",                      "sector":"Automotive",     "industry":"Auto Components",       "cap":"large", "aliases":["bosch india","bosch"]},
    {"symbol":"MOTHERSON",  "name":"Samvardhana Motherson Intl Ltd", "sector":"Automotive",     "industry":"Auto Components",       "cap":"mid",   "aliases":["motherson","samvardhana"]},
    {"symbol":"EXIDEIND",   "name":"Exide Industries Ltd",           "sector":"Automotive",     "industry":"Batteries",             "cap":"mid",   "aliases":["exide"]},

    # ── Metals & Mining ───────────────────────────────────────────────────────
    {"symbol":"TATASTEEL",  "name":"Tata Steel Ltd",                 "sector":"Metals",         "industry":"Steel",                 "cap":"large", "aliases":["tata steel"]},
    {"symbol":"JSWSTEEL",   "name":"JSW Steel Ltd",                  "sector":"Metals",         "industry":"Steel",                 "cap":"large", "aliases":["jsw steel","jsw"]},
    {"symbol":"HINDALCO",   "name":"Hindalco Industries Ltd",        "sector":"Metals",         "industry":"Aluminium",             "cap":"large", "aliases":["hindalco","hindalco industries"]},
    {"symbol":"VEDL",       "name":"Vedanta Ltd",                    "sector":"Metals",         "industry":"Diversified Metals",    "cap":"large", "aliases":["vedanta"]},
    {"symbol":"SAIL",       "name":"Steel Authority of India Ltd",   "sector":"Metals",         "industry":"Steel",                 "cap":"large", "aliases":["sail","steel authority"]},
    {"symbol":"NMDC",       "name":"NMDC Ltd",                       "sector":"Metals",         "industry":"Iron Ore",              "cap":"large", "aliases":["nmdc"]},
    {"symbol":"JINDALSTEL", "name":"Jindal Steel & Power Ltd",       "sector":"Metals",         "industry":"Steel",                 "cap":"mid",   "aliases":["jindal steel","jspl"]},
    {"symbol":"NATIONALUM", "name":"National Aluminium Company Ltd", "sector":"Metals",         "industry":"Aluminium",             "cap":"mid",   "aliases":["nalco","national aluminium"]},
    {"symbol":"APLAPOLLO",  "name":"APL Apollo Tubes Ltd",           "sector":"Metals",         "industry":"Steel Tubes",           "cap":"mid",   "aliases":["apl apollo","apollo tubes"]},

    # ── Chemicals / Specialty ─────────────────────────────────────────────────
    {"symbol":"PIDILITIND", "name":"Pidilite Industries Ltd",        "sector":"Chemicals",      "industry":"Adhesives",             "cap":"large", "aliases":["pidilite","fevicol","m-seal"]},
    {"symbol":"ASIANPAINT", "name":"Asian Paints Ltd",               "sector":"Chemicals",      "industry":"Paints",                "cap":"large", "aliases":["asian paints"]},
    {"symbol":"DEEPAKNTR",  "name":"Deepak Nitrite Ltd",             "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["deepak nitrite"]},
    {"symbol":"SRF",        "name":"SRF Ltd",                        "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["srf"]},
    {"symbol":"UPL",        "name":"UPL Ltd",                        "sector":"Chemicals",      "industry":"Agrochemicals",         "cap":"large", "aliases":["upl","united phosphorus"]},
    {"symbol":"ATUL",       "name":"Atul Ltd",                       "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["atul ltd","atul"]},
    {"symbol":"NAVINFLUOR", "name":"Navin Fluorine International Ltd","sector":"Chemicals",     "industry":"Fluorochemicals",       "cap":"mid",   "aliases":["navin fluorine"]},
    {"symbol":"TATACHEM",   "name":"Tata Chemicals Ltd",             "sector":"Chemicals",      "industry":"Chemicals",             "cap":"mid",   "aliases":["tata chemicals"]},
    {"symbol":"VINATIORGA", "name":"Vinati Organics Ltd",            "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["vinati organics","vinati"]},
    {"symbol":"PIIND",      "name":"PI Industries Ltd",              "sector":"Chemicals",      "industry":"Agrochemicals",         "cap":"mid",   "aliases":["pi industries"]},
    {"symbol":"CLEAN",      "name":"Clean Science & Technology Ltd", "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["clean science"]},
    {"symbol":"COROMANDEL", "name":"Coromandel International Ltd",   "sector":"Chemicals",      "industry":"Fertilisers",           "cap":"mid",   "aliases":["coromandel"]},

    # ── Cement ────────────────────────────────────────────────────────────────
    {"symbol":"ULTRACEMCO", "name":"UltraTech Cement Ltd",           "sector":"Cement",         "industry":"Cement",                "cap":"large", "aliases":["ultratech cement","ultratech"]},
    {"symbol":"GRASIM",     "name":"Grasim Industries Ltd",          "sector":"Cement",         "industry":"Cement & VSF",          "cap":"large", "aliases":["grasim"]},
    {"symbol":"SHREECEM",   "name":"Shree Cement Ltd",               "sector":"Cement",         "industry":"Cement",                "cap":"large", "aliases":["shree cement"]},
    {"symbol":"DALBHARAT",  "name":"Dalmia Bharat Ltd",              "sector":"Cement",         "industry":"Cement",                "cap":"mid",   "aliases":["dalmia bharat","dalmia"]},
    {"symbol":"RAMCOCEM",   "name":"The Ramco Cements Ltd",          "sector":"Cement",         "industry":"Cement",                "cap":"mid",   "aliases":["ramco cement","ramco"]},
    {"symbol":"JKCEMENT",   "name":"JK Cement Ltd",                  "sector":"Cement",         "industry":"Cement",                "cap":"mid",   "aliases":["jk cement"]},

    # ── Real Estate ───────────────────────────────────────────────────────────
    {"symbol":"DLF",        "name":"DLF Ltd",                        "sector":"Real Estate",    "industry":"Real Estate Dev",       "cap":"large", "aliases":["dlf"]},
    {"symbol":"GODREJPROP", "name":"Godrej Properties Ltd",          "sector":"Real Estate",    "industry":"Real Estate Dev",       "cap":"mid",   "aliases":["godrej properties","godrej props"]},
    {"symbol":"OBEROIRLTY", "name":"Oberoi Realty Ltd",              "sector":"Real Estate",    "industry":"Real Estate Dev",       "cap":"mid",   "aliases":["oberoi realty","oberoi"]},
    {"symbol":"PRESTIGE",   "name":"Prestige Estates Projects Ltd",  "sector":"Real Estate",    "industry":"Real Estate Dev",       "cap":"mid",   "aliases":["prestige estates","prestige"]},
    {"symbol":"PHOENIXLTD", "name":"Phoenix Mills Ltd",              "sector":"Real Estate",    "industry":"Retail REITs",          "cap":"mid",   "aliases":["phoenix mills","phoenix"]},
    {"symbol":"BRIGADE",    "name":"Brigade Enterprises Ltd",        "sector":"Real Estate",    "industry":"Real Estate Dev",       "cap":"mid",   "aliases":["brigade"]},

    # ── Telecom ───────────────────────────────────────────────────────────────
    {"symbol":"BHARTIARTL", "name":"Bharti Airtel Ltd",              "sector":"Telecom",        "industry":"Telecom Services",      "cap":"large", "aliases":["bharti airtel","airtel"]},
    {"symbol":"INDUSTOWER", "name":"Indus Towers Ltd",               "sector":"Telecom",        "industry":"Telecom Infrastructure","cap":"large", "aliases":["indus towers"]},
    {"symbol":"TATACOMM",   "name":"Tata Communications Ltd",        "sector":"Telecom",        "industry":"Data Services",         "cap":"mid",   "aliases":["tata communications","tata comm"]},

    # ── Railways / Government PSU ─────────────────────────────────────────────
    {"symbol":"RITES",      "name":"RITES Ltd",                      "sector":"Infrastructure", "industry":"Railway Consultancy",   "cap":"mid",   "aliases":["rites"]},
    {"symbol":"RAILTEL",    "name":"RailTel Corporation of India Ltd","sector":"Technology",     "industry":"Telecom Infrastructure","cap":"small",  "aliases":["railtel"]},
    {"symbol":"BEML",       "name":"BEML Ltd",                       "sector":"Defence",        "industry":"Defence Manufacturing", "cap":"mid",   "aliases":["beml"]},

    # ── Coverage gap fix (2026-07-26) ────────────────────────────────────────
    # 34 real, listed companies confirmed missing from this universe via the
    # AI Search V3 benchmark — the benchmark's own reference company list
    # (benchmarks/ai_search/data.py) named these in generated questions, but
    # this file had no matching entry, so real entity/comparison detection
    # silently failed on well-known names (Ashok Leyland, Hindustan Zinc,
    # IndiGo, Paytm, etc.) for both V2 and V3 identically. Sector/name data
    # cross-checked against that same reference file.
    {"symbol":"CANBK",      "name":"Canara Bank",                    "sector":"Banking",        "industry":"PSU Bank",               "cap":"large", "aliases":["canara bank","canara"]},
    {"symbol":"AUBANK",     "name":"AU Small Finance Bank Ltd",      "sector":"Banking",        "industry":"Small Finance Bank",     "cap":"mid",   "aliases":["au small finance bank","au bank"]},
    {"symbol":"STARHEALTH", "name":"Star Health and Allied Insurance Co Ltd", "sector":"Insurance", "industry":"Health Insurance",   "cap":"mid",   "aliases":["star health","star health insurance"]},
    {"symbol":"ASHOKLEY",   "name":"Ashok Leyland Ltd",              "sector":"Auto",           "industry":"Commercial Vehicles",    "cap":"large", "aliases":["ashok leyland"]},
    {"symbol":"TATACONSUM", "name":"Tata Consumer Products Ltd",     "sector":"FMCG",           "industry":"Beverages & Food",       "cap":"large", "aliases":["tata consumer","tata consumer products"]},
    {"symbol":"VBL",        "name":"Varun Beverages Ltd",            "sector":"FMCG",           "industry":"Beverages",              "cap":"large", "aliases":["varun beverages"]},
    {"symbol":"CROMPTON",   "name":"Crompton Greaves Consumer Electricals Ltd", "sector":"Consumer", "industry":"Consumer Electricals", "cap":"mid", "aliases":["crompton","crompton greaves"]},
    {"symbol":"SYRMA",      "name":"Syrma SGS Technology Ltd",       "sector":"Electronics",    "industry":"Electronics Manufacturing", "cap":"small", "aliases":["syrma","syrma sgs"]},
    {"symbol":"AMBER",      "name":"Amber Enterprises India Ltd",    "sector":"Electronics",    "industry":"Electronics Manufacturing", "cap":"mid", "aliases":["amber enterprises","amber"]},
    {"symbol":"BHARATFORG", "name":"Bharat Forge Ltd",               "sector":"Defence",        "industry":"Forging & Auto Components","cap":"large","aliases":["bharat forge"]},
    {"symbol":"BDL",        "name":"Bharat Dynamics Ltd",            "sector":"Defence",        "industry":"Defence Manufacturing",  "cap":"mid",   "aliases":["bharat dynamics"]},
    {"symbol":"SOLARINDS",  "name":"Solar Industries India Ltd",     "sector":"Defence",        "industry":"Explosives & Defence",   "cap":"large", "aliases":["solar industries"]},
    {"symbol":"PAYTM",      "name":"One97 Communications Ltd",       "sector":"New-age",        "industry":"Fintech / Payments",     "cap":"mid",   "aliases":["paytm","one97","one97 communications"]},
    {"symbol":"ABFRL",      "name":"Aditya Birla Fashion and Retail Ltd", "sector":"Retail",     "industry":"Apparel Retail",         "cap":"mid",   "aliases":["aditya birla fashion","abfrl"]},
    {"symbol":"VMART",      "name":"V-Mart Retail Ltd",              "sector":"Retail",         "industry":"Value Retail",           "cap":"small", "aliases":["v-mart","vmart"]},
    {"symbol":"INDIGO",     "name":"InterGlobe Aviation Ltd",        "sector":"Aviation",       "industry":"Airlines",               "cap":"large", "aliases":["indigo","interglobe aviation"]},
    # SPICEJET removed (2026-08-09) — same investigation as JBCHEPHARM above:
    # absent from bhavcopy for 4 consecutive trading days; yfinance returns a
    # hard "quote not found" 404, a stronger signal than the other two
    # removals. No successor symbol found.
    {"symbol":"HINDZINC",   "name":"Hindustan Zinc Ltd",             "sector":"Metals",         "industry":"Zinc & Silver Mining",   "cap":"large", "aliases":["hindustan zinc","hind zinc"]},
    {"symbol":"GMRAIRPORT", "name":"GMR Airports Infrastructure Ltd","sector":"Infra",          "industry":"Airport Infrastructure", "cap":"large", "aliases":["gmr infrastructure","gmr airports","gmr"]},
    {"symbol":"IRB",        "name":"IRB Infrastructure Developers Ltd", "sector":"Infra",       "industry":"Road Infrastructure",    "cap":"mid",   "aliases":["irb infrastructure","irb"]},
    {"symbol":"AMBUJACEM",  "name":"Ambuja Cements Ltd",             "sector":"Cement",         "industry":"Cement",                 "cap":"large", "aliases":["ambuja cements","ambuja"]},
    {"symbol":"ACC",        "name":"ACC Ltd",                        "sector":"Cement",         "industry":"Cement",                 "cap":"large", "aliases":["acc limited","acc cement"]},
    {"symbol":"IDEA",       "name":"Vodafone Idea Ltd",              "sector":"Telecom",        "industry":"Telecom Services",       "cap":"mid",   "aliases":["vodafone idea","vi"]},
    {"symbol":"ZEEL",       "name":"Zee Entertainment Enterprises Ltd", "sector":"Media",       "industry":"Broadcasting",           "cap":"mid",   "aliases":["zee entertainment","zee"]},
    {"symbol":"SUNTV",      "name":"Sun TV Network Ltd",             "sector":"Media",          "industry":"Broadcasting",           "cap":"mid",   "aliases":["sun tv","sun tv network"]},
    {"symbol":"PVRINOX",    "name":"PVR INOX Ltd",                   "sector":"Media",          "industry":"Multiplex / Cinema",     "cap":"mid",   "aliases":["pvr inox","pvr","inox"]},
    {"symbol":"IEX",        "name":"Indian Energy Exchange Ltd",     "sector":"Exchange",       "industry":"Power Exchange",         "cap":"mid",   "aliases":["indian energy exchange","iex"]},
    {"symbol":"BSE",        "name":"BSE Ltd",                        "sector":"Exchange",       "industry":"Stock Exchange",         "cap":"mid",   "aliases":["bse limited","bombay stock exchange"]},
    {"symbol":"IIFL",       "name":"IIFL Finance Ltd",               "sector":"NBFC",           "industry":"Diversified NBFC",       "cap":"mid",   "aliases":["iifl finance","iifl"]},
    {"symbol":"MOTILALOFS", "name":"Motilal Oswal Financial Services Ltd", "sector":"Broking",  "industry":"Broking & Asset Management", "cap":"mid", "aliases":["motilal oswal","motilal oswal financial"]},
    {"symbol":"KFINTECH",   "name":"KFin Technologies Ltd",          "sector":"Fintech",        "industry":"RTA Services",           "cap":"mid",   "aliases":["kfin technologies","kfintech"]},
    # GUJGASLTD removed (2026-08-09) — same investigation as JBCHEPHARM/
    # SPICEJET above: absent from bhavcopy for 4 consecutive trading days,
    # yfinance's historical-bars fetch fails for the same window. No
    # successor symbol found.

    # ═══════════════════════════════════════════════════════════════════════
    # Nifty 500 expansion (2026-07-26). Sourced from Wikipedia's NIFTY_500
    # constituents table ("as of 30 June 2026", 500-row table verified by
    # count), cross-referenced against the universe above — additive only,
    # never overwrites an already-present symbol. Sector/cap are a best-
    # effort mapping onto this file's existing taxonomy (Wikipedia's own
    # "industry" column is preserved verbatim in "industry"); "cap" only
    # affects the /api/companies directory filter/sort, not AI Search
    # entity matching, so it's a coarser heuristic than symbol/name, which
    # are the accuracy-critical fields here. Aliases that would collide
    # across two or more different companies in this batch (or an existing
    # entry) were dropped rather than kept ambiguous — see the generation
    # script's collision check; this is the same false-positive-match bug
    # class already found and fixed once for "ITC"/"REC"/"LIC" above.
    # ═══════════════════════════════════════════════════════════════════════
    # ── Automotive (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"APOLLOTYRE", "name":"Apollo Tyres Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["apollotyre"]},
    {"symbol":"ARE&M", "name":"Amara Raja Energy & Mobility Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["amara", "amara raja", "amaron", "are&m"]},
    {"symbol":"ASAHIINDIA", "name":"Asahi India Glass Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["asahi", "asahi glass", "asahiindia"]},
    {"symbol":"ATHERENERG", "name":"Ather Energy Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["ather", "atherenerg"]},
    {"symbol":"BALKRISIND", "name":"Balkrishna Industries Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["balkrishna", "balkrisind"]},
    {"symbol":"BELRISE", "name":"Belrise Industries Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["belrise"]},
    {"symbol":"CEATLTD", "name":"Ceat Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["ceat", "ceatltd"]},
    {"symbol":"CIEINDIA", "name":"CIE Automotive India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["cie", "cie automotive", "cieindia"]},
    {"symbol":"CRAFTSMAN", "name":"Craftsman Automation Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["craftsman", "craftsman automation"]},
    {"symbol":"ENDURANCE", "name":"Endurance Technologies Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["endurance"]},
    {"symbol":"FORCEMOT", "name":"Force Motors Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["force", "forcemot"]},
    {"symbol":"GABRIEL", "name":"Gabriel India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["gabriel"]},
    {"symbol":"HYUNDAI", "name":"Hyundai Motor India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["hyundai"]},
    {"symbol":"JBMA", "name":"JBM Auto Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["jbm", "jbma"]},
    {"symbol":"JKTYRE", "name":"JK Tyre & Industries Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["jktyre"]},
    {"symbol":"MINDACORP", "name":"Minda Corporation Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["minda corporation", "mindacorp"]},
    {"symbol":"MRF", "name":"MRF Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["mrf"]},
    {"symbol":"MSUMI", "name":"Motherson Sumi Wiring India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["motherson sumi", "msumi"]},
    {"symbol":"OLAELEC", "name":"Ola Electric Mobility Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["ola", "ola electric", "olaelec"]},
    {"symbol":"OLECTRA", "name":"Olectra Greentech Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["olectra", "olectra greentech"]},
    {"symbol":"RKFORGE", "name":"Ramkrishna Forgings Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["ramkrishna", "ramkrishna forgings", "rkforge"]},
    {"symbol":"SCHAEFFLER", "name":"Schaeffler India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["schaeffler"]},
    {"symbol":"SONACOMS", "name":"Sona BLW Precision Forgings Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["sona", "sona blw", "sonacoms"]},
    {"symbol":"TENNIND", "name":"Tenneco Clean Air India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["tenneco", "tenneco air", "tennind"]},
    {"symbol":"TIINDIA", "name":"Tube Investments of India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["tiindia"]},
    {"symbol":"TMPV", "name":"Tata Motors Passenger Vehicles Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["tata passenger", "tmpv"]},
    {"symbol":"UNOMINDA", "name":"UNO Minda Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["uno", "uno minda", "minda industries", "unominda"]},
    {"symbol":"ZFCVINDIA", "name":"ZF Commercial Vehicle Control Systems India Ltd", "sector":"Automotive", "industry":"Automobile and Auto Components", "cap":"mid", "aliases":["commercial", "commercial vehicle", "zfcvindia"]},
    # ── Banking (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"BANKINDIA", "name":"Bank of India", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["bankindia"]},
    {"symbol":"CENTRALBK", "name":"Central Bank of India", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["central", "centralbk"]},
    {"symbol":"CUB", "name":"City Union Bank Ltd", "sector":"Banking", "industry":"Financial Services", "cap":"large", "aliases":["city", "city union", "cub"]},
    {"symbol":"IDBI", "name":"IDBI Bank Ltd", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["idbi"]},
    {"symbol":"INDIANB", "name":"Indian Bank", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["indianb"]},
    {"symbol":"IOB", "name":"Indian Overseas Bank", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["iob", "overseas"]},
    {"symbol":"J&KBANK", "name":"Jammu & Kashmir Bank Ltd", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["j&kbank", "jammu", "jammu kashmir"]},
    {"symbol":"KARURVYSYA", "name":"Karur Vysya Bank Ltd", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["karur", "karur vysya", "karurvysya"]},
    {"symbol":"MAHABANK", "name":"Bank of Maharashtra", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["mahabank", "maharashtra"]},
    {"symbol":"UCOBANK", "name":"UCO Bank", "sector":"Banking", "industry":"Financial Services", "cap":"mid", "aliases":["uco", "ucobank"]},
    {"symbol":"YESBANK", "name":"Yes Bank Ltd", "sector":"Banking", "industry":"Financial Services", "cap":"large", "aliases":["yes", "yesbank"]},
    # ── Cement (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"INDIACEM", "name":"India Cements Ltd", "sector":"Cement", "industry":"Construction Materials", "cap":"mid", "aliases":["indiacem"]},
    {"symbol":"JSWCEMENT", "name":"JSW Cement Ltd", "sector":"Cement", "industry":"Construction Materials", "cap":"mid", "aliases":["jswcement"]},
    {"symbol":"NUVOCO", "name":"Nuvoco Vistas Corporation Ltd", "sector":"Cement", "industry":"Construction Materials", "cap":"mid", "aliases":["nuvoco", "nuvoco vistas"]},
    # ── Chemicals (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"AARTIIND", "name":"Aarti Industries Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["aarti", "aartiind"]},
    {"symbol":"ANURAS", "name":"Anupam Rasayan India Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["anupam", "anupam rasayan", "anuras"]},
    {"symbol":"BAYERCROP", "name":"Bayer Cropscience Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["bayer", "bayer cropscience", "bayercrop"]},
    {"symbol":"CHAMBLFERT", "name":"Chambal Fertilizers & Chemicals Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["chambal", "chambal fertilizers", "chamblfert"]},
    {"symbol":"DEEPAKFERT", "name":"Deepak Fertilisers & Petrochemicals Corp. Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["deepak", "deepak fertilisers", "deepakfert"]},
    {"symbol":"FACT", "name":"Fertilisers and Chemicals Travancore Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["fact", "fertilisers", "fertilisers travancore"]},
    {"symbol":"FLUOROCHEM", "name":"Gujarat Fluorochemicals Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["fluorochem", "gujarat fluorochemicals"]},
    {"symbol":"HSCL", "name":"Himadri Speciality Chemical Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["himadri", "himadri speciality", "hscl"]},
    {"symbol":"JUBLINGREA", "name":"Jubilant Ingrevia Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["jubilant ingrevia", "jublingrea"]},
    {"symbol":"LINDEINDIA", "name":"Linde India Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["linde", "lindeindia"]},
    {"symbol":"PARADEEP", "name":"Paradeep Phosphates Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["paradeep", "paradeep phosphates"]},
    {"symbol":"PCBL", "name":"PCBL Chemical Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["pcbl"]},
    {"symbol":"SPLPETRO", "name":"Supreme Petrochem Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["splpetro", "supreme", "supreme petrochem"]},
    {"symbol":"SUMICHEM", "name":"Sumitomo Chemical India Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["sumichem", "sumitomo"]},
    {"symbol":"SWANCORP", "name":"Swan Corp Ltd", "sector":"Chemicals", "industry":"Chemicals", "cap":"mid", "aliases":["swan", "swancorp"]},
    # ── Consumer (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"ABLBL", "name":"Aditya Birla Lifestyle Brands Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["ablbl"]},
    {"symbol":"BERGEPAINT", "name":"Berger Paints India Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["bergepaint", "berger paints", "berger"]},
    {"symbol":"BLS", "name":"BLS International Services Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["bls"]},
    {"symbol":"BLUESTARCO", "name":"Blue Star Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["blue star", "bluestarco"]},
    {"symbol":"CARTRADE", "name":"Cartrade Tech Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["cartrade", "cartrade tech"]},
    {"symbol":"CHALET", "name":"Chalet Hotels Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["chalet"]},
    {"symbol":"DEVYANI", "name":"Devyani International Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["devyani"]},
    {"symbol":"EIHOTEL", "name":"EIH Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["eih", "eihotel"]},
    # ETERNAL duplicate removed here (2026-08-09) — a second, less complete
    # entry already existed further up the list (found while renaming the
    # stale ZOMATO entry to ETERNAL; someone had partially fixed this
    # before but left the old ZOMATO row in place). Kept the richer one
    # (real "zomato"/"blinkit" aliases, more specific "Food Delivery"
    # industry) over this one.
    {"symbol":"FIRSTCRY", "name":"Brainbees Solutions Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["brainbees", "firstcry"]},
    {"symbol":"INDHOTEL", "name":"Indian Hotels Co. Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"large", "aliases":["indhotel"]},
    {"symbol":"ITCHOTELS", "name":"ITC Hotels Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["itchotels"]},
    {"symbol":"JSWDULUX", "name":"JSW Dulux Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["jsw dulux", "jswdulux"]},
    {"symbol":"KAJARIACER", "name":"Kajaria Ceramics Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["kajaria", "kajaria ceramics", "kajariacer"]},
    {"symbol":"LEMONTREE", "name":"Lemon Tree Hotels Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["lemon", "lemon tree", "lemontree"]},
    {"symbol":"LENSKART", "name":"Lenskart Solutions Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["lenskart"]},
    {"symbol":"LGEINDIA", "name":"LG Electronics India Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["lgeindia"]},
    {"symbol":"MEESHO", "name":"Meesho Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["meesho"]},
    {"symbol":"PGEL", "name":"PG Electroplast Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["electroplast", "pgel"]},
    {"symbol":"PWL", "name":"Physicswallah Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["physicswallah", "pwl"]},
    {"symbol":"SWIGGY", "name":"Swiggy Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"large", "aliases":["swiggy"]},
    {"symbol":"TBOTEK", "name":"TBO Tek Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["tbo", "tbo tek", "tbotek"]},
    {"symbol":"THELEELA", "name":"Leela Palaces Hotels & Resorts Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["leela", "leela palaces", "theleela"]},
    {"symbol":"TRAVELFOOD", "name":"Travel Food Services Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["travel", "travelfood"]},
    {"symbol":"URBANCO", "name":"Urban Company Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["urbanco"]},
    {"symbol":"VMM", "name":"Vishal Mega Mart Ltd", "sector":"Consumer", "industry":"Consumer Services", "cap":"mid", "aliases":["vishal", "vishal mega", "vmm"]},
    {"symbol":"WHIRLPOOL", "name":"Whirlpool of India Ltd", "sector":"Consumer", "industry":"Consumer Durables", "cap":"mid", "aliases":["whirlpool"]},
    # ── Defence (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"DATAPATTNS", "name":"Data Patterns (India) Ltd", "sector":"Defence", "industry":"Capital Goods", "cap":"mid", "aliases":["data", "data patterns", "datapattns"]},
    {"symbol":"ZENTEC", "name":"Zen Technologies Ltd", "sector":"Defence", "industry":"Capital Goods", "cap":"mid", "aliases":["zen", "zentec"]},
    # ── Energy (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"AEGISLOG", "name":"Aegis Logistics Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["aegislog"]},
    {"symbol":"AEGISVOPAK", "name":"Aegis Vopak Terminals Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["aegis vopak", "aegisvopak"]},
    {"symbol":"ATGL", "name":"Adani Total Gas Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["adani total", "atgl"]},
    {"symbol":"CASTROLIND", "name":"Castrol India Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["castrol", "castrolind"]},
    {"symbol":"CHENNPETRO", "name":"Chennai Petroleum Corporation Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["chennai", "chennai petroleum", "chennpetro"]},
    {"symbol":"HINDPETRO", "name":"Hindustan Petroleum Corporation Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"large", "aliases":["hindpetro", "hindustan petroleum", "hpcl"]},
    {"symbol":"MRPL", "name":"Mangalore Refinery & Petrochemicals Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["mangalore", "mrpl"]},
    {"symbol":"OIL", "name":"Oil India Ltd", "sector":"Energy", "industry":"Oil Gas & Consumable Fuels", "cap":"mid", "aliases":["oil"]},
    # ── FMCG (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"ABDL", "name":"Allied Blenders and Distillers Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["abdl", "allied", "allied blenders"]},
    {"symbol":"AWL", "name":"AWL Agri Business Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["awl", "awl business"]},
    {"symbol":"BALRAMCHIN", "name":"Balrampur Chini Mills Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["balramchin", "balrampur", "balrampur chini"]},
    {"symbol":"BBTC", "name":"Bombay Burmah Trading Corporation Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["bbtc", "bombay", "bombay burmah"]},
    {"symbol":"CCL", "name":"CCL Products (I) Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["ccl"]},
    {"symbol":"DOMS", "name":"DOMS Industries Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["doms"]},
    {"symbol":"GILLETTE", "name":"Gillette India Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["gillette"]},
    {"symbol":"GODFRYPHLP", "name":"Godfrey Phillips India Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["godfrey", "godfrey phillips", "godfryphlp"]},
    {"symbol":"HONASA", "name":"Honasa Consumer Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["honasa"]},
    {"symbol":"LTFOODS", "name":"LT Foods Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["ltfoods"]},
    {"symbol":"PATANJALI", "name":"Patanjali Foods Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["patanjali"]},
    {"symbol":"RADICO", "name":"Radico Khaitan Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["radico", "radico khaitan"]},
    {"symbol":"UBL", "name":"United Breweries Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["breweries", "ubl"]},
    {"symbol":"UNITDSPR", "name":"United Spirits Ltd", "sector":"FMCG", "industry":"Fast Moving Consumer Goods", "cap":"large", "aliases":["spirits", "unitdspr"]},
    # ── Finance (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"AADHARHFC", "name":"Aadhar Housing Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["aadhar", "aadharhfc"]},
    {"symbol":"AAVAS", "name":"Aavas Financiers Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["aavas", "aavas financiers"]},
    {"symbol":"ABCAPITAL", "name":"Aditya Birla Capital Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["abcapital"]},
    {"symbol":"ABSLAMC", "name":"Aditya Birla Sun Life AMC Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["abslamc"]},
    {"symbol":"AIIL", "name":"Authum Investment & Infrastructure Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["aiil", "authum"]},
    {"symbol":"ANANDRATHI", "name":"Anand Rathi Wealth Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["anand", "anand rathi", "anandrathi"]},
    {"symbol":"APTUS", "name":"Aptus Value Housing Finance India Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["aptus", "aptus value"]},
    {"symbol":"BAJAJHFL", "name":"Bajaj Housing Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["bajajhfl"]},
    {"symbol":"BAJAJHLDNG", "name":"Bajaj Holdings & Investment Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["bajajhldng"]},
    {"symbol":"CANFINHOME", "name":"Can Fin Homes Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["can", "can fin", "canfinhome"]},
    {"symbol":"CGCL", "name":"Capri Global Capital Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["capri", "cgcl"]},
    {"symbol":"CHOICEIN", "name":"Choice International Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["choice", "choicein"]},
    {"symbol":"CHOLAHLDNG", "name":"Cholamandalam Financial Holdings Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"large", "aliases":["cholahldng"]},
    {"symbol":"CREDITACC", "name":"CreditAccess Grameen Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["creditacc", "creditaccess", "creditaccess grameen"]},
    {"symbol":"CRISIL", "name":"CRISIL Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["crisil"]},
    {"symbol":"FIVESTAR", "name":"Five-Star Business Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["five-star", "five-star business", "fivestar"]},
    {"symbol":"GROWW", "name":"Billionbrains Garage Ventures Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["billionbrains", "billionbrains garage", "groww"]},
    {"symbol":"HDBFS", "name":"HDB Financial Services Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["hdb", "hdbfs"]},
    {"symbol":"HDFCAMC", "name":"HDFC Asset Management Company Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["hdfcamc"]},
    {"symbol":"HOMEFIRST", "name":"Home First Finance Company India Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["home", "home first", "homefirst"]},
    {"symbol":"HUDCO", "name":"Housing & Urban Development Corporation Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["hudco", "urban development"]},
    {"symbol":"ICICIAMC", "name":"ICICI Prudential Asset Management Company Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"large", "aliases":["iciciamc"]},
    {"symbol":"IFCI", "name":"IFCI Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["ifci"]},
    {"symbol":"JIOFIN", "name":"Jio Financial Services Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"large", "aliases":["jio", "jiofin"]},
    {"symbol":"JMFINANCIL", "name":"JM Financial Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["jmfinancil"]},
    {"symbol":"LICHSGFIN", "name":"LIC Housing Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["lichsgfin"]},
    {"symbol":"LTF", "name":"L&T Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["ltf"]},
    {"symbol":"MFSL", "name":"Max Financial Services Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["max", "mfsl"]},
    {"symbol":"NAM-INDIA", "name":"Nippon Life India Asset Management Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["nam-india", "nippon life", "nippon amc"]},
    {"symbol":"NUVAMA", "name":"Nuvama Wealth Management Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["nuvama"]},
    {"symbol":"PINELABS", "name":"Pine Labs Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["pine", "pine labs", "pinelabs"]},
    {"symbol":"PIRAMALFIN", "name":"Piramal Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["piramalfin"]},
    {"symbol":"POONAWALLA", "name":"Poonawalla Fincorp Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["poonawalla", "poonawalla fincorp"]},
    {"symbol":"SAMMAANCAP", "name":"Sammaan Capital Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["sammaan", "sammaancap"]},
    {"symbol":"SBFC", "name":"SBFC Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["sbfc"]},
    {"symbol":"SBICARD", "name":"SBI Cards and Payment Services Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"large", "aliases":["sbi cards", "sbicard"]},
    {"symbol":"SUNDARMFIN", "name":"Sundaram Finance Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["sundaram", "sundarmfin"]},
    {"symbol":"TATACAP", "name":"Tata Capital Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["tatacap"]},
    {"symbol":"TATAINVEST", "name":"Tata Investment Corporation Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["tatainvest"]},
    {"symbol":"UTIAMC", "name":"UTI Asset Management Company Ltd", "sector":"Finance", "industry":"Financial Services", "cap":"mid", "aliases":["uti", "utiamc"]},
    # ── Healthcare (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"ACUTAAS", "name":"Acutaas Chemicals Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["acutaas"]},
    {"symbol":"ASTERDM", "name":"Aster DM Healthcare Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["aster", "asterdm"]},
    {"symbol":"BLUEJET", "name":"Blue Jet Healthcare Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["blue jet", "bluejet"]},
    {"symbol":"CONCORDBIO", "name":"Concord Biotech Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["concord", "concord biotech", "concordbio"]},
    {"symbol":"INDGN", "name":"Indegene Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["indegene", "indgn"]},
    {"symbol":"JUBLPHARMA", "name":"Jubilant Pharmova Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["jubilant pharmova", "jublpharma"]},
    {"symbol":"LAURUSLABS", "name":"Laurus Labs Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["laurus", "laurus labs", "lauruslabs"]},
    {"symbol":"POLYMED", "name":"Poly Medicure Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["poly", "poly medicure", "polymed"]},
    {"symbol":"RAINBOW", "name":"Rainbow Childrens Medicare Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["rainbow", "rainbow childrens"]},
    {"symbol":"SYNGENE", "name":"Syngene International Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["syngene"]},
    {"symbol":"VIJAYA", "name":"Vijaya Diagnostic Centre Ltd", "sector":"Healthcare", "industry":"Healthcare", "cap":"mid", "aliases":["vijaya", "vijaya diagnostic"]},
    # ── Infrastructure (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"3MINDIA", "name":"3M India Ltd", "sector":"Infrastructure", "industry":"Diversified", "cap":"mid", "aliases":["3mindia"]},
    {"symbol":"ACE", "name":"Action Construction Equipment Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["ace", "action"]},
    {"symbol":"AFCONS", "name":"Afcons Infrastructure Ltd", "sector":"Infrastructure", "industry":"Construction", "cap":"mid", "aliases":["afcons"]},
    {"symbol":"AIAENG", "name":"AIA Engineering Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["aia", "aiaeng"]},
    {"symbol":"APARINDS", "name":"Apar Industries Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["apar", "aparinds"]},
    {"symbol":"CARBORUNIV", "name":"Carborundum Universal Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["carborundum", "carboruniv"]},
    {"symbol":"CEMPRO", "name":"Cemindia Projects Ltd", "sector":"Infrastructure", "industry":"Construction", "cap":"mid", "aliases":["cemindia", "cemindia projects", "cempro"]},
    {"symbol":"CPPLUS", "name":"Aditya Infotech Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["aditya infotech", "cpplus"]},
    {"symbol":"DCMSHRIRAM", "name":"DCM Shriram Ltd", "sector":"Infrastructure", "industry":"Diversified", "cap":"mid", "aliases":["dcm", "dcm shriram", "dcmshriram"]},
    {"symbol":"ECLERX", "name":"eClerx Services Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["eclerx"]},
    {"symbol":"ELECON", "name":"Elecon Engineering Co. Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["elecon"]},
    {"symbol":"ELGIEQUIP", "name":"Elgi Equipments Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["elgi", "elgiequip"]},
    {"symbol":"EMMVEE", "name":"Emmvee Photovoltaic Power Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["emmvee", "emmvee photovoltaic"]},
    {"symbol":"ENGINERSIN", "name":"Engineers India Ltd", "sector":"Infrastructure", "industry":"Construction", "cap":"mid", "aliases":["enginersin"]},
    {"symbol":"ENRIN", "name":"Siemens Energy India Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["enrin"]},
    {"symbol":"FINCABLES", "name":"Finolex Cables Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["fincables", "finolex"]},
    {"symbol":"FSL", "name":"Firstsource Solutions Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["firstsource", "fsl"]},
    {"symbol":"GALLANTT", "name":"Gallantt Ispat Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["gallantt", "gallantt ispat"]},
    {"symbol":"GESHIP", "name":"Great Eastern Shipping Co. Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["geship", "great", "great eastern"]},
    {"symbol":"GODREJIND", "name":"Godrej Industries Ltd", "sector":"Infrastructure", "industry":"Diversified", "cap":"mid", "aliases":["godrejind"]},
    {"symbol":"GPIL", "name":"Godawari Power & Ispat Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["godawari", "godawari ispat", "gpil"]},
    {"symbol":"GRAPHITE", "name":"Graphite India Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["graphite"]},
    {"symbol":"GVT&D", "name":"GE Vernova T&D India Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["gvt&d", "vernova"]},
    {"symbol":"HBLENGINE", "name":"HBL Engineering Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["hbl", "hblengine"]},
    {"symbol":"HEG", "name":"H.E.G. Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["heg"]},
    {"symbol":"IGIL", "name":"International Gemological Institute Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["gemological", "gemological institute", "igil"]},
    {"symbol":"INOXWIND", "name":"Inox Wind Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["inoxwind"]},
    {"symbol":"JINDALSAW", "name":"Jindal Saw Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["jindal saw", "jindalsaw"]},
    {"symbol":"JSWINFRA", "name":"JSW Infrastructure Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["jswinfra"]},
    {"symbol":"JWL", "name":"Jupiter Wagons Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["jupiter", "jupiter wagons", "jwl"]},
    {"symbol":"JYOTICNC", "name":"Jyoti CNC Automation Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["jyoti", "jyoti cnc", "jyoticnc"]},
    {"symbol":"KEC", "name":"Kec International Ltd", "sector":"Infrastructure", "industry":"Construction", "cap":"mid", "aliases":["kec"]},
    {"symbol":"KIRLOSENG", "name":"Kirloskar Oil Eng Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["kirloseng", "kirloskar", "kirloskar oil"]},
    {"symbol":"KPIL", "name":"Kalpataru Projects International Ltd", "sector":"Infrastructure", "industry":"Construction", "cap":"mid", "aliases":["kalpataru", "kalpataru projects", "kpil"]},
    {"symbol":"MMTC", "name":"MMTC Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["mmtc"]},
    {"symbol":"POWERINDIA", "name":"Hitachi Energy India Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["hitachi", "powerindia"]},
    {"symbol":"PREMIERENE", "name":"Premier Energies Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["premier", "premierene"]},
    {"symbol":"PTCIL", "name":"PTC Industries Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["ptc", "ptcil"]},
    {"symbol":"REDINGTON", "name":"Redington Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["redington"]},
    {"symbol":"RHIM", "name":"RHI MAGNESITA INDIA LTD.", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["rhi", "rhi magnesita", "rhim"]},
    {"symbol":"RRKABEL", "name":"R R Kabel Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["kabel", "rrkabel"]},
    {"symbol":"SCHNEIDER", "name":"Schneider Electric Infrastructure Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["schneider", "schneider electric"]},
    {"symbol":"SCI", "name":"Shipping Corporation of India Ltd", "sector":"Infrastructure", "industry":"Services", "cap":"mid", "aliases":["sci"]},
    {"symbol":"SHYAMMETL", "name":"Shyam Metalics and Energy Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["shyam", "shyam metalics", "shyammetl"]},
    {"symbol":"TIMKEN", "name":"Timken India Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["timken"]},
    {"symbol":"TITAGARH", "name":"Titagarh Rail Systems Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["titagarh", "titagarh rail"]},
    {"symbol":"TRITURBINE", "name":"Triveni Turbine Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["triturbine", "triveni", "triveni turbine"]},
    {"symbol":"USHAMART", "name":"Usha Martin Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["usha", "usha martin", "ushamart"]},
    {"symbol":"WAAREEENER", "name":"Waaree Energies Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["waaree", "waareeener"]},
    {"symbol":"WELCORP", "name":"Welspun Corp Ltd", "sector":"Infrastructure", "industry":"Capital Goods", "cap":"mid", "aliases":["welcorp"]},
    # ── Insurance (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"CANHLIFE", "name":"Canara HSBC Life Insurance Company Ltd", "sector":"Insurance", "industry":"Financial Services", "cap":"mid", "aliases":["canara hsbc", "canhlife"]},
    {"symbol":"GICRE", "name":"General Insurance Corporation of India", "sector":"Insurance", "industry":"Financial Services", "cap":"mid", "aliases":["gicre"]},
    {"symbol":"GODIGIT", "name":"Go Digit General Insurance Ltd", "sector":"Insurance", "industry":"Financial Services", "cap":"mid", "aliases":["digit", "godigit"]},
    {"symbol":"NIVABUPA", "name":"Niva Bupa Health Insurance Company Ltd", "sector":"Insurance", "industry":"Financial Services", "cap":"mid", "aliases":["niva", "niva bupa", "nivabupa"]},
    # ── Media (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"SAREGAMA", "name":"Saregama India Ltd", "sector":"Media", "industry":"Media Entertainment & Publication", "cap":"mid", "aliases":["saregama"]},
    # ── Metals (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"GMDCLTD", "name":"Gujarat Mineral Development Corporation Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["gmdcltd", "gujarat mineral"]},
    {"symbol":"GRAVITA", "name":"Gravita India Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["gravita"]},
    {"symbol":"HINDCOPPER", "name":"Hindustan Copper Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["hindcopper", "hindustan copper"]},
    {"symbol":"JAINREC", "name":"Jain Resource Recycling Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["jain", "jain resource", "jainrec"]},
    {"symbol":"JSL", "name":"Jindal Stainless Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["jindal stainless", "jsl"]},
    {"symbol":"LLOYDSME", "name":"Lloyds Metals And Energy Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["lloyds", "lloydsme"]},
    {"symbol":"NSLNISP", "name":"NMDC Steel Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["nslnisp"]},
    {"symbol":"SARDAEN", "name":"Sarda Energy and Minerals Ltd", "sector":"Metals", "industry":"Metals & Mining", "cap":"mid", "aliases":["sarda", "sardaen"]},
    # ── Pharmaceuticals (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"AJANTPHARM", "name":"Ajanta Pharmaceuticals Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["ajanta", "ajantpharm"]},
    {"symbol":"ANTHEM", "name":"Anthem Biosciences Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["anthem", "anthem biosciences"]},
    {"symbol":"CAPLIPOINT", "name":"Caplin Point Laboratories Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["caplin", "caplin point", "caplipoint"]},
    {"symbol":"COHANCE", "name":"Cohance Lifesciences Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["cohance", "cohance lifesciences"]},
    {"symbol":"EMCURE", "name":"Emcure Pharmaceuticals Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["emcure"]},
    {"symbol":"ERIS", "name":"Eris Lifesciences Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["eris", "eris lifesciences"]},
    {"symbol":"GLAND", "name":"Gland Pharma Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["gland"]},
    {"symbol":"GLAXO", "name":"Glaxosmithkline Pharmaceuticals Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["glaxo", "glaxosmithkline"]},
    {"symbol":"MANKIND", "name":"Mankind Pharma Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["mankind"]},
    {"symbol":"NEULANDLAB", "name":"Neuland Laboratories Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["neuland", "neuland laboratories", "neulandlab"]},
    {"symbol":"ONESOURCE", "name":"Onesource Specialty Pharma Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["onesource", "onesource specialty"]},
    {"symbol":"PFIZER", "name":"Pfizer Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["pfizer"]},
    {"symbol":"PPLPHARMA", "name":"Piramal Pharma Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["pplpharma"]},
    {"symbol":"SAILIFE", "name":"Sai Life Sciences Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["sai", "sai sciences", "sailife"]},
    {"symbol":"WOCKPHARMA", "name":"Wockhardt Ltd", "sector":"Pharmaceuticals", "industry":"Healthcare", "cap":"mid", "aliases":["wockhardt", "wockpharma"]},
    {"symbol":"ZYDUSWELL", "name":"Zydus Wellness Ltd", "sector":"Pharmaceuticals", "industry":"Fast Moving Consumer Goods", "cap":"mid", "aliases":["zydus wellness", "zyduswell"]},
    # ── Power (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"ACMESOLAR", "name":"ACME Solar Holdings Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["acme", "acmesolar"]},
    {"symbol":"ADANIENSOL", "name":"Adani Energy Solutions Ltd", "sector":"Power", "industry":"Power", "cap":"large", "aliases":["adaniensol"]},
    {"symbol":"JPPOWER", "name":"Jaiprakash Power Ventures Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["jaiprakash", "jaiprakash ventures", "jppower"]},
    {"symbol":"NAVA", "name":"Nava Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["nava"]},
    {"symbol":"NLCINDIA", "name":"NLC India Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["nlc", "nlcindia"]},
    {"symbol":"NTPCGREEN", "name":"NTPC Green Energy Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["ntpcgreen"]},
    {"symbol":"RPOWER", "name":"Reliance Power Ltd", "sector":"Power", "industry":"Power", "cap":"mid", "aliases":["rpower"]},
    # ── Real Estate (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"ABREL", "name":"Aditya Birla Real Estate Ltd", "sector":"Real Estate", "industry":"Realty", "cap":"mid", "aliases":["abrel"]},
    {"symbol":"ANANTRAJ", "name":"Anant Raj Ltd", "sector":"Real Estate", "industry":"Realty", "cap":"mid", "aliases":["anant", "anant raj", "anantraj"]},
    {"symbol":"LODHA", "name":"Lodha Developers Ltd", "sector":"Real Estate", "industry":"Realty", "cap":"mid", "aliases":["lodha", "lodha developers"]},
    {"symbol":"SIGNATURE", "name":"Signatureglobal (India) Ltd", "sector":"Real Estate", "industry":"Realty", "cap":"mid", "aliases":["signature", "signatureglobal"]},
    {"symbol":"SOBHA", "name":"Sobha Ltd", "sector":"Real Estate", "industry":"Realty", "cap":"mid", "aliases":["sobha"]},
    # ── Technology (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"AFFLE", "name":"Affle 3i Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["affle"]},
    {"symbol":"BSOFT", "name":"Birlasoft Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["bsoft"]},
    {"symbol":"HEXT", "name":"Hexaware Technologies Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["hexaware", "hext"]},
    {"symbol":"IKS", "name":"Inventurus Knowledge Solutions Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["iks", "inventurus", "inventurus knowledge"]},
    {"symbol":"INTELLECT", "name":"Intellect Design Arena Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["intellect", "intellect design"]},
    {"symbol":"LATENTVIEW", "name":"Latent View Analytics Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["latent", "latent view", "latentview"]},
    # LTM duplicate removed here (2026-08-09) — same pattern as the ETERNAL
    # duplicate above: a second, incomplete/wrong entry (name "LTM Ltd" not
    # the real "LTIMindtree Ltd", cap wrongly "mid" for a large IT major)
    # already existed further up, from a previous partial fix that never
    # removed the old LTIM row. Kept the more accurate one.
    {"symbol":"MAPMYINDIA", "name":"C.E. Info Systems Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["info", "mapmyindia"]},
    {"symbol":"NETWEB", "name":"Netweb Technologies India Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["netweb"]},
    {"symbol":"NEWGEN", "name":"Newgen Software Technologies Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["newgen", "newgen software"]},
    {"symbol":"SONATSOFTW", "name":"Sonata Software Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["sonata", "sonata software", "sonatsoftw"]},
    {"symbol":"TATATECH", "name":"Tata Technologies Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["tatatech"]},
    {"symbol":"ZENSARTECH", "name":"Zensar Technolgies Ltd", "sector":"Technology", "industry":"Information Technology", "cap":"mid", "aliases":["zensar", "zensar technolgies", "zensartech"]},
    # ── Telecom (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"BHARTIHEXA", "name":"Bharti Hexacom Ltd", "sector":"Telecom", "industry":"Telecommunication", "cap":"mid", "aliases":["bharti", "bharti hexacom", "bhartihexa"]},
    {"symbol":"HFCL", "name":"HFCL Ltd", "sector":"Telecom", "industry":"Telecommunication", "cap":"mid", "aliases":["hfcl"]},
    {"symbol":"ITI", "name":"ITI Ltd", "sector":"Telecom", "industry":"Telecommunication", "cap":"mid", "aliases":["iti"]},
    {"symbol":"TEJASNET", "name":"Tejas Networks Ltd", "sector":"Telecom", "industry":"Telecommunication", "cap":"mid", "aliases":["tejas", "tejas networks", "tejasnet"]},
    {"symbol":"TTML", "name":"Tata Teleservices (Maharashtra) Ltd", "sector":"Telecom", "industry":"Telecommunication", "cap":"mid", "aliases":["tata teleservices", "ttml"]},
    # ── Textiles (Nifty 500 expansion, 2026-07-26) ─────────────────
    {"symbol":"KPRMILL", "name":"K.P.R. Mill Ltd", "sector":"Textiles", "industry":"Textiles", "cap":"mid", "aliases":["kprmill", "mill"]},
    {"symbol":"TRIDENT", "name":"Trident Ltd", "sector":"Textiles", "industry":"Textiles", "cap":"mid", "aliases":["trident"]},
    {"symbol":"VTL", "name":"Vardhman Textiles Ltd", "sector":"Textiles", "industry":"Textiles", "cap":"mid", "aliases":["vardhman", "vtl"]},
    {"symbol":"WELSPUNLIV", "name":"Welspun Living Ltd", "sector":"Textiles", "industry":"Textiles", "cap":"mid", "aliases":["welspun living", "welspunliv"]},

    # ── ETFs / REITs / InvITs (2026-07-26) ────────────────────────────────────
    # Not Nifty 500 constituents (a different instrument class — units/ETF
    # shares, not equity) so not covered by the constituents merge above.
    # Each symbol individually verified against screener.in's own listing
    # page for that exact ticker (not carried over from a secondary-source
    # summary) given how easily REIT/InvIT tickers get confused with each
    # other across sources (e.g. Nexus Select Trust is genuinely "NXST",
    # not "NEXE" as one aggregator's summary claimed; Embassy REIT is
    # "EMBASSY", not "EMBA") — deliberately a short, individually-checked
    # list rather than a longer, less-certain one.
    {"symbol":"NIFTYBEES", "name":"Nippon India ETF Nifty 50 BeES", "sector":"ETF", "industry":"Index ETF", "cap":"large", "aliases":["nifty bees", "niftybees"]},
    {"symbol":"JUNIORBEES", "name":"Nippon India ETF Nifty Next 50 Junior BeES", "sector":"ETF", "industry":"Index ETF", "cap":"mid", "aliases":["junior bees", "juniorbees"]},
    {"symbol":"BANKBEES", "name":"Nippon India ETF Nifty Bank BeES", "sector":"ETF", "industry":"Sector ETF", "cap":"large", "aliases":["bank bees", "bankbees"]},
    {"symbol":"GOLDBEES", "name":"Nippon India ETF Gold BeES", "sector":"ETF", "industry":"Commodity ETF", "cap":"large", "aliases":["gold bees", "goldbees"]},
    {"symbol":"EMBASSY", "name":"Embassy Office Parks REIT", "sector":"REIT", "industry":"Office Real Estate Trust", "cap":"large", "aliases":["embassy reit", "embassy office"]},
    {"symbol":"MINDSPACE", "name":"Mindspace Business Parks REIT", "sector":"REIT", "industry":"Office Real Estate Trust", "cap":"large", "aliases":["mindspace reit", "mindspace business"]},
    {"symbol":"BIRET", "name":"Brookfield India Real Estate Trust", "sector":"REIT", "industry":"Office Real Estate Trust", "cap":"mid", "aliases":["brookfield reit", "brookfield india reit", "biret"]},
    {"symbol":"NXST", "name":"Nexus Select Trust", "sector":"REIT", "industry":"Retail Real Estate Trust", "cap":"mid", "aliases":["nexus select", "nxst"]},
    {"symbol":"INDIGRID", "name":"IndiGrid Infrastructure Trust", "sector":"InvIT", "industry":"Power Transmission InvIT", "cap":"mid", "aliases":["indigrid"]},
    {"symbol":"PGINVIT", "name":"Powergrid Infrastructure Investment Trust", "sector":"InvIT", "industry":"Power Transmission InvIT", "cap":"mid", "aliases":["powergrid invit", "pginvit"]},
    {"symbol":"IRBINVIT", "name":"IRB InvIT Fund", "sector":"InvIT", "industry":"Road Infrastructure InvIT", "cap":"mid", "aliases":["irb invit", "irbinvit"]},

    # ── Tier 1 universe expansion (2026-08-09) ──────────────────────────────
    # Sourced from NSE's own sectoral-index constituent files (niftyindices.
    # com/IndexConstituent/ind_{index}list.csv — official, live-verified,
    # real Industry field per company, not a guess or placeholder), the only
    # NSE-published source found with genuine industry classification beyond
    # this file's own hand-curated entries (see the universe-expansion
    # investigation's Step 2 finding: bhavcopy itself carries no sector/
    # industry column at all). 14 sectoral/thematic index files were pulled;
    # after dedup against the 505 companies already above, only 7 were
    # genuinely new — the other ~180 constituents across those 14 files were
    # already present, confirming the investigation's own finding that these
    # index files mostly overlap the already-curated large/mid-cap set
    # rather than extending meaningfully past it. This is real, but it means
    # Tier 1 as sourced lands at 512, not the ~700-900 originally estimated
    # — reaching that range would need additional NSE index files beyond the
    # 14 named in this task, a scope decision not made here (see report).
    # `industry` values are the CSV's own field verbatim, except PSB's
    # ("Financial Services" in the source file) mapped to "Banks" to match
    # every other bank entry's existing terminology in this file — real
    # company, real classification, just aligned to this file's own already-
    # established vocabulary rather than introducing a new one-off value.
    # `cap` tier is not present in the source file; assigned from each
    # company's real live market cap (yfinance, 2026-08-09) using the
    # existing entries' own tier boundaries as a reference — those
    # boundaries are visibly fuzzy/judgment-based in the pre-existing data
    # too (e.g. RBLBANK at ~Rs.60,000cr is tagged "small" while FEDERALBNK at
    # ~Rs.88,000cr is "mid"), so this is a best-effort placement consistent
    # with that existing convention, not a precise computed rule.
    {"symbol":"DBCORP",    "name":"D.B. Corp Ltd",                  "sector":"Media",          "industry":"Media Entertainment & Publication", "cap":"small", "aliases":["db corp","dainik bhaskar"]},
    {"symbol":"HATHWAY",   "name":"Hathway Cable & Datacom Ltd",    "sector":"Media",          "industry":"Media Entertainment & Publication", "cap":"small", "aliases":["hathway","hathway cable"]},
    {"symbol":"NETWORK18", "name":"Network18 Media & Investments Ltd", "sector":"Media",       "industry":"Media Entertainment & Publication", "cap":"small", "aliases":["network18","network 18"]},
    {"symbol":"NAZARA",    "name":"Nazara Technologies Ltd",        "sector":"Media",          "industry":"Media Entertainment & Publication", "cap":"mid",   "aliases":["nazara","nazara technologies"]},
    {"symbol":"TIPSMUSIC", "name":"Tips Music Ltd",                 "sector":"Media",          "industry":"Media Entertainment & Publication", "cap":"mid",   "aliases":["tips music","tips industries"]},
    {"symbol":"PFOCUS",    "name":"Prime Focus Ltd",                "sector":"Media",          "industry":"Media Entertainment & Publication", "cap":"mid",   "aliases":["prime focus"]},
    {"symbol":"PSB",       "name":"Punjab & Sind Bank",             "sector":"Banking",        "industry":"Banks",                  "cap":"mid",   "aliases":["punjab and sind bank","punjab & sind bank"]},
]

# ── Build in-memory search index ──────────────────────────────────────────────
# Done once at module-load time; O(n) search is instant for n ≤ 300.
_SEARCH_INDEX = [
    {
        **co,
        "_sym_l":  co["symbol"].lower(),
        "_name_l": co["name"].lower(),
        "_alias_l": [a.lower() for a in co.get("aliases", [])],
    }
    for co in _NSE_UNIVERSE
]

# Deduplicate (IRCON appears twice; remove exact symbol dups)
_seen: set[str] = set()
_DEDUPED: list[dict] = []
for _co in _SEARCH_INDEX:
    if _co["symbol"] not in _seen:
        _seen.add(_co["symbol"])
        _DEDUPED.append(_co)
_SEARCH_INDEX = _DEDUPED

_ALL_SECTORS = sorted({co["sector"] for co in _NSE_UNIVERSE})


# ── Search / filter helpers ───────────────────────────────────────────────────

def _score(co: dict, q: str) -> int:
    """Return a relevance score ≥ 1 if the company matches query q, 0 otherwise."""
    sym  = co["_sym_l"]
    name = co["_name_l"]
    als  = co["_alias_l"]

    if sym == q:              return 100
    if sym.startswith(q):     return 90
    if q in sym:              return 80
    if name.startswith(q):    return 70
    if q in name:             return 60
    if any(q in a for a in als): return 50
    return 0


def _filter_and_rank(q: str, sector: str, cap: str) -> list[dict]:
    results = []
    ql = q.strip().lower()
    for co in _SEARCH_INDEX:
        if sector and co["sector"].lower() != sector.lower():
            continue
        if cap and co["cap"].lower() != cap.lower():
            continue
        score = _score(co, ql) if ql else 1
        if score:
            results.append({**co, "_score": score})
    results.sort(key=lambda x: (-x["_score"], x["name"]))
    return results


# ── Live price fetching ───────────────────────────────────────────────────────

def _fetch_prices_sync(symbols: list[str]) -> dict[str, dict]:
    """
    Batch-fetch live prices from yfinance for a list of NSE symbols.
    Returns {symbol: {price, pct, positive}} for symbols that have data.
    """
    if not symbols:
        return {}
    try:
        import yfinance as yf
        import math as _math

        ns = [f"{s}.NS" for s in symbols]
        # period="2d" gives today + yesterday so we can compute change
        data = yf.download(ns, period="2d", interval="1d",
                           progress=False, auto_adjust=True, group_by="ticker", timeout=10)

        result: dict[str, dict] = {}
        for sym, ns_sym in zip(symbols, ns):
            try:
                # Handles both multi-ticker (MultiIndex) and single-ticker DataFrames
                df = (
                    data[ns_sym]
                    if ns_sym in data.columns.get_level_values(0)
                    else data.get(ns_sym)
                )
                if df is None or df.empty:
                    continue
                vals = df["Close"].dropna()
                if len(vals) == 0:
                    continue
                cur = float(vals.iloc[-1])
                if _math.isnan(cur) or _math.isinf(cur):
                    continue
                prev = float(vals.iloc[-2]) if len(vals) >= 2 else cur
                pct = round((cur / prev - 1) * 100, 2) if prev else 0.0
                result[sym] = {
                    "price":    f"{cur:,.2f}",
                    "pct":      pct,
                    "positive": cur >= prev,
                }
            except Exception:
                pass
        return result
    except Exception:
        return {}


async def _fetch_prices(symbols: list[str]) -> dict[str, dict]:
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        return await asyncio.wait_for(
            loop.run_in_executor(executor, _fetch_prices_sync, symbols),
            timeout=12.0,
        )
    except Exception:
        return {}


# ── API endpoints ─────────────────────────────────────────────────────────────

@router.get("/sectors")
async def list_sectors():
    """All distinct sectors in the company universe — for filter UI."""
    return {"sectors": _ALL_SECTORS}


@router.get("/search")
async def search_companies(
    q: str = Query("", description="Search term"),
    sector: str = Query("", description="Filter by sector"),
    cap: str = Query("", description="Filter by cap: large | mid | small"),
    limit: int = Query(20, ge=1, le=50),
):
    """
    Instant metadata-only search — no live prices.
    Fast enough for typeahead (<5ms).
    """
    results = _filter_and_rank(q, sector, cap)[:limit]
    return {
        "count": len(results),
        "companies": [
            {
                "symbol":   co["symbol"],
                "name":     co["name"],
                "sector":   co["sector"],
                "industry": co["industry"],
                "cap":      co["cap"],
            }
            for co in results
        ],
    }


@router.get("/")
async def list_companies(
    q:         str = Query("",    description="Search query"),
    sector:    str = Query("",    description="Filter by sector"),
    cap:       str = Query("",    description="Filter by cap: large | mid | small"),
    sort:      str = Query("name",description="Sort: name | cap | sector"),
    page:      int = Query(1,     ge=1),
    page_size: int = Query(24,    ge=6, le=60),
    live:      bool = Query(True, description="Fetch live prices for current page"),
):
    """
    Paginated company directory with optional live prices for the current page.

    Workflow:
      1. Filter the in-memory universe by q / sector / cap  (instant)
      2. Sort by name / cap / sector                         (instant)
      3. Paginate                                            (instant)
      4. Optionally fetch live prices for the page's symbols via yfinance
    """
    matches = _filter_and_rank(q, sector, cap)

    # Secondary sort (primary sort is always relevance score for queries,
    # then by the selected sort column)
    cap_order = {"large": 0, "mid": 1, "small": 2}
    if sort == "cap":
        matches.sort(key=lambda x: (cap_order.get(x["cap"], 3), x["name"]))
    elif sort == "sector":
        matches.sort(key=lambda x: (x["sector"], x["name"]))
    # "name" keeps existing alphabetical order from _filter_and_rank

    total = len(matches)
    total_pages = max(1, math.ceil(total / page_size))
    page = min(page, total_pages)
    start = (page - 1) * page_size
    page_items = matches[start: start + page_size]

    # Live prices for this page only
    prices: dict[str, dict] = {}
    if live and page_items:
        symbols = [co["symbol"] for co in page_items]
        prices = await _fetch_prices(symbols)

    companies = []
    for co in page_items:
        p = prices.get(co["symbol"], {})
        companies.append({
            "symbol":   co["symbol"],
            "name":     co["name"],
            "sector":   co["sector"],
            "industry": co["industry"],
            "cap":      co["cap"],
            "price":    p.get("price"),
            "pct":      p.get("pct"),
            "positive": p.get("positive"),
        })

    return {
        "total":       total,
        "page":        page,
        "page_size":   page_size,
        "total_pages": total_pages,
        "q":           q,
        "sector":      sector,
        "cap":         cap,
        "companies":   companies,
    }
