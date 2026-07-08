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
# ~260 NSE-listed companies with static metadata.
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
    {"symbol":"LTIM",       "name":"LTIMindtree Ltd",                "sector":"Technology",     "industry":"IT Services",           "cap":"large", "aliases":["ltimindtree","mindtree"]},
    {"symbol":"PERSISTENT", "name":"Persistent Systems Ltd",         "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["persistent"]},
    {"symbol":"MPHASIS",    "name":"Mphasis Ltd",                    "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["mphasis"]},
    {"symbol":"COFORGE",    "name":"Coforge Ltd",                    "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["coforge","niit tech"]},
    {"symbol":"KPITTECH",   "name":"KPIT Technologies Ltd",          "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["kpit"]},
    {"symbol":"LTTS",       "name":"L&T Technology Services Ltd",    "sector":"Technology",     "industry":"Engineering IT",        "cap":"mid",   "aliases":["l&t tech","ltts"]},
    {"symbol":"OFSS",       "name":"Oracle Financial Services Software","sector":"Technology",  "industry":"IT Software",           "cap":"large", "aliases":["oracle financial","ofss"]},
    {"symbol":"TATAELXSI",  "name":"Tata Elxsi Ltd",                 "sector":"Technology",     "industry":"Design Services",       "cap":"mid",   "aliases":["tata elxsi"]},
    {"symbol":"CYIENT",     "name":"Cyient Ltd",                     "sector":"Technology",     "industry":"Engineering IT",        "cap":"mid",   "aliases":["cyient"]},
    {"symbol":"BIRLASOFT",  "name":"Birlasoft Ltd",                  "sector":"Technology",     "industry":"IT Services",           "cap":"mid",   "aliases":["birlasoft"]},
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
    {"symbol":"CANARABANK", "name":"Canara Bank",                    "sector":"Banking",        "industry":"Banks",                 "cap":"large", "aliases":["canara bank"]},
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
    {"symbol":"GUJARATGAS", "name":"Gujarat Gas Ltd",                "sector":"Energy",         "industry":"City Gas Distribution", "cap":"mid",   "aliases":["gujarat gas"]},

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
    {"symbol":"GMRAIRPORT", "name":"GMR Airports Infrastructure Ltd","sector":"Infrastructure", "industry":"Airports",              "cap":"large", "aliases":["gmr airports","gmr"]},

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
    {"symbol":"JBCHEPHARM", "name":"JB Chemicals & Pharmaceuticals", "sector":"Pharmaceuticals","industry":"Pharmaceuticals",       "cap":"mid",   "aliases":["jb chemicals","jb chem"]},
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
    {"symbol":"ZOMATO",     "name":"Zomato Ltd",                     "sector":"Consumer",       "industry":"Food Delivery",         "cap":"large", "aliases":["zomato","blinkit"]},
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
    {"symbol":"MINDAIND",   "name":"UNO Minda Ltd",                  "sector":"Automotive",     "industry":"Auto Components",       "cap":"mid",   "aliases":["uno minda","minda industries"]},
    {"symbol":"EXIDEIND",   "name":"Exide Industries Ltd",           "sector":"Automotive",     "industry":"Batteries",             "cap":"mid",   "aliases":["exide"]},
    {"symbol":"AMARAJABAT", "name":"Amara Raja Energy & Mobility Ltd","sector":"Automotive",    "industry":"Batteries",             "cap":"mid",   "aliases":["amara raja","amaron"]},

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
    {"symbol":"VINATI",     "name":"Vinati Organics Ltd",            "sector":"Chemicals",      "industry":"Specialty Chemicals",   "cap":"mid",   "aliases":["vinati organics","vinati"]},
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
    {"symbol":"IRCON",      "name":"IRCON International Ltd",        "sector":"Infrastructure", "industry":"Railway Construction",  "cap":"mid",   "aliases":["ircon"]},
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
                           progress=False, auto_adjust=True, group_by="ticker")

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
