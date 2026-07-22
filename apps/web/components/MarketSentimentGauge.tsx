// Circular market-sentiment gauge — same 180° arc construction as the
// Fear & Greed gauge (components/market/MarketIntelligenceSidebar.tsx) so
// the two widgets read as one visual language, not two different gauge
// styles competing on the same product.
const R = 54, CX = 64, CY = 64;

function arcPath(from: number, to: number) {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const fx = CX + R * Math.cos(toRad(from));
  const fy = CY - R * Math.sin(toRad(from));
  const tx = CX + R * Math.cos(toRad(to));
  const ty = CY - R * Math.sin(toRad(to));
  return `M ${fx} ${fy} A ${R} ${R} 0 0 1 ${tx} ${ty}`;
}

export function MarketSentimentGauge({ score, bias, label }: { score: number; bias: string; label?: string }) {
  const clamped = Math.max(0, Math.min(100, score));
  const valueDeg = 180 - (clamped / 100) * 180;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const needleX = CX + R * Math.cos(toRad(valueDeg));
  const needleY = CY - R * Math.sin(toRad(valueDeg));

  const biasLower = bias.toLowerCase();
  const color = biasLower.includes("bull") ? "#22c55e"
    : biasLower.includes("bear") ? "#f43f5e"
    : "#f59e0b";

  return (
    <div className="flex flex-col items-center">
      <svg width="128" height="72" viewBox="0 0 128 72">
        <path d={arcPath(180, 144)} stroke="#f43f5e" strokeWidth="8" fill="none" strokeLinecap="round" />
        <path d={arcPath(144, 108)} stroke="#f97316" strokeWidth="8" fill="none" strokeLinecap="round" />
        <path d={arcPath(108, 72)}  stroke="#f59e0b" strokeWidth="8" fill="none" strokeLinecap="round" />
        <path d={arcPath(72, 36)}   stroke="#84cc16" strokeWidth="8" fill="none" strokeLinecap="round" />
        <path d={arcPath(36, 0)}    stroke="#22c55e" strokeWidth="8" fill="none" strokeLinecap="round" />
        <line x1={CX} y1={CY} x2={needleX} y2={needleY} stroke="white" strokeWidth="2" strokeLinecap="round" />
        <circle cx={CX} cy={CY} r="4" fill="white" />
      </svg>
      <p className="text-[26px] font-black leading-none text-white">{Math.round(clamped)}<span className="text-[13px] font-semibold text-slate-500">/100</span></p>
      <p className="mt-1 text-[13px] font-bold" style={{ color }}>{bias}</p>
      {label && <p className="mt-0.5 text-[10px] uppercase tracking-wider text-slate-500">{label}</p>}
    </div>
  );
}
