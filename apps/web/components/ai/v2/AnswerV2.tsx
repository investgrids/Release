"use client";

// AI Search V2 answer renderer (Step 6). One component per answer kind, all driven by answer_availability (the Step 5 contract). White surfaces, one calm hierarchy:
// what is the answer, what supports it, what is known versus not established, who and what matters, what to look at next. Empty sections do not render.
import Link from "next/link";
import { AISearchFeedback } from "@/components/ai/AISearchFeedback";
import { AIDisclaimer } from "@/components/ai/AIDisclaimer";
import {
  EVIDENCE_TYPE_LABEL, authorizedVerdict, evidenceStrength, followUps, internalSourceLink, norm, partialNotice, resolveKind, temporaryCopy, unavailableCopy,
  type V2IndexEntry, type V2Result,
} from "./contract";

const CARD = "rounded-2xl border border-surface-border/10 bg-surface-card";
const LABEL = "text-[11px] font-semibold uppercase tracking-[0.08em] text-text-muted";
const BODY = "text-[15px] leading-7 text-text-secondary";

function Section({ label, children, testId }: { label: string; children: React.ReactNode; testId?: string }) {
  return (
    <section className="space-y-3" data-testid={testId}>
      <h2 className={LABEL}>{label}</h2>
      {children}
    </section>
  );
}

const isDup = (text: string, others: string[]) => {
  const n = norm(text);
  return !n || others.some((o) => { const m = norm(o); return m === n || (m.length > 20 && (m.includes(n) || n.includes(m))); });
};

// ── evidence ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

interface Listed { key: string; title: string; kind: string; source?: string; date?: string; cited: boolean }

function listedEvidence(r: V2Result): Listed[] {
  const cited = new Set((r.evidence_index ?? []).filter((e) => (r.claim_sources ?? []).some((c) => c.sources.includes(e.id))).map((e) => norm(e.title)));
  const out: Listed[] = [];
  (r.related_events ?? []).forEach((e) => out.push({ key: `e-${e.id}`, title: e.title, kind: "event", source: e.source, date: e.date, cited: cited.has(norm(e.title)) }));
  (r.news ?? []).forEach((n) => out.push({ key: `n-${n.id}`, title: n.headline, kind: "news", source: n.source, date: n.published_at, cited: cited.has(norm(n.headline)) }));
  (r.policies ?? []).forEach((p) => out.push({ key: `p-${p.id}`, title: p.title, kind: "policy", source: p.ministry, date: p.status, cited: cited.has(norm(p.title)) }));
  return out;
}

function SourceChips({ ids, index }: { ids: string[]; index: Map<string, V2IndexEntry> }) {
  const seen = new Set<string>();
  const chips = ids.map((id) => index.get(id)).filter((e): e is V2IndexEntry => !!e).map((e) => `${e.source ? e.source + " · " : ""}${EVIDENCE_TYPE_LABEL[e.kind] ?? "Evidence"}`).filter((t) => !seen.has(t) && !!seen.add(t));
  if (!chips.length) return null;
  return (
    <span className="mt-1.5 flex flex-wrap gap-1.5" data-testid="source-chips">
      {chips.map((c) => <span key={c} className="rounded-md border border-surface-border/10 px-1.5 py-0.5 text-[11px] text-text-muted">{c}</span>)}
    </span>
  );
}

function EvidenceRow({ e }: { e: Listed }) {
  return (
    <li className="px-4 py-3">
      <p className="text-[13.5px] font-medium leading-snug text-text-primary">{e.title}</p>
      <p className="mt-1 text-[12px] text-text-muted">
        {[EVIDENCE_TYPE_LABEL[e.kind], e.source, e.date].filter(Boolean).join(" · ")}
        {e.cited && <span className="ml-2 text-violet-600">Used in this answer</span>}
      </p>
    </li>
  );
}

const EVIDENCE_SHOWN = 5;

/** The items the answer actually used come first; the rest sit behind one disclosure so a long list never outweighs the answer. */
function EvidenceList({ items, count }: { items: Listed[]; count: number }) {
  if (!items.length) return null;
  const ordered = [...items.filter((e) => e.cited), ...items.filter((e) => !e.cited)];
  const head = ordered.slice(0, EVIDENCE_SHOWN);
  const rest = ordered.slice(EVIDENCE_SHOWN);
  return (
    <Section label={`Evidence reviewed (${count})`} testId="evidence-list">
      <ul className={`${CARD} divide-y divide-surface-border/10`}>
        {head.map((e) => <EvidenceRow key={e.key} e={e} />)}
        {rest.length > 0 && (
          <li>
            <details>
              <summary className="cursor-pointer px-4 py-3 text-[13px] font-medium text-violet-600">Show {rest.length} more</summary>
              <ul className="divide-y divide-surface-border/10 border-t border-surface-border/10">{rest.map((e) => <EvidenceRow key={e.key} e={e} />)}</ul>
            </details>
          </li>
        )}
      </ul>
    </Section>
  );
}

function StrengthNote({ r }: { r: V2Result }) {
  const s = evidenceStrength(r);
  if (!s) return null;
  return (
    <div className="space-y-1.5 text-[12.5px] leading-5 text-text-muted" data-testid="evidence-strength">
      <p>
        <span className="font-semibold text-text-secondary">Evidence strength </span>
        <span aria-label={`${s.stars} of 5`} className="tracking-[0.15em] text-text-secondary">{"●".repeat(s.stars)}{"○".repeat(5 - s.stars)}</span>
        <span> {s.stars} of 5</span>
      </p>
      <p>
        Based on which kinds of evidence were found{s.found.length ? `: ${s.found.join(", ")}` : ""}.{s.missing.length ? ` Not available: ${s.missing.join(", ")}.` : ""} This describes the evidence, not how likely the answer is to be right.
      </p>
    </div>
  );
}

function Matters({ r }: { r: V2Result }) {
  const companies = (r.companies ?? []).filter((c) => c.symbol && c.name);
  const sectors = (r.sectors ?? []).filter((s) => s.name);
  if (!companies.length && !sectors.length) return null;
  return (
    <Section label="What this involves" testId="involves">
      <ul className={`${CARD} divide-y divide-surface-border/10`}>
        {companies.map((c) => (
          <li key={c.symbol} className="px-4 py-3">
            <div className="flex items-baseline justify-between gap-3">
              <Link href={`/companies/${encodeURIComponent(c.symbol)}`} className="text-[14px] font-semibold text-text-primary hover:text-violet-600">{c.name}</Link>
              {c.price && <span className="shrink-0 text-[13px] tabular-nums text-text-secondary">₹{c.price}{c.change && <span className={`ml-2 ${c.positive ? "text-emerald-600" : "text-rose-600"}`}>{c.change}</span>}</span>}
            </div>
            {c.reason && <p className="mt-1 text-[13px] leading-5 text-text-muted">{c.reason}</p>}
          </li>
        ))}
        {sectors.map((s) => (
          <li key={s.name} className="px-4 py-3">
            <p className="text-[14px] font-semibold text-text-primary">{s.name} <span className="font-normal text-text-muted">sector</span></p>
            {s.explanation && <p className="mt-1 text-[13px] leading-5 text-text-muted">{s.explanation}</p>}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function FollowUps({ questions, onAsk, label = "Where to look next" }: { questions: string[]; onAsk: (q: string) => void; label?: string }) {
  if (!questions.length) return null;
  return (
    <Section label={label} testId="follow-ups">
      <ul className="space-y-2">
        {questions.map((q) => (
          <li key={q}>
            <button type="button" onClick={() => onAsk(q)} className="w-full rounded-xl border border-surface-border/10 bg-surface-card px-4 py-3 text-left text-[14px] leading-snug text-text-primary transition hover:border-violet-500/40">
              {q}
            </button>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Header({ r, kindLabel }: { r: V2Result; kindLabel: string }) {
  return (
    <header className="space-y-2" data-testid="answer-header">
      <p className="text-[13px] text-text-muted">{r.query}</p>
      <p className={LABEL}>{kindLabel}</p>
    </header>
  );
}

function Footer({ r, onFeedbackMeta }: { r: V2Result; onFeedbackMeta?: Meta }) {
  return (
    <footer className="space-y-4 pt-2">
      {onFeedbackMeta && r.response_id ? <AISearchFeedback meta={onFeedbackMeta} /> : null}
      <AIDisclaimer />
    </footer>
  );
}

type Meta = { responseId: string | null; query: string; specialist?: string | null; schemaVersion?: string | null; cached: boolean; latencyMs: number | null; provider: string | null };

interface Props {
  result: V2Result;
  onFollowUp: (q: string) => void;
  onRetry?: () => void;
  feedbackMeta?: Meta;
  /** Today's example questions, offered as next steps on a state that cannot answer. */
  nextQuestions?: string[];
}

// ── research and partial research ────────────────────────────────────────────────────────────────────────────────────────

function ResearchView({ result: r, onFollowUp, feedbackMeta }: Props) {
  const partial = resolveKind(r) === "partial_research";
  const a = r.answer ?? {};
  const lead = a.summary ?? "";
  const short = a.bottom_line && !isDup(a.bottom_line, [lead]) ? a.bottom_line : null;
  const index = new Map((r.evidence_index ?? []).map((e) => [e.id, e]));
  const claims = (r.claim_sources ?? []).filter((c) => c.claim && (c.status ?? "ok") === "ok" && !isDup(c.claim, [lead, a.bottom_line ?? ""]));
  const drivers = (r.key_drivers ?? []).filter((d) => d.title && d.explanation && !isDup(d.explanation, [lead, a.bottom_line ?? "", ...claims.map((c) => c.claim)]));
  const meaning = ([["Why", a.why_it_happened], ["Near term", a.immediate_impact], ["Medium term", a.medium_term], ["Longer term", a.long_term], ["Already priced in", a.what_priced_in]] as [string, string | undefined][])
    .filter(([, t]) => t && t.trim() && !isDup(t, [lead, a.bottom_line ?? "", ...claims.map((c) => c.claim)]));
  const what = !claims.length && a.what_happened && a.what_happened.trim() && !isDup(a.what_happened, [lead]) ? a.what_happened : null;
  const limits = (a.risks ?? []).filter((t) => t && !isDup(t, [lead, a.bottom_line ?? ""]));
  const opps = (a.opportunities ?? []).filter(Boolean);
  const notice = partial ? partialNotice(r) : null;
  const verdict = authorizedVerdict(r);
  const listed = listedEvidence(r);
  const questions = followUps(r);

  return (
    <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]" data-testid="answer-research" data-kind={partial ? "partial_research" : "research"}>
      <article className="min-w-0 space-y-8">
        <Header r={r} kindLabel={partial ? "Partial answer" : "Answer"} />
        {notice && (
          <div className={`${CARD} border-l-4 border-l-violet-500 px-5 py-4`} role="note" data-testid="partial-notice">
            <p className="text-[14px] font-semibold text-text-primary">{notice.title}</p>
            <p className="mt-1 text-[14px] leading-6 text-text-secondary">{notice.body}</p>
            {notice.missing.length > 0 && <p className="mt-2 text-[13px] text-text-muted">Not yet available: {notice.missing.join("; ")}.</p>}
          </div>
        )}
        <div className="space-y-3">
          <p className="text-[22px] font-semibold leading-snug tracking-tight text-text-primary sm:text-[26px]" data-testid="lead">{lead}</p>
          {short && <p className={BODY} data-testid="in-short"><span className="font-semibold text-text-primary">In short: </span>{short}</p>}
        </div>
        {verdict && (
          <Section label="MarketRipple view" testId="verdict">
            <p className={`${CARD} px-5 py-4 text-[15px] text-text-primary`}>
              <span className="font-semibold">{verdict.rating}</span>
              {verdict.direction ? <span className="text-text-secondary"> · {verdict.direction}</span> : null}
              <span className="mt-1 block text-[12.5px] text-text-muted">A research view, not a recommendation to buy or sell.</span>
            </p>
          </Section>
        )}
        {(claims.length > 0 || what) && (
          <Section label="What the evidence shows" testId="observations">
            <ul className="space-y-4">
              {claims.map((c) => (
                <li key={c.claim} className="border-l-2 border-surface-border/20 pl-4">
                  <p className="text-[15px] leading-7 text-text-primary">{c.claim}</p>
                  <SourceChips ids={c.sources} index={index} />
                </li>
              ))}
              {what && <li className="border-l-2 border-surface-border/20 pl-4"><p className="text-[15px] leading-7 text-text-primary">{what}</p></li>}
            </ul>
          </Section>
        )}
        {(drivers.length > 0 || meaning.length > 0) && (
          <Section label="What it means" testId="meaning">
            <div className="space-y-3">
              {drivers.map((d) => <p key={d.title} className={BODY}><span className="font-semibold text-text-primary">{d.title}. </span>{d.explanation}</p>)}
              {meaning.map(([k, t]) => <p key={k} className={BODY}><span className="font-semibold text-text-primary">{k}. </span>{t}</p>)}
            </div>
          </Section>
        )}
        {(limits.length > 0 || opps.length > 0) && (
          <Section label="Known limits" testId="limits">
            <ul className="space-y-2">
              {limits.map((t) => <li key={t} className={`${BODY} flex gap-3`}><span aria-hidden className="mt-3 h-1 w-1 shrink-0 rounded-full bg-text-muted" />{t}</li>)}
              {opps.map((t) => <li key={t} className={`${BODY} flex gap-3`}><span aria-hidden className="mt-3 h-1 w-1 shrink-0 rounded-full bg-text-muted" />{t}</li>)}
            </ul>
          </Section>
        )}
        <FollowUps questions={questions} onAsk={onFollowUp} />
        <Footer r={r} onFeedbackMeta={feedbackMeta} />
      </article>
      <aside className="min-w-0 space-y-8 lg:pt-14">
        <Matters r={r} />
        <EvidenceList items={listed} count={r.answer_availability?.evidence_count ?? listed.length} />
        <StrengthNote r={r} />
      </aside>
    </div>
  );
}

// ── education and product information ────────────────────────────────────────────────────────────────────────────────────

const EDU_NEXT: Record<string, string[]> = {
  pe_ratio: ["What is TCS's current P/E?", "Compare HDFC Bank and ICICI Bank"],
  fii_flows: ["How much did FIIs sell today?", "What is driving the Banking sector today?"],
  marketripple_score: ["How is HDFC Bank doing as a business?", "Compare HDFC Bank and ICICI Bank"],
};

function ExplainerView({ result: r, onFollowUp, feedbackMeta }: Props) {
  const product = resolveKind(r) === "product_information";
  const e = r.education ?? {};
  const link = internalSourceLink(e.source);
  const sections = (r.key_drivers ?? []).filter((d) => d.title && d.explanation);
  const note = r.answer?.bottom_line && !isDup(r.answer.bottom_line, [r.answer.summary ?? ""]) ? r.answer.bottom_line : null;
  const next = EDU_NEXT[e.topic ?? ""] ?? [];
  return (
    <article className="mx-auto max-w-[720px] space-y-8" data-testid={product ? "answer-product" : "answer-education"} data-kind={product ? "product_information" : "education"}>
      <Header r={r} kindLabel={product ? "MarketRipple guide" : "Explained"} />
      <div className="space-y-3">
        <h1 className="text-[26px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[30px]">{e.title || r.query}</h1>
        <p className="text-[17px] leading-8 text-text-secondary" data-testid="lead">{r.answer?.summary}</p>
      </div>
      {e.beyond_published_detail && (
        <div className={`${CARD} border-l-4 border-l-violet-500 px-5 py-4`} role="note" data-testid="partial-notice">
          <p className="text-[14px] font-semibold text-text-primary">Answered in part</p>
          <p className="mt-1 text-[14px] leading-6 text-text-secondary">This covers what MarketRipple publishes about the score. The detail you asked for is not part of the published methodology.</p>
        </div>
      )}
      {sections.length > 0 && (
        <div className="space-y-6" data-testid="explainer-sections">
          {sections.map((d) => (
            <section key={d.title} className="space-y-1.5">
              <h2 className="text-[15px] font-semibold text-text-primary">{d.title}</h2>
              <p className={BODY}>{d.explanation}</p>
            </section>
          ))}
        </div>
      )}
      {note && <p className="text-[14px] leading-6 text-text-muted" data-testid="explainer-note">{note}</p>}
      <div className={`${CARD} px-5 py-4 text-[13px] leading-5 text-text-muted`} data-testid="explainer-basis">
        <p>
          <span className="font-semibold text-text-secondary">{product ? "From the MarketRipple methodology." : "From MarketRipple's reviewed glossary."}</span>
          {" "}{product ? "This describes how the product works. It is not live market data for any company." : "This is a general explanation, not live market evidence, and not a forecast or a recommendation."}
        </p>
        {link && <p className="mt-2"><Link href={link.href} className="font-medium text-violet-600 hover:underline">{link.label}</Link></p>}
      </div>
      <FollowUps questions={next} onAsk={onFollowUp} label="Try next" />
      <Footer r={r} onFeedbackMeta={feedbackMeta} />
    </article>
  );
}

// ── unavailable and temporarily unavailable ──────────────────────────────────────────────────────────────────────────────

function NoticeView({ result: r, onFollowUp, onRetry, feedbackMeta, nextQuestions }: Props) {
  const temp = resolveKind(r) === "temporarily_unavailable";
  const copy = temp ? temporaryCopy(r.answer_availability?.reason) : unavailableCopy(r);
  const related = !temp ? listedEvidence(r) : [];
  const suggestions = (r.company_suggestions ?? []).slice(0, 4);
  const own = followUps(r);
  const next = (own.length ? own : nextQuestions ?? []).slice(0, 4);
  return (
    <article className="mx-auto max-w-[720px] space-y-8" data-testid={temp ? "answer-temporary" : "answer-unavailable"} data-kind={temp ? "temporarily_unavailable" : "unavailable"} data-reason={r.answer_availability?.reason ?? ""}>
      <Header r={r} kindLabel={temp ? "Temporarily unavailable" : "No answer"} />
      <div className="space-y-3">
        <h1 className="text-[24px] font-semibold leading-tight tracking-tight text-text-primary sm:text-[28px]" data-testid="notice-title">{copy.title}</h1>
        {copy.body && <p className="text-[16px] leading-7 text-text-secondary" data-testid="notice-body">{copy.body}</p>}
        {copy.retry && onRetry && (
          <button type="button" onClick={onRetry} className="mt-2 rounded-xl bg-violet-600 px-4 py-2 text-[13px] font-semibold text-white transition hover:bg-violet-500" data-testid="retry">Try again</button>
        )}
      </div>
      {suggestions.length > 0 && (
        <Section label="Did you mean" testId="did-you-mean">
          <div className="flex flex-wrap gap-2">
            {suggestions.map((c) => (
              <button key={c.symbol} type="button" onClick={() => onFollowUp(`How is ${c.name} doing as a business?`)} className="rounded-full border border-surface-border/10 bg-surface-card px-3.5 py-1.5 text-[13px] text-text-primary hover:border-violet-500/40">{c.name}</button>
            ))}
          </div>
        </Section>
      )}
      {related.length > 0 && <EvidenceList items={related} count={r.answer_availability?.evidence_count ?? related.length} />}
      <FollowUps questions={next} onAsk={onFollowUp} label={temp ? "Meanwhile" : "Try instead"} />
      <Footer r={r} onFeedbackMeta={feedbackMeta} />
    </article>
  );
}

export function AnswerV2(props: Props) {
  switch (resolveKind(props.result)) {
    case "education":
    case "product_information":
      return <ExplainerView {...props} />;
    case "unavailable":
    case "temporarily_unavailable":
      return <NoticeView {...props} />;
    default:
      return <ResearchView {...props} />;
  }
}
