export const dashboardData = {
  highlights: [
    { label: "Nifty", value: "22,530.70", meta: "+1.08% Today" },
    { label: "Top Gainer", value: "BEL", meta: "+6.32%" },
    { label: "Top Loser", value: "TECHM", meta: "-2.35%" },
    { label: "Market Pulse", value: "Bullish", meta: "Event-driven momentum" }
  ],
  trendingEvents: [
    {
      id: "evt-1",
      category: "Government",
      title: "Government approves ₹75,000 Cr Railway Expansion Plan",
      summary: "Cabinet approves massive railway infrastructure expansion covering 3,000 km of new lines.",
      tags: ["Yesterday", "Government", "Railways", "Infra"],
      score: 92
    },
    {
      id: "evt-2",
      category: "RBI",
      title: "RBI maintains status quo, hints at future rate cuts",
      summary: "Monetary policy committee holds repo rate at 6.5% while signaling easing bias.",
      tags: ["2 days ago", "RBI", "Monetary Policy"],
      score: 88
    },
    {
      id: "evt-3",
      category: "Policy",
      title: "India-US discuss semiconductor partnership expansion",
      summary: "Strategic tech cooperation deal may unlock $10B in chip manufacturing investments.",
      tags: ["3 days ago", "Semiconductors", "Policy"],
      score: 75
    }
  ],
  aiTitle: "RBI policy optimism, strong earnings and FII inflows lift markets higher.",
  aiSummary:
    "Markets opened higher as RBI maintained status quo and hinted at future rate cuts. Infrastructure and capital goods stocks led the rally after government capex push."
};

export const eventsData = [
  {
    id: "evt-1",
    title: "RBI holds policy rate",
    summary: "Liquidity measures stay supportive while inflation remains under watch.",
    impact_score: 8.2,
    confidence: 0.91,
    sectors: ["Financials", "Consumer"],
    companies: ["HDFC Bank", "ICICI Bank"],
    timeline: [
      { label: "Announcement", value: "09:00 AM" },
      { label: "Market reaction", value: "10:30 AM" },
      { label: "Analyst notes", value: "12:15 PM" }
    ]
  },
  {
    id: "evt-2",
    title: "Energy firm announces capex plan",
    summary: "Large renewable investments may reshape power sector earnings over the next 12 months.",
    impact_score: 7.5,
    confidence: 0.84,
    sectors: ["Energy", "Infrastructure"],
    companies: ["NTPC", "Tata Power"],
    timeline: [
      { label: "Press release", value: "11:00 AM" },
      { label: "Analyst call", value: "01:00 PM" },
      { label: "Sector shift", value: "03:30 PM" }
    ]
  }
];

export const newsData = [
  {
    id: "news-1",
    headline: "Govt approves ₹75,000 Cr railway expansion plan",
    summary: "Cabinet approves massive railway infrastructure expansion covering 3,000 km of new lines.",
    source: "Economic Times",
    publishedAt: "2m ago",
    companies: ["IRCON", "RVNL", "L&T"],
    impact_score: 9.2,
    score: 92
  },
  {
    id: "news-2",
    headline: "RBI keeps rates unchanged, signals possible cut in Aug",
    summary: "Monetary policy committee holds repo rate at 6.5% while signaling easing bias ahead.",
    source: "Business Standard",
    publishedAt: "28m ago",
    companies: ["HDFC Bank", "ICICI Bank"],
    impact_score: 8.5,
    score: 85
  },
  {
    id: "news-3",
    headline: "IndiGo Q4 results beat estimates, strong outlook ahead",
    summary: "IndiGo reports 14% revenue growth, raises FY25 capacity guidance on strong travel demand.",
    source: "LiveMint",
    publishedAt: "1h ago",
    companies: ["IndiGo"],
    impact_score: 7.8,
    score: 78
  },
  {
    id: "news-4",
    headline: "Global crude prices fall on demand concerns",
    summary: "Brent crude slips below $82/bbl as weak Chinese data weighs on global demand outlook.",
    source: "Reuters",
    publishedAt: "2h ago",
    companies: ["ONGC", "BPCL", "IOC"],
    impact_score: 6.5,
    score: 65
  }
];

export const sectorHeatmapData = [
  { id: "sector-1", name: "Capital Goods", value: "+2.45%", positive: true, span: "2x" },
  { id: "sector-2", name: "Auto", value: "+1.32%", positive: true },
  { id: "sector-3", name: "Metal", value: "+1.18%", positive: true },
  { id: "sector-4", name: "Power", value: "+1.05%", positive: true },
  { id: "sector-5", name: "Banking", value: "+0.82%", positive: true },
  { id: "sector-6", name: "Infra", value: "+0.75%", positive: true },
  { id: "sector-7", name: "Oil & Gas", value: "+0.48%", positive: true },
  { id: "sector-8", name: "IT", value: "-0.35%", positive: false },
  { id: "sector-9", name: "FMCG", value: "+0.22%", positive: true },
  { id: "sector-10", name: "Pharma", value: "+0.18%", positive: true },
  { id: "sector-11", name: "Consumer Durables", value: "-0.15%", positive: false },
  { id: "sector-12", name: "Realty", value: "-0.62%", positive: false }
];

export const opportunityRadarData = [
  { id: "op-1", score: 95, theme: "AI Infrastructure Boom", reason: "Rising AI adoption, data centers, govt push", category: "Infrastructure" },
  { id: "op-2", score: 92, theme: "Railway Modernization", reason: "Strong order pipeline, multi-year capex", category: "Infrastructure" },
  { id: "op-3", score: 88, theme: "Defence Manufacturing", reason: "Policy support, import substitution", category: "Defence" },
  { id: "op-4", score: 86, theme: "Green Energy Transition", reason: "Renewable push, policy tailwinds", category: "Energy" }
];

export const storiesData = [
  {
    id: "story-1",
    title: "India Defence Boom",
    description: "How policy shifts and capex are building a new defence ecosystem.",
    theme: "Macro + Government",
    image: "https://images.unsplash.com/photo-1581092334496-4f8c63c0e5a4?auto=format&fit=crop&w=1200&q=80"
  },
  {
    id: "story-2",
    title: "AI Infrastructure",
    description: "The platform companies powering enterprise AI adoption across India.",
    theme: "Technology",
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?auto=format&fit=crop&w=1200&q=80"
  },
  {
    id: "story-3",
    title: "EV Revolution",
    description: "Battery, charging and policy signals that define the next decade of mobility.",
    theme: "Consumer + Energy",
    image: "https://images.unsplash.com/photo-1511174511562-5f7f18b874f0?auto=format&fit=crop&w=1200&q=80"
  }
];

export const governmentTrackerData = [
  {
    date: "Jul 29, 2026",
    title: "New tax incentive plan for manufacturing",
    status: "Live"
  },
  {
    date: "Jul 28, 2026",
    title: "Regulatory review on data privacy rules",
    status: "Alert"
  },
  {
    date: "Jul 27, 2026",
    title: "Infrastructure spending guidance update",
    status: "Watch"
  }
];

export const companyImpactData = [
  {
    company: "Tata Steel",
    headline: "Steel orders jump after infrastructure push",
    impact: "Positive",
    time: "3h ago"
  },
  {
    company: "Reliance Industries",
    headline: "Retail sales exceed forecasts on festive demand",
    impact: "Neutral",
    time: "5h ago"
  },
  {
    company: "Infosys",
    headline: "Strong deal pipeline lifts analyst sentiment",
    impact: "Positive",
    time: "8h ago"
  }
];

export const marketSentimentData = [
  { label: "Equity Flow", score: "Bullish", trend: "+14%" },
  { label: "Credit Demand", score: "Stable", trend: "-1%" },
  { label: "Commodity Pulse", score: "Cautious", trend: "+3%" }
];

export const stocksInFocusData = [
  { ticker: "RELIANCE", name: "Reliance Industries", price: "₹3,285.40", change: "+1.8%" },
  { ticker: "TCS", name: "Tata Consultancy Services", price: "₹4,025.10", change: "+1.4%" },
  { ticker: "ADANIPORTS", name: "Adani Ports", price: "₹4,120.75", change: "+2.1%" }
];

export const radarData = [
  {
    id: "radar-1",
    theme: "Green Energy Transition",
    score: 92,
    reason: "Policy tailwinds, capex momentum and earnings revisions.",
    confidence: 0.88,
    beneficiaries: ["Adani Green", "Tata Power"]
  },
  {
    id: "radar-2",
    theme: "Digital Infrastructure",
    score: 85,
    reason: "5G rollout and cloud demand are reshaping telecom and data center supply chains.",
    confidence: 0.82,
    beneficiaries: ["Bharti Airtel", "Tata Communications"]
  }
];

export const compareData = [
  {
    symbol: "INFY",
    name: "Infosys",
    revenue: "18.5B",
    profit: "3.2B",
    roe: "28%",
    debtEquity: "0.15",
    pe: "24.8",
    pb: "7.1",
    marketCap: "95B"
  },
  {
    symbol: "TCS",
    name: "Tata Consultancy Services",
    revenue: "27.1B",
    profit: "5.0B",
    roe: "35%",
    debtEquity: "0.02",
    pe: "29.4",
    pb: "10.5",
    marketCap: "180B"
  }
];

export const calendarData = [
  {
    id: "cal-1",
    category: "RBI",
    title: "RBI Minutes",
    date: "22 MAY",
    month: "MAY",
    day: "22",
    time: "14:00 IST",
    impact: "High",
    description: "RBI monetary policy committee meeting minutes released."
  },
  {
    id: "cal-2",
    category: "PMI",
    title: "India Manufacturing PMI",
    date: "24 MAY",
    month: "MAY",
    day: "24",
    time: "10:30 IST",
    impact: "Medium",
    description: "S&P Global India Manufacturing PMI for May 2024."
  },
  {
    id: "cal-3",
    category: "GDP",
    title: "GDP Growth Rate (QoQ)",
    date: "31 MAY",
    month: "MAY",
    day: "31",
    time: "12:00 IST",
    impact: "High",
    description: "India Q4 FY24 GDP growth rate quarterly release."
  },
  {
    id: "cal-4",
    category: "FX",
    title: "Foreign Exchange Reserves",
    date: "07 JUN",
    month: "JUN",
    day: "07",
    time: "12:30 IST",
    impact: "Medium",
    description: "RBI weekly foreign exchange reserves data."
  }
];

export const stockDetails = {
  symbol: "HAL",
  name: "Hindustan Aeronautics Limited",
  price: "₹4,628.15",
  change: "+278.75 (6.41%)",
  chartData: [
    { month: "Jun'23", value: 2600 },
    { month: "Sep'23", value: 2850 },
    { month: "Dec'23", value: 3100 },
    { month: "Mar'24", value: 3450 },
    { month: "Apr'24", value: 3850 },
    { month: "May'24", value: 4200 },
    { month: "Jun'24", value: 4628 }
  ],
  info: {
    industry: "Aerospace & Defence",
    marketCap: "₹3.09 Lakh Cr",
    pe: "32.45",
    pb: "4.1",
    roe: "18.65%",
    divYield: "0.86%",
    highLow: "4,700 / 2,812",
    faceValue: "₹25"
  },
  impactEvents: [
    {
      title: "Government increases Defence Budget by 12%",
      summary: "Positive for companies like HAL with strong order pipeline.",
      impact: "High",
      timeAgo: "2h ago"
    },
    {
      title: "HAL bags ₹3,000 Cr order for LCH Prachand helicopters",
      summary: "Order boosts helicopter manufacturing and export capability.",
      impact: "Medium",
      timeAgo: "1d ago"
    },
    {
      title: "Export opportunities rise in Africa",
      summary: "Several countries show interest in HAL’s aircraft & systems.",
      impact: "Medium",
      timeAgo: "5d ago"
    }
  ],
  news: [
    { headline: "HAL bags ₹3,000 Cr order for 12 LCH Prachand helicopters", publishedAt: "1d ago" },
    { headline: "Defence budget increase to boost aerospace stocks", publishedAt: "4h ago" },
    { headline: "HAL signs MoU with Rolls-Royce for engine tech", publishedAt: "2d ago" }
  ],
  peers: [
    { symbol: "BEL", name: "Bharat Electronics", price: "₹315.40", change: "+0.65%", marketCap: "₹2.29 Lakh Cr" },
    { symbol: "BDL", name: "Bharat Dynamics", price: "₹1,232.50", change: "+5.25%", marketCap: "₹45,662 Cr" },
    { symbol: "MAZDOCK", name: "Mazagon Dock", price: "₹2,456.00", change: "+3.85%", marketCap: "₹99,734 Cr" }
  ],
  dna: [
    { label: "Growth", value: 8.5 },
    { label: "Stability", value: 8.0 },
    { label: "Government Exposure", value: 9.5 },
    { label: "Debt Risk", value: 2.0 },
    { label: "News Sensitivity", value: 7.0 },
    { label: "Management Quality", value: 8.0 }
  ],
  keyStats: [
    { label: "Market Cap", value: "₹3.09 Lakh Cr" },
    { label: "P/E Ratio (TTM)", value: "32.45" },
    { label: "ROE", value: "18.65%" },
    { label: "Debt to Equity", value: "0.12" },
    { label: "Dividend Yield", value: "0.86%" },
    { label: "52W High / Low", value: "4,700 / 2,812" },
    { label: "Face Value", value: "₹25" }
  ],
  about: {
    description: "HAL is an India-based aerospace and defence company engaged in designing, developing, manufacturing, repairing, overhauling & upgrading aircraft, helicopters, aero-engines and related systems.",
    details: [
      { label: "Headquarters", value: "Bengaluru, India" },
      { label: "Industry", value: "Aerospace & Defence" },
      { label: "Established", value: "1940" }
    ]
  },
  timeline: [
    { label: "20 May 2024", value: "High impact: Government increases Defence Budget by 12%" },
    { label: "18 May 2024", value: "High impact: HAL secures ₹3,000 Cr order for LCH Prachand helicopters" },
    { label: "10 May 2024", value: "Medium impact: Q4 FY24 results announced" },
    { label: "2 May 2024", value: "Low impact: Promoter holding increases to 75.15%" },
    { label: "25 Apr 2024", value: "Low impact: HAL signs MoU with foreign defence firm" }
  ]
};
