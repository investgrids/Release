/**
 * Homepage hero freshness/session-label decision (2026-10-15 fix, extended
 * 2026-10-15 for source alignment).
 *
 * Extracted from app/page.tsx's HomepageIntelligenceHero into a pure,
 * testable function -- see the homepage freshness audit this fixes. Root
 * cause: StoryEngineWorker (MIE's intraday narrative) only runs during live
 * trading hours (9:15 AM-3:30 PM IST, see the backend's
 * story_engine.py::_is_market_hours). That means mieStory.story_date is
 * ALWAYS yesterday's by design for the entire pre-market window and briefly
 * after 9:15 AM until the first intraday story lands -- not a failure, the
 * engine correctly hasn't run yet. The original logic let that structurally
 * -expected MIE staleness override even a genuinely-fresh Daily Brief,
 * producing "Tuesday's Pre-Market Intelligence" on a Wednesday morning the
 * brief itself already knew was Wednesday.
 *
 * TWO INDEPENDENT FRESHNESS DIMENSIONS, never conflated:
 *  - mieIsToday / mieVerdictFreshness: whether the MARKET VERDICT (outlook,
 *    confidence -- sourced from mieStory.pulse/confidence via
 *    deriveOutlookFromMie, UNCHANGED by this module) is genuinely today's.
 *  - briefIsToday: whether the SECTOR/COMPANY CONCLUSIONS (focusSector,
 *    highestRisk, evCompanies/briefCompanies -- all sourced from the Daily
 *    Brief article) are genuinely today's.
 * A second source-alignment review (2026-10-15) found the first version of
 * this fix conflated the two into one isGenuinelyToday/heroIsCurrent flag,
 * which meant: (a) a stale MIE verdict could be shown directly under a
 * title that said "Today's Pre-Market Intelligence" with no indication the
 * verdict itself was yesterday's, and (b) the reverse case (MIE current,
 * Brief stale) would present stale Brief-derived sector conclusions in
 * present tense. The fundamental rule, per the product decision: fresh
 * intelligence must never make stale intelligence appear fresh. So:
 *  - heroTitle distinguishes "Today's {X} Intelligence" (MIE itself is
 *    current -- the full, MIE-backed product) from "Today's {X} Brief"
 *    (only the Brief is current -- explicitly narrower wording) from
 *    "{Day}'s Market Close" (neither is current).
 *  - mieVerdictFreshness/mieVerdictDayLabel let the caller label the
 *    verdict badge as "previous session (Tuesday)" whenever mieIsToday is
 *    false, REGARDLESS of briefIsToday -- the verdict is never silently
 *    presented as current just because the Brief is.
 *  - briefIsToday is exposed so sector-conclusion sentences can be gated on
 *    it specifically (page.tsx does this for todaysSummary and
 *    heroFreshnessLabel), not on the combined isGenuinelyToday.
 * deriveOutlookFromMie() itself is NOT modified or called from here -- this
 * module only decides freshness/wording, never computes or substitutes a
 * verdict. The MIE-Live Market Intelligence consistency contract (the
 * verdict always reads the identical mieStory object, see page.tsx's own
 * comment there) is preserved untouched.
 *
 * Weekend/holiday routing happens upstream, at HomePage() via
 * isWeekendSession() against /api/market/session -- this function is never
 * reached on a weekend day and doesn't need to special-case it beyond
 * preserving the one `sessionEnum === "weekend"` branch kept for
 * defensiveness.
 */

export type FreshnessState = "fresh" | "stale" | "unavailable";
export type VerdictFreshness = "current" | "previous_session" | "unavailable";

export interface MieStoryLike {
  state?: FreshnessState | null;
  story_date?: string | null;
  /** Presence (not staleness) of this is what gates whether a verdict exists at all -- matches deriveOutlookFromMie's own `if (!pulse) return null` guard. */
  pulse?: string | null;
}

export interface HomepageFreshnessInput {
  mieStory?: MieStoryLike | null;
  /** The published_at timestamp of the morning_intelligence article (`brief.published_at`). */
  briefPublishedAt?: string | null;
  /** `/api/market/session`'s session enum (e.g. "pre_market" | "pre_open" | "open" | "after_market" | "weekend"). */
  sessionEnum?: string | null;
  /** Injectable for tests; defaults to the real current time. */
  now?: Date;
}

export interface HomepageFreshnessResult {
  freshnessState: FreshnessState;
  /** Whether MIE's own story is genuinely from today's IST calendar date. */
  mieIsToday: boolean;
  /** Whether the Daily Brief article is genuinely from today's IST calendar date. */
  briefIsToday: boolean;
  /** EITHER signal being genuinely today -- governs overall page framing (freshnessState's own fallback, etc), never the verdict or sector-conclusion tense directly. */
  isGenuinelyToday: boolean;
  /** Same value as isGenuinelyToday, kept as a separate name for readability at call sites (matches prior code). */
  heroIsCurrent: boolean;
  /** The real weekday the shown TITLE's data is from, only set when !isGenuinelyToday. */
  heroDayLabel: string | null;
  /** The Daily Brief's own weekday, set whenever briefPublishedAt is known -- independent of isGenuinelyToday, so callers can label brief-specific staleness (e.g. "Updated Tuesday") even while the title itself reads "today" because MIE is current. */
  briefWeekday: string | null;
  /** Whether the market verdict (outlook/confidence) is current, a labeled previous-session carry-forward, or there's no verdict to show at all. */
  mieVerdictFreshness: VerdictFreshness;
  /** The MIE story's own weekday, only set when mieVerdictFreshness is "previous_session". */
  mieVerdictDayLabel: string | null;
  sessionNoun: string;
  heroTitle: string;
}

export const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export const SESSION_NOUN: Record<string, string> = {
  pre_market: "Pre-Market Intelligence",
  pre_open: "Pre-Market Intelligence",
  open: "Market Intelligence",
  after_market: "Market Wrap",
  weekend: "Weekend → Monday Setup",
};

function istWeekday(iso: string): string {
  return WEEKDAY_NAMES[new Date(new Date(iso).getTime() + 5.5 * 3600_000).getUTCDay()];
}

export function deriveHomepageFreshness(input: HomepageFreshnessInput): HomepageFreshnessResult {
  const now = input.now ?? new Date();
  const nowIst = new Date(now.getTime() + 5.5 * 3600_000);
  const todayIstDate = nowIst.toISOString().slice(0, 10);

  // Same "no timestamp -> treat as current" fallback the prior inline code used (briefSession's own early return).
  const briefIsToday = (() => {
    if (!input.briefPublishedAt) return true;
    const dIst = new Date(new Date(input.briefPublishedAt).getTime() + 5.5 * 3600_000);
    return (
      nowIst.getUTCFullYear() === dIst.getUTCFullYear() &&
      nowIst.getUTCMonth() === dIst.getUTCMonth() &&
      nowIst.getUTCDate() === dIst.getUTCDate()
    );
  })();
  const briefWeekday = input.briefPublishedAt ? istWeekday(input.briefPublishedAt) : null;

  const storyDate = input.mieStory?.story_date ?? null;
  const mieIsToday = storyDate ? storyDate === todayIstDate : false;

  const isGenuinelyToday = mieIsToday || briefIsToday;
  const heroIsCurrent = isGenuinelyToday;
  const heroDayLabel = !isGenuinelyToday
    ? (storyDate ? WEEKDAY_NAMES[new Date(`${storyDate}T00:00:00Z`).getUTCDay()] : briefWeekday)
    : null;

  // The verdict's own freshness, independent of briefIsToday. "unavailable" means there's no pulse to form a
  // verdict from at all (deriveOutlookFromMie would return null) -- never relabeled as current or stale, just absent.
  const mieVerdictFreshness: VerdictFreshness = !input.mieStory?.pulse ? "unavailable" : mieIsToday ? "current" : "previous_session";
  const mieVerdictDayLabel = mieVerdictFreshness === "previous_session" && storyDate
    ? WEEKDAY_NAMES[new Date(`${storyDate}T00:00:00Z`).getUTCDay()]
    : null;

  const freshnessState: FreshnessState = (input.mieStory?.state as FreshnessState | undefined) ?? (briefIsToday ? "fresh" : "stale");

  const sessionEnum = input.sessionEnum ?? "";
  const sessionNoun = SESSION_NOUN[sessionEnum] ?? "Market Intelligence";
  // "Intelligence" is reserved for when MIE itself is current (the full, MIE-backed product); when only the Brief
  // is current, the title says "Brief" instead -- deliberately narrower wording so it's never read as a claim that
  // the (possibly stale) MIE-backed verdict shown alongside it is also current. "Market Wrap" has no "Intelligence"
  // substring, so it's unaffected -- an after-market wrap is already brief-like wording.
  const sessionNounBriefOnly = sessionNoun.replace("Intelligence", "Brief");
  const heroTitle =
    freshnessState !== "fresh"
      ? "Latest Market Intelligence"
      : sessionEnum === "weekend"
        ? SESSION_NOUN.weekend
        : mieIsToday
          ? `Today's ${sessionNoun}`
          : briefIsToday
            ? `Today's ${sessionNounBriefOnly}`
            : `${heroDayLabel}'s Market Close`;

  return {
    freshnessState, mieIsToday, briefIsToday, isGenuinelyToday, heroIsCurrent, heroDayLabel, briefWeekday,
    mieVerdictFreshness, mieVerdictDayLabel, sessionNoun, heroTitle,
  };
}
