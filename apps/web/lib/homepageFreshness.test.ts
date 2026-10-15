/**
 * Regression suite for the 2026-10-15 homepage freshness fix — see
 * lib/homepageFreshness.ts's module docstring for the bug this covers:
 * "Tuesday's Pre-Market Intelligence" shown live on a Wednesday morning,
 * because MIE's intraday-only story overrode a genuinely-fresh Daily Brief.
 * No existing test covered this logic before this fix (confirmed: no test
 * file referenced heroTitle/isGenuinelyToday/briefSession before this suite).
 */
import { describe, it, expect } from "vitest";
import { deriveHomepageFreshness, SESSION_NOUN } from "./homepageFreshness";

const IST = 5.5 * 3600_000;
/** A UTC Date whose IST wall-clock time is exactly istDateStr + istTime (e.g. "2026-10-15" + "07:45"). */
function atIst(istDateStr: string, istTime: string): Date {
  return new Date(new Date(`${istDateStr}T${istTime}:00.000Z`).getTime() - IST);
}
/** An ISO timestamp whose IST wall-clock date is istDateStr, at the given IST time (defaults to midday). */
function publishedAtIst(istDateStr: string, istTime = "12:00"): string {
  return atIst(istDateStr, istTime).toISOString();
}

const TODAY = "2026-10-15";       // a Thursday
const YESTERDAY = "2026-10-14";   // a Wednesday
const FRIDAY = "2026-10-16";
const SATURDAY = "2026-10-17";
const SUNDAY = "2026-10-18";

describe("deriveHomepageFreshness — the bug this fixes", () => {
  it("weekday 07:45 IST, today's Daily Brief available, yesterday's MIE story — shows TODAY's Brief, not yesterday, and labels the verdict as previous-session (the exact live bug, plus the source-alignment fix)", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY, pulse: "-" },   // MIE hasn't run yet today -- correctly stale by design, but a real verdict exists
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),       // but the Daily Brief IS today's
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.mieIsToday).toBe(false);
    expect(r.briefIsToday).toBe(true);
    expect(r.isGenuinelyToday).toBe(true);           // the fix: EITHER signal, not MIE-only
    // "Brief", not "Intelligence" -- the MIE-backed verdict itself is NOT current, so the heading must not claim the
    // full, MIE-backed product is current just because the Brief is.
    expect(r.heroTitle).toBe("Today's Pre-Market Brief");
    expect(r.heroDayLabel).toBeNull();
    expect(r.freshnessState).toBe("fresh");
    // The verdict is explicitly labeled previous-session, independent of the (current) Brief-driven heading.
    expect(r.mieVerdictFreshness).toBe("previous_session");
    expect(r.mieVerdictDayLabel).toBe("Wednesday");
  });

  it("weekday 07:45 IST, no current Daily Brief available either — explicitly historical, never a live forecast", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),  // brief is also stale (yesterday's)
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.mieIsToday).toBe(false);
    expect(r.briefIsToday).toBe(false);
    expect(r.isGenuinelyToday).toBe(false);
    expect(r.heroDayLabel).toBe("Wednesday");
    expect(r.heroTitle).toBe("Wednesday's Market Close");              // not "Wednesday's Pre-Market Intelligence"
    expect(r.heroTitle).not.toContain("Pre-Market Intelligence");
    expect(r.heroTitle).not.toContain("Intelligence");                // no present-tense "Intelligence" claim on stale data
  });

  it("weekday 09:20 IST, no current MIE story yet (just after open) — still defers to the fresh brief, verdict still marked previous-session", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY, pulse: "+" },   // StoryEngineWorker hasn't generated today's first story yet
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "open",
      now: atIst(TODAY, "09:20"),
    });
    expect(r.isGenuinelyToday).toBe(true);
    expect(r.heroTitle).toBe("Today's Market Brief");
    expect(r.mieVerdictFreshness).toBe("previous_session");
  });

  it("weekday 09:35 IST, current MIE story available — MIE takes over, identical to pre-fix behavior, verdict marked current", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TODAY, pulse: "+" },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "open",
      now: atIst(TODAY, "09:35"),
    });
    expect(r.mieIsToday).toBe(true);
    expect(r.isGenuinelyToday).toBe(true);
    expect(r.heroTitle).toBe("Today's Market Intelligence");
    expect(r.mieVerdictFreshness).toBe("current");
    expect(r.mieVerdictDayLabel).toBeNull();
  });

  it("weekday 15:45 IST, current after-market intelligence available", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TODAY },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "after_market",
      now: atIst(TODAY, "15:45"),
    });
    expect(r.isGenuinelyToday).toBe(true);
    expect(r.heroTitle).toBe("Today's Market Wrap");
  });

  it("Friday evening after close, next trading day is Monday — still correctly 'today' while Friday's data is current", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: FRIDAY },
      briefPublishedAt: publishedAtIst(FRIDAY, "16:00"),
      sessionEnum: "after_market",
      now: atIst(FRIDAY, "18:00"),
    });
    expect(r.isGenuinelyToday).toBe(true);
    expect(r.heroTitle).toBe("Today's Market Wrap");
  });

  it("Saturday — weekend session noun, never a day-prefixed stale title (weekend routing is upstream, but this function must not misbehave if reached)", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: FRIDAY },
      briefPublishedAt: publishedAtIst(FRIDAY, "16:00"),
      sessionEnum: "weekend",
      now: atIst(SATURDAY, "11:00"),
    });
    expect(r.heroTitle).toBe(SESSION_NOUN.weekend);
  });

  it("Sunday — same weekend handling as Saturday", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: FRIDAY },
      briefPublishedAt: publishedAtIst(FRIDAY, "16:00"),
      sessionEnum: "weekend",
      now: atIst(SUNDAY, "11:00"),
    });
    expect(r.heroTitle).toBe(SESSION_NOUN.weekend);
  });

  it("NSE market holiday on a weekday — session enum is whatever the holiday-aware session API reports (e.g. still 'weekend'-equivalent); this function trusts sessionEnum as given, same as before the fix", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),
      sessionEnum: "weekend",   // the holiday-aware backend session service maps holidays onto the same enum value
      now: atIst(TODAY, "11:00"),
    });
    expect(r.heroTitle).toBe(SESSION_NOUN.weekend);
  });

  it("missing MIE story entirely (null) and a fresh brief — brief alone is enough", () => {
    const r = deriveHomepageFreshness({
      mieStory: null,
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.mieIsToday).toBe(false);
    expect(r.briefIsToday).toBe(true);
    expect(r.isGenuinelyToday).toBe(true);
    expect(r.freshnessState).toBe("fresh");
  });

  it("malformed/missing brief.published_at — falls back to treating the brief as current, same as the pre-fix code's own fallback", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY },
      briefPublishedAt: null,
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.briefIsToday).toBe(true);
    expect(r.isGenuinelyToday).toBe(true);
  });

  it("malformed mieStory.story_date (not a real date string) is simply never equal to today — fails safe, not throwing", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: "not-a-date" },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.mieIsToday).toBe(false);
    expect(r.isGenuinelyToday).toBe(false);
    expect(r.heroTitle).toContain("Market Close");
  });

  it("mieStory.state is explicitly 'unavailable' — freshnessState passes it through untouched regardless of today-ness", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "unavailable", story_date: TODAY },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "open",
      now: atIst(TODAY, "10:00"),
    });
    expect(r.freshnessState).toBe("unavailable");
    expect(r.heroTitle).toBe("Latest Market Intelligence");   // stale/unavailable always wins over any today-ness
  });

  it("UTC-to-IST day transition: 19:00 UTC (which is already 00:30 IST the NEXT calendar day) correctly uses the IST date, not the UTC date", () => {
    // 2026-10-14T19:00:00Z = 2026-10-15T00:30 IST -- already Wednesday in IST while still Tuesday in UTC.
    const now = new Date("2026-10-14T19:00:00.000Z");
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TODAY },             // "today" meaning the IST date, 2026-10-15
      briefPublishedAt: new Date("2026-10-14T19:15:00.000Z").toISOString(),
      sessionEnum: "weekend",
      now,
    });
    expect(r.mieIsToday).toBe(true);
    expect(r.briefIsToday).toBe(true);
  });

  it("UTC-to-IST day transition: 18:00 UTC (still 23:30 IST the SAME day) does not prematurely roll to the next IST date", () => {
    // 2026-10-14T18:00:00Z = 2026-10-14T23:30 IST -- still Tuesday in IST.
    const now = new Date("2026-10-14T18:00:00.000Z");
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY },   // "2026-10-14" is actually TODAY in IST at this instant
      briefPublishedAt: new Date("2026-10-14T13:00:00.000Z").toISOString(),
      sessionEnum: "after_market",
      now,
    });
    expect(r.mieIsToday).toBe(true);
    expect(r.briefIsToday).toBe(true);
  });
});

describe("deriveHomepageFreshness — source alignment (verdict vs. brief conclusions, independently labeled)", () => {
  it("current Brief + current MIE — full current presentation, no previous-session label anywhere", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TODAY, pulse: "+" },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "08:00"),
    });
    expect(r.mieIsToday).toBe(true);
    expect(r.briefIsToday).toBe(true);
    expect(r.heroTitle).toBe("Today's Pre-Market Intelligence");
    expect(r.mieVerdictFreshness).toBe("current");
  });

  it("current Brief + stale MIE — Brief-only heading ('Brief', not 'Intelligence'), verdict explicitly labeled previous-session with its real day", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY, pulse: "-" },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "08:00"),
    });
    expect(r.heroTitle).toBe("Today's Pre-Market Brief");
    expect(r.mieVerdictFreshness).toBe("previous_session");
    expect(r.mieVerdictDayLabel).toBe("Wednesday");
  });

  it("current Brief + no MIE at all — verdict marked unavailable, never fabricated as current or mislabeled as previous-session", () => {
    const r = deriveHomepageFreshness({
      mieStory: null,
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "08:00"),
    });
    expect(r.heroTitle).toBe("Today's Pre-Market Brief");
    expect(r.mieVerdictFreshness).toBe("unavailable");
    expect(r.mieVerdictDayLabel).toBeNull();
  });

  it("current Brief + MIE present but with no pulse (a story object that carries no verdict) — unavailable, not previous-session", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY, pulse: null },
      briefPublishedAt: publishedAtIst(TODAY, "07:30"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "08:00"),
    });
    expect(r.mieVerdictFreshness).toBe("unavailable");
  });

  it("stale Brief + current MIE — the fix's sharpest case: title stays fully current (MIE itself IS today's), verdict is current, but brief-sourced conclusions must be presented in past tense by the caller (gated on briefIsToday, not heroTitle)", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TODAY, pulse: "+" },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),
      sessionEnum: "open",
      now: atIst(TODAY, "10:00"),
    });
    expect(r.mieIsToday).toBe(true);
    expect(r.briefIsToday).toBe(false);            // <- the caller (page.tsx) must gate sector/company conclusion
                                                      //    tense and the "Updated today" caption on THIS, not on
                                                      //    heroTitle/isGenuinelyToday being true.
    expect(r.heroTitle).toBe("Today's Market Intelligence");   // correct: MIE itself genuinely is today's
    expect(r.mieVerdictFreshness).toBe("current");
    expect(r.briefWeekday).toBe("Wednesday");        // so the caller can still say "Wednesday's close" for the brief
  });

  it("both stale — the whole experience is labeled historical, AND the verdict is independently labeled previous-session with its own (possibly different) day", () => {
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: YESTERDAY, pulse: "-" },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.isGenuinelyToday).toBe(false);
    expect(r.heroTitle).toBe("Wednesday's Market Close");
    expect(r.mieVerdictFreshness).toBe("previous_session");
    expect(r.mieVerdictDayLabel).toBe("Wednesday");
  });

  it("both stale, and the MIE's own stale date differs from the Brief's stale date — the verdict label always names its OWN real day, independent of whatever the overall heading names", () => {
    // NOTE: heroDayLabel's own precedence (MIE's storyDate first when present, else the brief's day) is pre-existing,
    // unchanged behavior -- not something touched by this fix. In this specific case it names the OLDER of the two
    // stale days (MIE's) rather than the more recent one (the Brief's), which is arguably not the most informative
    // choice for the overall heading, but changing that precedence rule is outside this task's approved scope
    // (verdict labeling and brief-conclusion tense, not the headline's own day-selection rule) -- flagged in the
    // report as a separate, pre-existing nuance rather than changed here.
    const TWO_DAYS_AGO = "2026-10-13";   // a Tuesday
    const r = deriveHomepageFreshness({
      mieStory: { state: "fresh", story_date: TWO_DAYS_AGO, pulse: "-" },
      briefPublishedAt: publishedAtIst(YESTERDAY, "16:00"),   // Wednesday -- a different stale day than MIE's
      sessionEnum: "pre_open",
      now: atIst(TODAY, "07:45"),
    });
    expect(r.heroDayLabel).toBe("Tuesday");           // MIE's storyDate takes precedence for the headline (pre-existing rule, unchanged)
    expect(r.mieVerdictDayLabel).toBe("Tuesday");     // the verdict label always names its OWN real day
    expect(r.briefWeekday).toBe("Wednesday");         // the Brief's own day is still correctly available to the caller, regardless
  });

  it("pre-market to intraday transition, minute by minute: brief-backed title holds through 09:15-09:31, MIE takes over the instant its first story lands at 09:32", () => {
    const mieStale = { state: "fresh" as const, story_date: YESTERDAY, pulse: "-" };
    const mieCurrent = { state: "fresh" as const, story_date: TODAY, pulse: "-" };
    const brief = publishedAtIst(TODAY, "07:30");

    const atOpen = deriveHomepageFreshness({ mieStory: mieStale, briefPublishedAt: brief, sessionEnum: "open", now: atIst(TODAY, "09:15") });
    expect(atOpen.heroTitle).toBe("Today's Market Brief");

    const justBefore = deriveHomepageFreshness({ mieStory: mieStale, briefPublishedAt: brief, sessionEnum: "open", now: atIst(TODAY, "09:31") });
    expect(justBefore.heroTitle).toBe("Today's Market Brief");
    expect(justBefore.mieVerdictFreshness).toBe("previous_session");

    const atFirstStory = deriveHomepageFreshness({ mieStory: mieCurrent, briefPublishedAt: brief, sessionEnum: "open", now: atIst(TODAY, "09:32") });
    expect(atFirstStory.heroTitle).toBe("Today's Market Intelligence");
    expect(atFirstStory.mieVerdictFreshness).toBe("current");
  });
});
