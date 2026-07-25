import {
  Building2, Landmark, Flame, Cpu, TrendingUp, Radio, ShieldAlert,
  LineChart, Factory, Banknote, Sparkles, type LucideIcon,
} from "lucide-react";

/**
 * Category-matched visual treatment for article cards — a gradient + icon,
 * not a photo. Every article is real AI-written text with no accompanying
 * image asset, so anything claiming to be "the" picture for a specific
 * story would be fabricated. This is the honest alternative: a keyword
 * match against real article fields (type, sectors, headline) picks a
 * consistent, on-brand illustration for that *category* of story, the same
 * way a print section front uses a themed treatment rather than a unique
 * photo for every single piece.
 */
interface ArtSpec { icon: LucideIcon; gradient: string; }

const RULES: { test: RegExp; art: ArtSpec }[] = [
  { test: /\brbi\b|reserve bank|monetary policy|repo rate/i,
    art: { icon: Landmark,   gradient: "from-indigo-600/40 via-indigo-900/30 to-slate-950" } },
  { test: /\bbank(ing)?\b|nbfc|hdfc|icici|financ/i,
    art: { icon: Banknote,   gradient: "from-sky-600/40 via-sky-900/30 to-slate-950" } },
  { test: /crude|oil|energy|opec|petroleum|gas price/i,
    art: { icon: Flame,      gradient: "from-amber-600/40 via-orange-900/30 to-slate-950" } },
  { test: /\bai\b|artificial intelligence|semiconductor|chip|technology|it services/i,
    art: { icon: Cpu,        gradient: "from-violet-600/40 via-purple-900/30 to-slate-950" } },
  { test: /defence|defense|manufactur|industrial/i,
    art: { icon: Factory,    gradient: "from-emerald-600/40 via-emerald-900/30 to-slate-950" } },
  { test: /risk|crash|sell-?off|volatil|warning/i,
    art: { icon: ShieldAlert, gradient: "from-rose-600/40 via-rose-900/30 to-slate-950" } },
  { test: /breaking/i,
    art: { icon: Radio,      gradient: "from-rose-600/40 via-slate-900/30 to-slate-950" } },
  { test: /opportunity|theme/i,
    art: { icon: TrendingUp, gradient: "from-emerald-600/40 via-teal-900/30 to-slate-950" } },
  { test: /gdp|economy|inflation|fiscal|budget/i,
    art: { icon: Landmark,   gradient: "from-slate-600/40 via-slate-900/30 to-slate-950" } },
  { test: /company|earnings|quarterly|profit|revenue/i,
    art: { icon: Building2,  gradient: "from-sky-600/40 via-slate-900/30 to-slate-950" } },
];

const DEFAULT_ART: ArtSpec = { icon: LineChart, gradient: "from-violet-600/40 via-sky-900/30 to-slate-950" };

function pickArt(headline: string, articleType: string, sectors: string[]): ArtSpec {
  const haystack = `${headline} ${articleType} ${sectors.join(" ")}`;
  for (const rule of RULES) {
    if (rule.test.test(haystack)) return rule.art;
  }
  return DEFAULT_ART;
}

export function ArticleArt({
  headline, articleType, sectors = [], className = "",
}: {
  headline: string;
  articleType: string;
  sectors?: string[];
  className?: string;
}) {
  const { icon: Icon, gradient } = pickArt(headline, articleType, sectors);
  return (
    <div className={`relative flex items-center justify-center overflow-hidden bg-gradient-to-br ${gradient} ${className}`}>
      <div className="absolute inset-0 opacity-[0.15]" style={{
        backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)",
        backgroundSize: "24px 24px",
      }} />
      <Icon className="h-10 w-10 text-white/25" strokeWidth={1.5} />
    </div>
  );
}
