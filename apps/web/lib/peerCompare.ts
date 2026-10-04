// Peer comparison helpers for the "Where <company> sits" card. Pure: they only read figures the page already shows.

export type PeerFigures = { symbol: string; pe?: string | null; roe?: string | null };

// "₹1,234.5", "15.1", "47.7%", "-3.2%" -> number; "—", "N/A", "" -> null.
export function parseFigure(v: string | number | null | undefined): number | null {
  if (v === null || v === undefined) return null;
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  const s = v.trim();
  if (!s || s === "—" || s.toUpperCase() === "N/A") return null;
  const n = Number(s.replace(/[₹%,\s]/g, ""));
  return Number.isFinite(n) ? n : null;
}

export function median(xs: number[]): number | null {
  if (xs.length === 0) return null;
  const a = [...xs].sort((x, y) => x - y);
  const m = Math.floor(a.length / 2);
  return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
}

const fmt = (n: number) => (Math.abs(n) >= 100 ? n.toFixed(0) : n.toFixed(1));

// One factual sentence per metric where at least two peers have a figure: how the company compares with the peer median, and where it ranks.
// A P/E is only compared when it is positive (a negative or missing P/E has no meaningful rank).
export function peerSentences(self: PeerFigures, peers: PeerFigures[]): string[] {
  const out: string[] = [];
  const pe = parseFigure(self.pe);
  const pePeers = peers.map(p => parseFigure(p.pe)).filter((x): x is number => x !== null && x > 0);
  if (pe !== null && pe > 0 && pePeers.length >= 2) {
    const med = median(pePeers)!;
    const dearer = pePeers.filter(x => x < pe).length, cheaper = pePeers.filter(x => x > pe).length;
    out.push(`P/E ${fmt(pe)} against a peer median of ${fmt(med)}: ${pe < med ? "below" : pe > med ? "above" : "in line with"} the median; priced ${pe < med ? `lower than ${cheaper}` : `higher than ${dearer}`} of ${pePeers.length} peers.`);
  }
  const roe = parseFigure(self.roe);
  const roePeers = peers.map(p => parseFigure(p.roe)).filter((x): x is number => x !== null);
  if (roe !== null && roePeers.length >= 2) {
    const med = median(roePeers)!;
    const higher = roePeers.filter(x => x < roe).length;
    out.push(`ROE ${fmt(roe)}% against a peer median of ${fmt(med)}%: ${roe > med ? "above" : roe < med ? "below" : "in line with"} the median; higher than ${higher} of ${roePeers.length} peers.`);
  }
  return out;
}
