// The About card's context paragraph for a company page: plain, natural sentences built only from fields the page already has, so the text is
// accurate by construction. It carries the terms people search for (the company name and ticker, "share price", the sector, market cap, P/E).

type AboutFields = {
  name: string; symbol: string; sector?: string | null; industry?: string | null;
  price?: string | number | null; pct_change?: number | null; market_cap?: string | null; pe?: string | null;
};

const has = (v: unknown): v is string | number => v !== null && v !== undefined && String(v).trim() !== "" && String(v).trim() !== "—" && String(v).trim() !== "N/A";

export function aboutHeading(s: Pick<AboutFields, "name" | "symbol">): string {
  return `About ${s.name} (${s.symbol.toUpperCase()})`;
}

export function aboutSummary(s: AboutFields): string {
  const sym = s.symbol.toUpperCase();
  const sector = has(s.sector) ? String(s.sector) : null;
  const industry = has(s.industry) && s.industry !== s.sector ? String(s.industry) : null;
  const parts: string[] = [];
  parts.push(`${s.name} (${sym}) is listed on the NSE${sector ? ` in the ${sector} sector${industry ? `, ${industry} industry` : ""}` : ""}.`);
  if (has(s.price)) {
    const pct = typeof s.pct_change === "number" && Number.isFinite(s.pct_change) ? ` (${s.pct_change >= 0 ? "+" : ""}${s.pct_change.toFixed(2)}% today)` : "";
    const withs: string[] = [];
    if (has(s.market_cap)) withs.push(`a market capitalisation of ${s.market_cap}`);
    if (has(s.pe)) withs.push(`a price-to-earnings (P/E) ratio of ${s.pe}`);
    parts.push(`The ${sym} share price is ₹${s.price}${pct}${withs.length ? `, with ${withs.join(" and ")}` : ""}.`);
  }
  parts.push(`MarketRipple tracks the ${sym} investment thesis, the ripple-chain impact of market events on ${s.name}${sector ? `, and the ${sector} sector outlook` : ""}.`);
  return parts.join(" ");
}
