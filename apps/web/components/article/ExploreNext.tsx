import Link from "next/link";
import {
  Sparkles, Scale, Building2, Layers, Waves, History, Newspaper, ArrowRight,
} from "lucide-react";
import { truncateForQuery } from "@/lib/text";

// Consolidated "What Should You Explore Next?" module (AI Newsroom redesign,
// 2026-08-12) — replaces THREE previously-independent sections at the
// bottom of the article page ("Ask AI About This Event" pills,
// RelatedIntelligence's related-companies/themes chips, and NextSteps'
// takeaway/recommended/groups/path list). Those told the reader WHERE they
// could go; this tells them WHY, using only the article's own real
// structured fields (companies_affected, sectors_affected, related_*,
// ripple_effect, historical_events) — no new AI generation call, no
// fabricated comparisons or history.
//
// NextSteps.tsx itself is untouched — it's still used by /companies,
// /historical, /ripple, /opportunity-radar, /newsroom/daily-brief, and
// /intelligence, none of which this task is scoped to touch.

export interface ExploreCompany { name: string; symbol: string | null; impact: "positive" | "negative" | "neutral"; reason?: string }
export interface ExploreSector { name: string; impact?: string }
export interface ExploreRelatedCompany { symbol: string; name: string; link: string }
export interface ExploreRelatedTheme { theme: string; link: string }
export interface ExploreRelatedArticle { slug: string; headline: string; angle: string }
export interface ExploreRippleLink { from_entity: string; to_entity: string; mechanism: string }

interface ExploreNextProps {
  headline: string;
  companiesAffected: ExploreCompany[];
  sectorsAffected: ExploreSector[];
  relatedCompanies: ExploreRelatedCompany[];
  relatedThemes: ExploreRelatedTheme[];
  relatedArticles: ExploreRelatedArticle[];
  rippleEffect: ExploreRippleLink[];
  historicalCount: number;
}

interface ExploreCard {
  kind: "ask-ai" | "compare" | "company" | "sector" | "ripple" | "historical" | "related";
  icon: typeof Sparkles;
  color: string;
  eyebrow: string;
  title: string;
  description: string;
  cta: string;
  href: string;
  wide?: boolean;
}

const CARD_COLOR: Record<ExploreCard["kind"], string> = {
  "ask-ai":    "text-violet-700 dark:text-violet-300 border-violet-200 dark:border-violet-500/25 bg-violet-50 dark:bg-violet-500/10",
  compare:     "text-amber-700 dark:text-amber-300 border-amber-200 dark:border-amber-500/25 bg-amber-50 dark:bg-amber-500/10",
  company:     "text-sky-700 dark:text-sky-300 border-sky-200 dark:border-sky-500/25 bg-sky-50 dark:bg-sky-500/10",
  sector:      "text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-500/25 bg-indigo-50 dark:bg-indigo-500/10",
  ripple:      "text-cyan-700 dark:text-cyan-300 border-cyan-200 dark:border-cyan-500/25 bg-cyan-50 dark:bg-cyan-500/10",
  historical:  "text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-500/25 bg-emerald-50 dark:bg-emerald-500/10",
  related:     "text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-500/25 bg-rose-50 dark:bg-rose-500/10",
};

const nameKey = (s: string) => s.trim().toLowerCase();

// Deterministic selection — no LLM call. Priority order per spec:
// 1 Ask AI, 2 Compare, 3 Company Intelligence, 4 Sector Intelligence,
// 5 Ripple, 6 Historical, 7 Related article. Only genuinely available
// destinations render; nothing is invented to fill a slot.
function selectExploreCards(props: ExploreNextProps): ExploreCard[] {
  const { headline, companiesAffected, sectorsAffected, relatedCompanies, relatedThemes, relatedArticles, rippleEffect, historicalCount } = props;

  // related_companies/related_themes are built server-side from the exact
  // same companies_affected/sectors_affected entries, run through the real
  // symbol normalizer (app/services/symbol_normalization.py) and canonical
  // sector resolver — so a name match here guarantees a clean, non-BOM:
  // -prefixed /companies/{symbol} or real /sectors/{id} link. An affected
  // company whose symbol couldn't be normalized simply has no match here
  // and is excluded, rather than falling back to a malformed URL.
  const relatedCompanyByName = new Map(relatedCompanies.map(c => [nameKey(c.name), c]));
  const seenSymbols = new Set<string>();
  const usableCompanies = companiesAffected
    .map(c => relatedCompanyByName.get(nameKey(c.name)))
    .filter((c): c is ExploreRelatedCompany => !!c && !seenSymbols.has(c.symbol) && (seenSymbols.add(c.symbol), true));

  const primaryCompany = usableCompanies[0] ?? null;
  const secondaryCompany = usableCompanies[1] ?? null;

  const relatedThemeByName = new Map(relatedThemes.map(t => [nameKey(t.theme), t]));
  const primarySector = sectorsAffected.length > 0
    ? relatedThemeByName.get(nameKey(sectorsAffected[0].name)) ?? relatedThemes[0] ?? null
    : relatedThemes[0] ?? null;

  const cards: ExploreCard[] = [];

  // 1 — Ask AI (company-specific > sector-specific > generic fallback)
  if (primaryCompany) {
    const q = `How could this affect ${primaryCompany.name}?`;
    cards.push({
      kind: "ask-ai", icon: Sparkles, color: CARD_COLOR["ask-ai"],
      eyebrow: "Ask AI", title: q,
      description: "Get a company-specific impact analysis using the evidence from this story.",
      cta: `Analyze ${primaryCompany.name}`,
      href: `/ai-search?q=${encodeURIComponent(q)}`,
    });
  } else if (primarySector) {
    const q = `How could this affect the ${primarySector.theme} sector?`;
    cards.push({
      kind: "ask-ai", icon: Sparkles, color: CARD_COLOR["ask-ai"],
      eyebrow: "Ask AI", title: q,
      description: "Get a sector-specific impact analysis using the evidence from this story.",
      cta: `Analyze ${primarySector.theme}`,
      href: `/ai-search?q=${encodeURIComponent(q)}`,
    });
  } else {
    cards.push({
      kind: "ask-ai", icon: Sparkles, color: CARD_COLOR["ask-ai"],
      eyebrow: "Ask AI", title: "Ask AI about this story",
      description: "Get a full investment analysis grounded in this article's own evidence, not just the summary.",
      cta: "Ask AI",
      href: `/ai-search?q=${encodeURIComponent(truncateForQuery(headline))}`,
    });
  }

  // 2 — Compare (only with two genuinely usable companies)
  if (primaryCompany && secondaryCompany) {
    cards.push({
      kind: "compare", icon: Scale, color: CARD_COLOR.compare,
      eyebrow: "Compare", title: `${primaryCompany.name} vs ${secondaryCompany.name}`,
      description: "Compare the two most affected companies across fundamentals, recent performance, and this event's expected impact.",
      cta: "Compare companies",
      href: `/compare?a=${encodeURIComponent(primaryCompany.symbol)}&b=${encodeURIComponent(secondaryCompany.symbol)}`,
    });
  }

  // 3 — Company Intelligence
  if (primaryCompany) {
    cards.push({
      kind: "company", icon: Building2, color: CARD_COLOR.company,
      eyebrow: "Company Intelligence", title: primaryCompany.name,
      description: `Fundamentals, recent events, risks and market intelligence for ${primaryCompany.name}.`,
      cta: `View ${primaryCompany.name}`,
      href: primaryCompany.link,
    });
  }

  // 4 — Sector Intelligence
  if (primarySector) {
    cards.push({
      kind: "sector", icon: Layers, color: CARD_COLOR.sector,
      eyebrow: "Sector Intelligence", title: primarySector.theme,
      description: `See the companies, catalysts and risks currently shaping the ${primarySector.theme.toLowerCase()} sector.`,
      cta: `Explore ${primarySector.theme}`,
      href: primarySector.link,
    });
  }

  const gridCards = cards.slice(0, 4);

  // Final, single wide card — Ripple > Historical > Related article
  // (ranked alternatives; only the single highest-priority one that's
  // actually available fills the last slot, per the 3-5 card cap).
  let wideCard: ExploreCard | null = null;
  if (rippleEffect.length > 0) {
    const chain = rippleEffect.slice(0, 3).map(r => r.from_entity).concat(rippleEffect[rippleEffect.length - 1].to_entity);
    const dedupedChain = chain.filter((step, i) => i === 0 || step !== chain[i - 1]);
    wideCard = {
      kind: "ripple", icon: Waves, color: CARD_COLOR.ripple,
      eyebrow: "See Where This Story Could Ripple",
      title: dedupedChain.join(" → "),
      description: "Follow how this event connects to other companies, sectors, opportunities and risks.",
      cta: "Open Ripple Intelligence",
      href: "/ripple",
      wide: true,
    };
  } else if (historicalCount > 0) {
    wideCard = {
      kind: "historical", icon: History, color: CARD_COLOR.historical,
      eyebrow: "Historical Context",
      title: "What happened the last time a similar event occurred?",
      description: "See the verified historical precedent behind this story's confidence scoring.",
      cta: "Explore historical patterns",
      href: "/historical",
      wide: true,
    };
  } else {
    const relatedArticle = relatedArticles.find(r => r.angle !== "question") ?? relatedArticles[0] ?? null;
    if (relatedArticle) {
      wideCard = {
        kind: "related", icon: Newspaper, color: CARD_COLOR.related,
        eyebrow: "Related Intelligence",
        title: relatedArticle.headline,
        description: "See the related analysis and how this story has developed.",
        cta: "Read analysis",
        href: `/newsroom/article/${relatedArticle.slug}`,
        wide: true,
      };
    }
  }

  return wideCard ? [...gridCards, wideCard] : gridCards;
}

export function ExploreNext(props: ExploreNextProps) {
  const cards = selectExploreCards(props);
  if (cards.length === 0) return null;
  const gridCards = cards.filter(c => !c.wide);
  const wideCard = cards.find(c => c.wide) ?? null;

  return (
    <section aria-labelledby="explore-next-heading">
      <h2 id="explore-next-heading" className="text-[15px] font-bold text-text-primary">
        What Should You Explore Next?
      </h2>
      <p className="mb-4 mt-0.5 text-[12px] text-text-muted">Continue your research from this story.</p>

      <div className="grid gap-3 sm:grid-cols-2">
        {gridCards.map((card) => (
          <ExploreCardLink key={card.kind} card={card} />
        ))}
      </div>
      {wideCard && (
        <div className="mt-3">
          <ExploreCardLink card={wideCard} />
        </div>
      )}
    </section>
  );
}

function ExploreCardLink({ card }: { card: ExploreCard }) {
  const Icon = card.icon;
  return (
    <Link
      href={card.href as any}
      className="group flex flex-col rounded-2xl border border-surface-border/7 bg-text-primary/[0.02] p-4 transition hover:border-surface-border/20 hover:bg-text-primary/[0.035]"
    >
      <span className={`inline-flex w-fit items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[9px] font-bold uppercase tracking-[0.14em] ${card.color}`}>
        <Icon className="h-2.5 w-2.5" /> {card.eyebrow}
      </span>
      <p className="mt-2.5 text-[13.5px] font-semibold leading-snug text-text-primary">{card.title}</p>
      <p className="mt-1 flex-1 text-[12px] leading-5 text-text-muted">{card.description}</p>
      <span className="mt-2.5 flex items-center gap-1 text-[12px] font-semibold text-text-secondary transition group-hover:text-text-primary">
        {card.cta} <ArrowRight className="h-3 w-3 transition group-hover:translate-x-0.5" />
      </span>
    </Link>
  );
}
