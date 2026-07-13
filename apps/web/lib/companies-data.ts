/**
 * NSE company universe — authoritative source for the companies directory.
 * Search and filter run in-memory (sub-ms). Live prices are fetched separately
 * from the Railway backend's /api/data/quotes endpoint.
 */

export interface Company {
  symbol: string;
  name: string;
  sector: string;
  industry: string;
  cap: "large" | "mid" | "small";
  aliases: string[];
}

export const NSE_UNIVERSE: Company[] = [
  // ── Technology / IT ────────────────────────────────────────────────────────
  { symbol: "TCS",        name: "Tata Consultancy Services Ltd",         sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["tcs", "tata consultancy"] },
  { symbol: "INFY",       name: "Infosys Ltd",                           sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["infosys"] },
  { symbol: "WIPRO",      name: "Wipro Ltd",                             sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["wipro"] },
  { symbol: "HCLTECH",    name: "HCL Technologies Ltd",                  sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["hcl", "hcltech"] },
  { symbol: "TECHM",      name: "Tech Mahindra Ltd",                     sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["tech mahindra"] },
  { symbol: "LTIM",       name: "LTIMindtree Ltd",                       sector: "Technology",     industry: "IT Services",            cap: "large", aliases: ["ltimindtree", "mindtree"] },
  { symbol: "PERSISTENT", name: "Persistent Systems Ltd",                sector: "Technology",     industry: "IT Services",            cap: "mid",   aliases: ["persistent"] },
  { symbol: "MPHASIS",    name: "Mphasis Ltd",                           sector: "Technology",     industry: "IT Services",            cap: "mid",   aliases: ["mphasis"] },
  { symbol: "COFORGE",    name: "Coforge Ltd",                           sector: "Technology",     industry: "IT Services",            cap: "mid",   aliases: ["coforge", "niit tech"] },
  { symbol: "KPITTECH",   name: "KPIT Technologies Ltd",                 sector: "Technology",     industry: "IT Services",            cap: "mid",   aliases: ["kpit"] },
  { symbol: "LTTS",       name: "L&T Technology Services Ltd",           sector: "Technology",     industry: "Engineering IT",         cap: "mid",   aliases: ["l&t tech", "ltts"] },
  { symbol: "OFSS",       name: "Oracle Financial Services Software",    sector: "Technology",     industry: "IT Software",            cap: "large", aliases: ["oracle financial", "ofss"] },
  { symbol: "TATAELXSI",  name: "Tata Elxsi Ltd",                        sector: "Technology",     industry: "Design Services",        cap: "mid",   aliases: ["tata elxsi"] },
  { symbol: "CYIENT",     name: "Cyient Ltd",                            sector: "Technology",     industry: "Engineering IT",         cap: "mid",   aliases: ["cyient"] },
  { symbol: "BIRLASOFT",  name: "Birlasoft Ltd",                         sector: "Technology",     industry: "IT Services",            cap: "mid",   aliases: ["birlasoft"] },
  { symbol: "NAUKRI",     name: "Info Edge India Ltd",                   sector: "Technology",     industry: "Internet Platform",      cap: "large", aliases: ["info edge", "naukri", "jeevansathi"] },
  { symbol: "INDIAMART",  name: "IndiaMart InterMesh Ltd",               sector: "Technology",     industry: "B2B Marketplace",        cap: "mid",   aliases: ["indiamart"] },
  { symbol: "HONAUT",     name: "Honeywell Automation India Ltd",        sector: "Technology",     industry: "Industrial Automation",  cap: "large", aliases: ["honeywell"] },
  { symbol: "DIXON",      name: "Dixon Technologies India Ltd",          sector: "Technology",     industry: "Electronics Mfg",        cap: "mid",   aliases: ["dixon"] },
  { symbol: "KAYNES",     name: "Kaynes Technology India Ltd",           sector: "Technology",     industry: "Electronics Mfg",        cap: "mid",   aliases: ["kaynes"] },
  { symbol: "POLICYBZR",  name: "PB Fintech Ltd",                        sector: "Technology",     industry: "Insurtech",              cap: "mid",   aliases: ["policybazaar", "pb fintech"] },
  { symbol: "RAILTEL",    name: "RailTel Corporation of India Ltd",      sector: "Technology",     industry: "Telecom Infrastructure", cap: "small", aliases: ["railtel"] },

  // ── Banking ─────────────────────────────────────────────────────────────────
  { symbol: "HDFCBANK",   name: "HDFC Bank Ltd",                         sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["hdfc bank", "hdfc"] },
  { symbol: "ICICIBANK",  name: "ICICI Bank Ltd",                        sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["icici bank", "icici"] },
  { symbol: "KOTAKBANK",  name: "Kotak Mahindra Bank Ltd",               sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["kotak bank", "kotak"] },
  { symbol: "SBIN",       name: "State Bank of India",                   sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["sbi", "state bank"] },
  { symbol: "AXISBANK",   name: "Axis Bank Ltd",                         sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["axis bank", "axis"] },
  { symbol: "INDUSINDBK", name: "IndusInd Bank Ltd",                     sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["indusind bank", "indusind"] },
  { symbol: "PNB",        name: "Punjab National Bank",                  sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["pnb", "punjab national"] },
  { symbol: "BANKBARODA", name: "Bank of Baroda",                        sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["bob", "bank of baroda"] },
  { symbol: "CANARABANK", name: "Canara Bank",                           sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["canara bank"] },
  { symbol: "UNIONBANK",  name: "Union Bank of India",                   sector: "Banking",        industry: "Banks",                  cap: "large", aliases: ["union bank"] },
  { symbol: "FEDERALBNK", name: "The Federal Bank Ltd",                  sector: "Banking",        industry: "Banks",                  cap: "mid",   aliases: ["federal bank"] },
  { symbol: "IDFCFIRSTB", name: "IDFC First Bank Ltd",                   sector: "Banking",        industry: "Banks",                  cap: "mid",   aliases: ["idfc first", "idfc"] },
  { symbol: "BANDHANBNK", name: "Bandhan Bank Ltd",                      sector: "Banking",        industry: "Banks",                  cap: "mid",   aliases: ["bandhan bank", "bandhan"] },
  { symbol: "RBLBANK",    name: "RBL Bank Ltd",                          sector: "Banking",        industry: "Banks",                  cap: "small", aliases: ["rbl bank", "rbl"] },

  // ── Finance / NBFC ──────────────────────────────────────────────────────────
  { symbol: "BAJFINANCE", name: "Bajaj Finance Ltd",                     sector: "Finance",        industry: "NBFC",                   cap: "large", aliases: ["bajaj finance", "bfl"] },
  { symbol: "BAJAJFINSV", name: "Bajaj Finserv Ltd",                     sector: "Finance",        industry: "Diversified Financial",  cap: "large", aliases: ["bajaj finserv"] },
  { symbol: "MUTHOOTFIN", name: "Muthoot Finance Ltd",                   sector: "Finance",        industry: "Gold Finance",           cap: "mid",   aliases: ["muthoot finance", "muthoot"] },
  { symbol: "MANAPPURAM", name: "Manappuram Finance Ltd",                sector: "Finance",        industry: "Gold Finance",           cap: "mid",   aliases: ["manappuram"] },
  { symbol: "CHOLAFIN",   name: "Cholamandalam Investment & Finance",    sector: "Finance",        industry: "NBFC",                   cap: "mid",   aliases: ["chola", "cholamandalam"] },
  { symbol: "SHRIRAMFIN", name: "Shriram Finance Ltd",                   sector: "Finance",        industry: "Vehicle Finance",        cap: "large", aliases: ["shriram finance", "shriram"] },
  { symbol: "HDFCLIFE",   name: "HDFC Life Insurance Company Ltd",       sector: "Finance",        industry: "Life Insurance",         cap: "large", aliases: ["hdfc life"] },
  { symbol: "SBILIFE",    name: "SBI Life Insurance Company Ltd",        sector: "Finance",        industry: "Life Insurance",         cap: "large", aliases: ["sbi life"] },
  { symbol: "LICI",       name: "Life Insurance Corporation of India",   sector: "Finance",        industry: "Life Insurance",         cap: "large", aliases: ["lic", "lici"] },
  { symbol: "ICICIPRULI", name: "ICICI Prudential Life Insurance Co",    sector: "Finance",        industry: "Life Insurance",         cap: "large", aliases: ["icici pru life", "icici prudential"] },
  { symbol: "ICICIGI",    name: "ICICI Lombard General Insurance",       sector: "Finance",        industry: "General Insurance",      cap: "large", aliases: ["icici lombard"] },
  { symbol: "PFC",        name: "Power Finance Corporation Ltd",         sector: "Finance",        industry: "Power Finance",          cap: "large", aliases: ["power finance", "pfc"] },
  { symbol: "RECLTD",     name: "REC Ltd",                               sector: "Finance",        industry: "Power Finance",          cap: "large", aliases: ["rec", "rural electrification"] },
  { symbol: "IRFC",       name: "Indian Railway Finance Corporation",    sector: "Finance",        industry: "Railway Finance",        cap: "large", aliases: ["irfc"] },
  { symbol: "IREDA",      name: "Indian Renewable Energy Dev Agency",    sector: "Finance",        industry: "Green Finance",          cap: "mid",   aliases: ["ireda"] },
  { symbol: "PNBHOUSING", name: "PNB Housing Finance Ltd",               sector: "Finance",        industry: "Housing Finance",        cap: "mid",   aliases: ["pnb housing"] },
  { symbol: "ANGELONE",   name: "Angel One Ltd",                         sector: "Finance",        industry: "Broking",                cap: "mid",   aliases: ["angel one", "angel broking"] },
  { symbol: "CDSL",       name: "Central Depository Services Ltd",       sector: "Finance",        industry: "Depositories",           cap: "mid",   aliases: ["cdsl"] },
  { symbol: "CAMS",       name: "Computer Age Management Services",      sector: "Finance",        industry: "Mutual Fund Services",   cap: "mid",   aliases: ["cams"] },
  { symbol: "360ONE",     name: "360 One WAM Ltd",                       sector: "Finance",        industry: "Wealth Management",      cap: "mid",   aliases: ["360 one", "iifl wealth"] },
  { symbol: "MCX",        name: "Multi Commodity Exchange of India",     sector: "Finance",        industry: "Commodity Exchange",     cap: "mid",   aliases: ["mcx"] },

  // ── Energy / Oil & Gas ──────────────────────────────────────────────────────
  { symbol: "RELIANCE",   name: "Reliance Industries Ltd",               sector: "Energy",         industry: "Oil & Gas Conglomerate", cap: "large", aliases: ["reliance", "ril"] },
  { symbol: "ONGC",       name: "Oil & Natural Gas Corporation",         sector: "Energy",         industry: "Oil & Gas E&P",          cap: "large", aliases: ["ongc"] },
  { symbol: "BPCL",       name: "Bharat Petroleum Corporation",          sector: "Energy",         industry: "Oil Refining",           cap: "large", aliases: ["bpcl", "bharat petroleum"] },
  { symbol: "IOC",        name: "Indian Oil Corporation Ltd",            sector: "Energy",         industry: "Oil Refining",           cap: "large", aliases: ["ioc", "indian oil"] },
  { symbol: "GAIL",       name: "GAIL India Ltd",                        sector: "Energy",         industry: "Natural Gas",            cap: "large", aliases: ["gail"] },
  { symbol: "PETRONET",   name: "Petronet LNG Ltd",                      sector: "Energy",         industry: "LNG",                    cap: "large", aliases: ["petronet"] },
  { symbol: "COALINDIA",  name: "Coal India Ltd",                        sector: "Energy",         industry: "Coal Mining",            cap: "large", aliases: ["coal india"] },
  { symbol: "IGL",        name: "Indraprastha Gas Ltd",                  sector: "Energy",         industry: "City Gas Distribution",  cap: "mid",   aliases: ["igl", "indraprastha gas"] },
  { symbol: "MGL",        name: "Mahanagar Gas Ltd",                     sector: "Energy",         industry: "City Gas Distribution",  cap: "mid",   aliases: ["mgl", "mahanagar gas"] },
  { symbol: "GUJARATGAS", name: "Gujarat Gas Ltd",                       sector: "Energy",         industry: "City Gas Distribution",  cap: "mid",   aliases: ["gujarat gas"] },

  // ── Power ────────────────────────────────────────────────────────────────────
  { symbol: "NTPC",       name: "NTPC Ltd",                              sector: "Power",          industry: "Power Generation",       cap: "large", aliases: ["ntpc", "national thermal"] },
  { symbol: "POWERGRID",  name: "Power Grid Corporation of India",       sector: "Power",          industry: "Power Transmission",     cap: "large", aliases: ["power grid", "pgcil"] },
  { symbol: "TATAPOWER",  name: "Tata Power Company Ltd",                sector: "Power",          industry: "Power Utilities",        cap: "large", aliases: ["tata power"] },
  { symbol: "ADANIGREEN", name: "Adani Green Energy Ltd",                sector: "Power",          industry: "Renewable Energy",       cap: "large", aliases: ["adani green"] },
  { symbol: "ADANIPOWER", name: "Adani Power Ltd",                       sector: "Power",          industry: "Power Generation",       cap: "large", aliases: ["adani power"] },
  { symbol: "NHPC",       name: "NHPC Ltd",                              sector: "Power",          industry: "Hydro Power",            cap: "large", aliases: ["nhpc"] },
  { symbol: "SJVN",       name: "SJVN Ltd",                              sector: "Power",          industry: "Hydro Power",            cap: "mid",   aliases: ["sjvn"] },
  { symbol: "TORNTPOWER", name: "Torrent Power Ltd",                     sector: "Power",          industry: "Power Utilities",        cap: "mid",   aliases: ["torrent power"] },
  { symbol: "SUZLON",     name: "Suzlon Energy Ltd",                     sector: "Power",          industry: "Wind Energy",            cap: "mid",   aliases: ["suzlon"] },
  { symbol: "CESC",       name: "CESC Ltd",                              sector: "Power",          industry: "Power Utilities",        cap: "mid",   aliases: ["cesc"] },
  { symbol: "JSWENERGY",  name: "JSW Energy Ltd",                        sector: "Power",          industry: "Power Generation",       cap: "large", aliases: ["jsw energy"] },

  // ── Infrastructure / Construction ────────────────────────────────────────────
  { symbol: "LT",         name: "Larsen & Toubro Ltd",                   sector: "Infrastructure", industry: "Construction EPC",       cap: "large", aliases: ["l&t", "larsen", "toubro", "lt"] },
  { symbol: "BHEL",       name: "Bharat Heavy Electricals Ltd",          sector: "Infrastructure", industry: "Heavy Engineering",      cap: "large", aliases: ["bhel", "bharat heavy"] },
  { symbol: "ADANIENT",   name: "Adani Enterprises Ltd",                 sector: "Infrastructure", industry: "Diversified",            cap: "large", aliases: ["adani enterprises", "adani"] },
  { symbol: "ADANIPORTS", name: "Adani Ports & SEZ Ltd",                 sector: "Infrastructure", industry: "Ports",                  cap: "large", aliases: ["adani ports", "apsez"] },
  { symbol: "SIEMENS",    name: "Siemens Ltd",                           sector: "Infrastructure", industry: "Electrical Equipment",   cap: "large", aliases: ["siemens"] },
  { symbol: "ABB",        name: "ABB India Ltd",                         sector: "Infrastructure", industry: "Power Transmission",     cap: "large", aliases: ["abb india", "abb"] },
  { symbol: "THERMAX",    name: "Thermax Ltd",                           sector: "Infrastructure", industry: "Industrial Boilers",     cap: "mid",   aliases: ["thermax"] },
  { symbol: "CUMMINSIND", name: "Cummins India Ltd",                     sector: "Infrastructure", industry: "Industrial Engines",     cap: "mid",   aliases: ["cummins india", "cummins"] },
  { symbol: "CGPOWER",    name: "CG Power and Industrial Solutions",     sector: "Infrastructure", industry: "Electrical Equipment",   cap: "mid",   aliases: ["cg power"] },
  { symbol: "POLYCAB",    name: "Polycab India Ltd",                     sector: "Infrastructure", industry: "Cables & Wires",         cap: "large", aliases: ["polycab"] },
  { symbol: "KEI",        name: "KEI Industries Ltd",                    sector: "Infrastructure", industry: "Cables & Wires",         cap: "mid",   aliases: ["kei industries"] },
  { symbol: "NBCC",       name: "NBCC India Ltd",                        sector: "Infrastructure", industry: "Govt Construction",      cap: "mid",   aliases: ["nbcc"] },
  { symbol: "NCC",        name: "NCC Ltd",                               sector: "Infrastructure", industry: "Construction",           cap: "small", aliases: ["ncc construction"] },
  { symbol: "ASTRAL",     name: "Astral Ltd",                            sector: "Infrastructure", industry: "PVC Pipes",              cap: "mid",   aliases: ["astral pipes", "astral"] },
  { symbol: "SUPREMEIND", name: "Supreme Industries Ltd",                sector: "Infrastructure", industry: "Plastic Products",       cap: "mid",   aliases: ["supreme industries"] },
  { symbol: "CONCOR",     name: "Container Corporation of India",        sector: "Infrastructure", industry: "Logistics",              cap: "large", aliases: ["concor", "container corporation"] },
  { symbol: "DELHIVERY",  name: "Delhivery Ltd",                         sector: "Infrastructure", industry: "Logistics",              cap: "mid",   aliases: ["delhivery"] },
  { symbol: "GMRAIRPORT", name: "GMR Airports Infrastructure Ltd",       sector: "Infrastructure", industry: "Airports",               cap: "large", aliases: ["gmr airports", "gmr"] },
  { symbol: "RITES",      name: "RITES Ltd",                             sector: "Infrastructure", industry: "Railway Consultancy",    cap: "mid",   aliases: ["rites"] },
  { symbol: "IRCON",      name: "IRCON International Ltd",               sector: "Infrastructure", industry: "Railway Construction",   cap: "mid",   aliases: ["ircon"] },

  // ── Defence & Aerospace ──────────────────────────────────────────────────────
  { symbol: "HAL",        name: "Hindustan Aeronautics Ltd",             sector: "Defence",        industry: "Aerospace & Defence",    cap: "large", aliases: ["hal", "hindustan aeronautics"] },
  { symbol: "BEL",        name: "Bharat Electronics Ltd",                sector: "Defence",        industry: "Defence Electronics",    cap: "large", aliases: ["bel", "bharat electronics"] },
  { symbol: "RVNL",       name: "Rail Vikas Nigam Ltd",                  sector: "Defence",        industry: "Railway Infrastructure", cap: "mid",   aliases: ["rvnl", "rail vikas"] },
  { symbol: "MAZDOCK",    name: "Mazagon Dock Shipbuilders Ltd",         sector: "Defence",        industry: "Shipbuilding",           cap: "mid",   aliases: ["mazagon dock", "mazagaon"] },
  { symbol: "GRSE",       name: "Garden Reach Shipbuilders & Engineers", sector: "Defence",        industry: "Shipbuilding",           cap: "mid",   aliases: ["grse", "garden reach"] },
  { symbol: "COCHINSHIP", name: "Cochin Shipyard Ltd",                   sector: "Defence",        industry: "Shipbuilding",           cap: "mid",   aliases: ["cochin shipyard"] },
  { symbol: "BEML",       name: "BEML Ltd",                              sector: "Defence",        industry: "Defence Manufacturing",  cap: "mid",   aliases: ["beml"] },

  // ── Pharmaceuticals ──────────────────────────────────────────────────────────
  { symbol: "SUNPHARMA",  name: "Sun Pharmaceutical Industries",         sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["sun pharma", "sun pharmaceutical"] },
  { symbol: "DRREDDY",    name: "Dr Reddy's Laboratories Ltd",           sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["dr reddys", "dr reddy"] },
  { symbol: "CIPLA",      name: "Cipla Ltd",                             sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["cipla"] },
  { symbol: "DIVISLAB",   name: "Divi's Laboratories Ltd",               sector: "Pharmaceuticals", industry: "APIs",                 cap: "large", aliases: ["divis labs", "divi"] },
  { symbol: "AUROPHARMA", name: "Aurobindo Pharma Ltd",                  sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["aurobindo"] },
  { symbol: "LUPIN",      name: "Lupin Ltd",                             sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["lupin"] },
  { symbol: "BIOCON",     name: "Biocon Ltd",                            sector: "Pharmaceuticals", industry: "Biotechnology",        cap: "large", aliases: ["biocon"] },
  { symbol: "TORNTPHARM", name: "Torrent Pharmaceuticals Ltd",           sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "mid",   aliases: ["torrent pharma", "torrent"] },
  { symbol: "ALKEM",      name: "Alkem Laboratories Ltd",                sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "mid",   aliases: ["alkem"] },
  { symbol: "GLENMARK",   name: "Glenmark Pharmaceuticals Ltd",          sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "mid",   aliases: ["glenmark"] },
  { symbol: "IPCALAB",    name: "IPCA Laboratories Ltd",                 sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "mid",   aliases: ["ipca"] },
  { symbol: "NATCOPHARM", name: "Natco Pharma Ltd",                      sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "mid",   aliases: ["natco pharma", "natco"] },
  { symbol: "ZYDUSLIFE",  name: "Zydus Lifesciences Ltd",                sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["zydus", "cadila"] },
  { symbol: "ABBOTINDIA", name: "Abbott India Ltd",                      sector: "Pharmaceuticals", industry: "Pharmaceuticals",      cap: "large", aliases: ["abbott india", "abbott"] },

  // ── Healthcare ───────────────────────────────────────────────────────────────
  { symbol: "APOLLOHOSP", name: "Apollo Hospitals Enterprise Ltd",       sector: "Healthcare",     industry: "Hospitals",              cap: "large", aliases: ["apollo hospitals", "apollo"] },
  { symbol: "FORTIS",     name: "Fortis Healthcare Ltd",                 sector: "Healthcare",     industry: "Hospitals",              cap: "mid",   aliases: ["fortis healthcare", "fortis"] },
  { symbol: "MAXHEALTH",  name: "Max Healthcare Institute Ltd",          sector: "Healthcare",     industry: "Hospitals",              cap: "mid",   aliases: ["max healthcare", "max hospital"] },
  { symbol: "LALPATHLAB", name: "Dr Lal PathLabs Ltd",                   sector: "Healthcare",     industry: "Diagnostics",            cap: "mid",   aliases: ["lal pathlabs", "dr lal"] },
  { symbol: "NH",         name: "Narayana Hrudayalaya Ltd",              sector: "Healthcare",     industry: "Hospitals",              cap: "mid",   aliases: ["narayana hrudayalaya", "nh"] },
  { symbol: "KIMS",       name: "Krishna Institute of Medical Sciences", sector: "Healthcare",     industry: "Hospitals",              cap: "mid",   aliases: ["kims"] },
  { symbol: "MEDANTA",    name: "Global Health Ltd",                     sector: "Healthcare",     industry: "Hospitals",              cap: "mid",   aliases: ["medanta", "global health"] },

  // ── FMCG ─────────────────────────────────────────────────────────────────────
  { symbol: "HINDUNILVR", name: "Hindustan Unilever Ltd",                sector: "FMCG",           industry: "Personal Products",      cap: "large", aliases: ["hul", "hindustan unilever", "hindustan lever"] },
  { symbol: "ITC",        name: "ITC Ltd",                               sector: "FMCG",           industry: "Tobacco & FMCG",         cap: "large", aliases: ["itc"] },
  { symbol: "NESTLEIND",  name: "Nestle India Ltd",                      sector: "FMCG",           industry: "Packaged Foods",         cap: "large", aliases: ["nestle india", "nestle", "maggi"] },
  { symbol: "BRITANNIA",  name: "Britannia Industries Ltd",              sector: "FMCG",           industry: "Biscuits & Bakery",      cap: "large", aliases: ["britannia"] },
  { symbol: "DABUR",      name: "Dabur India Ltd",                       sector: "FMCG",           industry: "Personal Care",          cap: "large", aliases: ["dabur"] },
  { symbol: "MARICO",     name: "Marico Ltd",                            sector: "FMCG",           industry: "Personal Care",          cap: "large", aliases: ["marico", "parachute"] },
  { symbol: "COLPAL",     name: "Colgate Palmolive India Ltd",           sector: "FMCG",           industry: "Oral Care",              cap: "large", aliases: ["colgate palmolive", "colgate"] },
  { symbol: "GODREJCP",   name: "Godrej Consumer Products Ltd",          sector: "FMCG",           industry: "Personal Products",      cap: "large", aliases: ["godrej consumer", "gcpl", "godrej"] },
  { symbol: "EMAMILTD",   name: "Emami Ltd",                             sector: "FMCG",           industry: "Personal Care",          cap: "mid",   aliases: ["emami"] },
  { symbol: "BIKAJI",     name: "Bikaji Foods International Ltd",        sector: "FMCG",           industry: "Packaged Snacks",        cap: "mid",   aliases: ["bikaji"] },

  // ── Consumer / Retail ────────────────────────────────────────────────────────
  { symbol: "TITAN",      name: "Titan Company Ltd",                     sector: "Consumer",       industry: "Jewellery & Watches",    cap: "large", aliases: ["titan", "tanishq", "fastrack"] },
  { symbol: "DMART",      name: "Avenue Supermarts Ltd",                 sector: "Consumer",       industry: "Supermarkets",           cap: "large", aliases: ["dmart", "avenue supermarts", "d-mart"] },
  { symbol: "ZOMATO",     name: "Zomato Ltd",                            sector: "Consumer",       industry: "Food Delivery",          cap: "large", aliases: ["zomato", "blinkit"] },
  { symbol: "NYKAA",      name: "FSN E-Commerce Ventures Ltd",           sector: "Consumer",       industry: "Beauty E-Commerce",      cap: "mid",   aliases: ["nykaa", "fsn"] },
  { symbol: "IRCTC",      name: "Indian Railway Catering & Tourism",     sector: "Consumer",       industry: "Rail Tourism",           cap: "large", aliases: ["irctc"] },
  { symbol: "TRENT",      name: "Trent Ltd",                             sector: "Consumer",       industry: "Fashion Retail",         cap: "mid",   aliases: ["trent", "westside", "zudio"] },
  { symbol: "HAVELLS",    name: "Havells India Ltd",                     sector: "Consumer",       industry: "Electrical Equipment",   cap: "mid",   aliases: ["havells"] },
  { symbol: "VOLTAS",     name: "Voltas Ltd",                            sector: "Consumer",       industry: "HVAC",                   cap: "mid",   aliases: ["voltas"] },
  { symbol: "KALYANKJIL", name: "Kalyan Jewellers India Ltd",            sector: "Consumer",       industry: "Jewellery",              cap: "mid",   aliases: ["kalyan jewellers", "kalyan"] },
  { symbol: "PAGEIND",    name: "Page Industries Ltd",                   sector: "Consumer",       industry: "Innerwear",              cap: "large", aliases: ["page industries", "jockey"] },
  { symbol: "JUBLFOOD",   name: "Jubilant FoodWorks Ltd",                sector: "Consumer",       industry: "QSR",                    cap: "mid",   aliases: ["jubilant foodworks", "dominos", "jubilant"] },
  { symbol: "BATAINDIA",  name: "Bata India Ltd",                        sector: "Consumer",       industry: "Footwear",               cap: "mid",   aliases: ["bata india", "bata"] },

  // ── Automotive ───────────────────────────────────────────────────────────────
  { symbol: "MARUTI",     name: "Maruti Suzuki India Ltd",               sector: "Automotive",     industry: "Passenger Vehicles",     cap: "large", aliases: ["maruti suzuki", "maruti", "suzuki"] },
  { symbol: "TATAMOTORS", name: "Tata Motors Ltd",                       sector: "Automotive",     industry: "Automobiles",            cap: "large", aliases: ["tata motors"] },
  { symbol: "M&M",        name: "Mahindra & Mahindra Ltd",               sector: "Automotive",     industry: "Automobiles",            cap: "large", aliases: ["mahindra", "m&m"] },
  { symbol: "BAJAJ-AUTO", name: "Bajaj Auto Ltd",                        sector: "Automotive",     industry: "Two-Wheelers",           cap: "large", aliases: ["bajaj auto", "bajaj"] },
  { symbol: "HEROMOTOCO", name: "Hero MotoCorp Ltd",                     sector: "Automotive",     industry: "Two-Wheelers",           cap: "large", aliases: ["hero motocorp", "hero honda", "hero"] },
  { symbol: "EICHERMOT",  name: "Eicher Motors Ltd",                     sector: "Automotive",     industry: "Two-Wheelers",           cap: "large", aliases: ["eicher motors", "royal enfield"] },
  { symbol: "TVSMOTOR",   name: "TVS Motor Company Ltd",                 sector: "Automotive",     industry: "Two-Wheelers",           cap: "large", aliases: ["tvs motor", "tvs"] },
  { symbol: "ESCORTS",    name: "Escorts Kubota Ltd",                    sector: "Automotive",     industry: "Tractors",               cap: "mid",   aliases: ["escorts kubota", "escorts"] },
  { symbol: "BOSCHLTD",   name: "Bosch Ltd",                             sector: "Automotive",     industry: "Auto Components",        cap: "large", aliases: ["bosch india", "bosch"] },
  { symbol: "MOTHERSON",  name: "Samvardhana Motherson Intl Ltd",        sector: "Automotive",     industry: "Auto Components",        cap: "mid",   aliases: ["motherson", "samvardhana"] },
  { symbol: "EXIDEIND",   name: "Exide Industries Ltd",                  sector: "Automotive",     industry: "Batteries",              cap: "mid",   aliases: ["exide"] },
  { symbol: "AMARAJABAT", name: "Amara Raja Energy & Mobility Ltd",      sector: "Automotive",     industry: "Batteries",              cap: "mid",   aliases: ["amara raja", "amaron"] },

  // ── Metals & Mining ──────────────────────────────────────────────────────────
  { symbol: "TATASTEEL",  name: "Tata Steel Ltd",                        sector: "Metals",         industry: "Steel",                  cap: "large", aliases: ["tata steel"] },
  { symbol: "JSWSTEEL",   name: "JSW Steel Ltd",                         sector: "Metals",         industry: "Steel",                  cap: "large", aliases: ["jsw steel", "jsw"] },
  { symbol: "HINDALCO",   name: "Hindalco Industries Ltd",               sector: "Metals",         industry: "Aluminium",              cap: "large", aliases: ["hindalco"] },
  { symbol: "VEDL",       name: "Vedanta Ltd",                           sector: "Metals",         industry: "Diversified Metals",     cap: "large", aliases: ["vedanta"] },
  { symbol: "SAIL",       name: "Steel Authority of India Ltd",          sector: "Metals",         industry: "Steel",                  cap: "large", aliases: ["sail", "steel authority"] },
  { symbol: "NMDC",       name: "NMDC Ltd",                              sector: "Metals",         industry: "Iron Ore",               cap: "large", aliases: ["nmdc"] },
  { symbol: "JINDALSTEL", name: "Jindal Steel & Power Ltd",              sector: "Metals",         industry: "Steel",                  cap: "mid",   aliases: ["jindal steel", "jspl"] },
  { symbol: "NATIONALUM", name: "National Aluminium Company Ltd",        sector: "Metals",         industry: "Aluminium",              cap: "mid",   aliases: ["nalco", "national aluminium"] },
  { symbol: "APLAPOLLO",  name: "APL Apollo Tubes Ltd",                  sector: "Metals",         industry: "Steel Tubes",            cap: "mid",   aliases: ["apl apollo", "apollo tubes"] },

  // ── Chemicals / Specialty ────────────────────────────────────────────────────
  { symbol: "PIDILITIND", name: "Pidilite Industries Ltd",               sector: "Chemicals",      industry: "Adhesives",              cap: "large", aliases: ["pidilite", "fevicol", "m-seal"] },
  { symbol: "ASIANPAINT", name: "Asian Paints Ltd",                      sector: "Chemicals",      industry: "Paints",                 cap: "large", aliases: ["asian paints"] },
  { symbol: "DEEPAKNTR",  name: "Deepak Nitrite Ltd",                    sector: "Chemicals",      industry: "Specialty Chemicals",    cap: "mid",   aliases: ["deepak nitrite"] },
  { symbol: "SRF",        name: "SRF Ltd",                               sector: "Chemicals",      industry: "Specialty Chemicals",    cap: "mid",   aliases: ["srf"] },
  { symbol: "UPL",        name: "UPL Ltd",                               sector: "Chemicals",      industry: "Agrochemicals",          cap: "large", aliases: ["upl", "united phosphorus"] },
  { symbol: "ATUL",       name: "Atul Ltd",                              sector: "Chemicals",      industry: "Specialty Chemicals",    cap: "mid",   aliases: ["atul ltd", "atul"] },
  { symbol: "NAVINFLUOR", name: "Navin Fluorine International Ltd",      sector: "Chemicals",      industry: "Fluorochemicals",        cap: "mid",   aliases: ["navin fluorine"] },
  { symbol: "TATACHEM",   name: "Tata Chemicals Ltd",                    sector: "Chemicals",      industry: "Chemicals",              cap: "mid",   aliases: ["tata chemicals"] },
  { symbol: "PIIND",      name: "PI Industries Ltd",                     sector: "Chemicals",      industry: "Agrochemicals",          cap: "mid",   aliases: ["pi industries"] },
  { symbol: "COROMANDEL", name: "Coromandel International Ltd",          sector: "Chemicals",      industry: "Fertilisers",            cap: "mid",   aliases: ["coromandel"] },

  // ── Cement ───────────────────────────────────────────────────────────────────
  { symbol: "ULTRACEMCO", name: "UltraTech Cement Ltd",                  sector: "Cement",         industry: "Cement",                 cap: "large", aliases: ["ultratech cement", "ultratech"] },
  { symbol: "GRASIM",     name: "Grasim Industries Ltd",                 sector: "Cement",         industry: "Cement & VSF",           cap: "large", aliases: ["grasim"] },
  { symbol: "SHREECEM",   name: "Shree Cement Ltd",                      sector: "Cement",         industry: "Cement",                 cap: "large", aliases: ["shree cement"] },
  { symbol: "DALBHARAT",  name: "Dalmia Bharat Ltd",                     sector: "Cement",         industry: "Cement",                 cap: "mid",   aliases: ["dalmia bharat", "dalmia"] },
  { symbol: "RAMCOCEM",   name: "The Ramco Cements Ltd",                 sector: "Cement",         industry: "Cement",                 cap: "mid",   aliases: ["ramco cement", "ramco"] },
  { symbol: "JKCEMENT",   name: "JK Cement Ltd",                         sector: "Cement",         industry: "Cement",                 cap: "mid",   aliases: ["jk cement"] },

  // ── Real Estate ──────────────────────────────────────────────────────────────
  { symbol: "DLF",        name: "DLF Ltd",                               sector: "Real Estate",    industry: "Real Estate Dev",        cap: "large", aliases: ["dlf"] },
  { symbol: "GODREJPROP", name: "Godrej Properties Ltd",                 sector: "Real Estate",    industry: "Real Estate Dev",        cap: "mid",   aliases: ["godrej properties", "godrej props"] },
  { symbol: "OBEROIRLTY", name: "Oberoi Realty Ltd",                     sector: "Real Estate",    industry: "Real Estate Dev",        cap: "mid",   aliases: ["oberoi realty", "oberoi"] },
  { symbol: "PRESTIGE",   name: "Prestige Estates Projects Ltd",         sector: "Real Estate",    industry: "Real Estate Dev",        cap: "mid",   aliases: ["prestige estates", "prestige"] },
  { symbol: "PHOENIXLTD", name: "Phoenix Mills Ltd",                     sector: "Real Estate",    industry: "Retail REITs",           cap: "mid",   aliases: ["phoenix mills", "phoenix"] },
  { symbol: "BRIGADE",    name: "Brigade Enterprises Ltd",               sector: "Real Estate",    industry: "Real Estate Dev",        cap: "mid",   aliases: ["brigade"] },

  // ── Telecom ──────────────────────────────────────────────────────────────────
  { symbol: "BHARTIARTL", name: "Bharti Airtel Ltd",                     sector: "Telecom",        industry: "Telecom Services",       cap: "large", aliases: ["bharti airtel", "airtel"] },
  { symbol: "INDUSTOWER", name: "Indus Towers Ltd",                      sector: "Telecom",        industry: "Telecom Infrastructure", cap: "large", aliases: ["indus towers"] },
  { symbol: "TATACOMM",   name: "Tata Communications Ltd",               sector: "Telecom",        industry: "Data Services",          cap: "mid",   aliases: ["tata communications", "tata comm"] },
];

// ── Derived data ────────────────────────────────────────────────────────────────

// Deduplicate by symbol (IRCON appears in both Infrastructure and Defence)
const _seen = new Set<string>();
export const COMPANIES = NSE_UNIVERSE.filter(c => {
  if (_seen.has(c.symbol)) return false;
  _seen.add(c.symbol);
  return true;
});

export const ALL_SECTORS: string[] = [...new Set(COMPANIES.map(c => c.sector))].sort();

// ── Search & filter ─────────────────────────────────────────────────────────────

function scoreCompany(co: Company, ql: string): number {
  const sym  = co.symbol.toLowerCase();
  const name = co.name.toLowerCase();
  if (sym === ql)           return 100;
  if (sym.startsWith(ql))   return 90;
  if (sym.includes(ql))     return 80;
  if (name.startsWith(ql))  return 70;
  if (name.includes(ql))    return 60;
  if (co.aliases.some(a => a.includes(ql))) return 50;
  return 0;
}

const CAP_ORDER: Record<string, number> = { large: 0, mid: 1, small: 2 };

export function filterAndRank(
  q: string,
  sector: string,
  cap: string,
  sort: string,
): Company[] {
  const ql = q.trim().toLowerCase();
  const results: { co: Company; s: number }[] = [];

  for (const co of COMPANIES) {
    if (sector && co.sector.toLowerCase() !== sector.toLowerCase()) continue;
    if (cap    && co.cap.toLowerCase()    !== cap.toLowerCase())    continue;
    const s = ql ? scoreCompany(co, ql) : 1;
    if (s) results.push({ co, s });
  }

  if (sort === "cap") {
    results.sort((a, b) =>
      (CAP_ORDER[a.co.cap] - CAP_ORDER[b.co.cap]) || a.co.name.localeCompare(b.co.name),
    );
  } else if (sort === "sector") {
    results.sort((a, b) =>
      a.co.sector.localeCompare(b.co.sector) || a.co.name.localeCompare(b.co.name),
    );
  } else {
    // Default: relevance desc, then alphabetical
    results.sort((a, b) => (b.s - a.s) || a.co.name.localeCompare(b.co.name));
  }

  return results.map(r => r.co);
}
