"use client";

import { useEffect, useState, useRef } from "react";
import { TrendingUp, TrendingDown, Zap, AlertTriangle, Activity } from "lucide-react";
import { useAlerts, type IntelligenceEvent } from "@/components/AlertProvider";
import { API_BASE_URL as API } from "@/lib/api";

const POLL_MS = 60_000; // poll DB feed every 60 s as SSE fallback

function timeAgo(iso: string) {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  return `${Math.floor(m / 60)}h ago`;
}

function AlertIcon({ headline }: { headline: string }) {
  const h = headline.toLowerCase();
  if (/direction|trend/i.test(h)) return <Activity className="h-3 w-3 text-violet-400" />;
  if (/sector|rotation/i.test(h)) return <TrendingUp className="h-3 w-3 text-sky-400" />;
  if (/volatil|vix|spike/i.test(h)) return <Zap className="h-3 w-3 text-amber-400" />;
  if (/buy|accumul|inflow|strength/i.test(h)) return <TrendingUp className="h-3 w-3 text-emerald-400" />;
  if (/sell|outflow|weak|declin/i.test(h)) return <TrendingDown className="h-3 w-3 text-rose-400" />;
  return <AlertTriangle className="h-3 w-3 text-amber-400" />;
}

function urgCls(u: number) {
  if (u >= 9) return { dot: "bg-rose-400",   badge: "bg-rose-500/20 text-rose-300"   };
  if (u >= 7) return { dot: "bg-amber-400",  badge: "bg-amber-500/20 text-amber-300" };
  if (u >= 5) return { dot: "bg-sky-400",    badge: "bg-sky-500/20 text-sky-300"     };
  return            { dot: "bg-slate-600",   badge: "bg-white/10 text-slate-400"     };
}

/** Normalize a DB feed item into IntelligenceEvent shape */
function normalizeFeedItem(r: any): IntelligenceEvent {
  return {
    id:              r.id,
    headline:        r.headline,
    urgency:         r.urgency ?? 4,
    sentiment:       r.sentiment ?? "neutral",
    direction:       r.direction ?? "sideways",
    one_liner:       r.one_liner ?? "",
    themes:          r.themes ?? [],
    sectors:         r.sectors ?? [],
    tickers:         r.tickers ?? [],
    refresh_homepage: r.refresh_homepage ?? false,
    source:          r.source ?? "news",
    ts:              r.triaged_at ?? r.ts ?? new Date().toISOString(),
  };
}

export function LiveAlertsFeed({ seed = [] }: { seed?: IntelligenceEvent[] }) {
  const { intelligenceEvents } = useAlerts();
  const [feed, setFeed] = useState<IntelligenceEvent[]>(seed);
  const seenIds = useRef<Set<string>>(new Set(seed.map(s => s.id)));
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Merge incoming SSE events (urgency >= 5)
  useEffect(() => {
    if (!intelligenceEvents.length) return;
    const incoming = intelligenceEvents.filter(e => e.urgency >= 5);
    if (!incoming.length) return;
    setFeed(prev => {
      const next = [...incoming.filter(e => !seenIds.current.has(e.id)), ...prev];
      incoming.forEach(e => seenIds.current.add(e.id));
      return next.slice(0, 10);
    });
  }, [intelligenceEvents]);

  // Poll DB feed every 60 s as fallback
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/intelligence/market/feed?limit=8`, { cache: "no-store" });
        if (!r.ok) return;
        const data = await r.json();
        const items: IntelligenceEvent[] = (data.feed ?? []).map(normalizeFeedItem);
        if (!items.length) return;
        setFeed(prev => {
          const prevIds = new Set(prev.map(p => p.id));
          const fresh = items.filter(i => !prevIds.has(i.id));
          if (!fresh.length) return prev; // nothing new
          fresh.forEach(i => seenIds.current.add(i.id));
          return [...fresh, ...prev].slice(0, 10);
        });
      } catch { /* backend offline */ }
    };

    // Run once on mount if seed was empty
    if (!seed.length) poll();

    pollingRef.current = setInterval(poll, POLL_MS);
    return () => { if (pollingRef.current) clearInterval(pollingRef.current); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-violet-400" />
        <p className="text-[11px] font-black uppercase tracking-[0.12em] text-white">Live AI Alerts</p>
        {feed.length > 0 && (
          <span className="ml-auto rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[9px] font-bold text-violet-400">
            {feed.length}
          </span>
        )}
      </div>

      {feed.length === 0 ? (
        <div className="space-y-1.5">
          {[1, 2, 3].map(i => (
            <div key={i} className="flex items-start gap-2 rounded-lg border border-white/[0.05] px-2.5 py-2">
              <div className="mt-1 h-1.5 w-1.5 rounded-full bg-slate-700" />
              <div className="flex-1">
                <div className="mb-1 h-2 w-3/4 rounded bg-white/[0.04]" />
                <div className="h-2 w-1/2 rounded bg-white/[0.03]" />
              </div>
            </div>
          ))}
          <p className="px-1 text-[10px] text-slate-600">Monitoring market for significant events…</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {feed.slice(0, 6).map(evt => {
            const cls = urgCls(evt.urgency);
            return (
              <div key={evt.id}
                className="flex items-start gap-2 rounded-lg border border-white/[0.05] bg-white/[0.02] px-2.5 py-2 transition hover:border-violet-500/15">
                <div className="mt-1 shrink-0">
                  <AlertIcon headline={evt.headline} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start gap-1.5">
                    <p className="flex-1 line-clamp-2 text-[11px] font-semibold leading-snug text-slate-200">
                      {evt.headline}
                    </p>
                    <span className={`shrink-0 rounded-full px-1 py-0.5 text-[8px] font-black ${cls.badge}`}>
                      {evt.urgency}/10
                    </span>
                  </div>
                  {evt.one_liner && evt.one_liner !== evt.headline && (
                    <p className="mt-0.5 line-clamp-1 text-[9px] leading-[1.4] text-slate-500">{evt.one_liner}</p>
                  )}
                  <div className="mt-1 flex items-center gap-1 flex-wrap">
                    {(evt.sectors ?? []).slice(0, 1).map(s => (
                      <span key={s} className="rounded-full bg-violet-500/10 px-1.5 py-0.5 text-[8px] text-violet-400">{s}</span>
                    ))}
                    {(evt.tickers ?? []).slice(0, 1).map(t => (
                      <span key={t} className="rounded-full bg-sky-500/10 px-1.5 py-0.5 text-[8px] text-sky-400">{t}</span>
                    ))}
                    <span className="ml-auto text-[9px] text-slate-600">{timeAgo(evt.ts)}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
