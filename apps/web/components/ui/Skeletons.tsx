// Skeleton pulse components — dark glassmorphism, matches real component proportions
import type { ReactNode } from "react";

const P = ({ className = "" }: { className?: string }) => (
  <div className={`animate-pulse rounded-lg bg-white/[0.07] ${className}`} />
);

const Card = ({ className = "", children }: { className?: string; children: ReactNode }) => (
  <div className={`rounded-[28px] border border-white/[0.06] bg-white/[0.02] ${className}`}>{children}</div>
);

// ── PreMarket ─────────────────────────────────────────────────────────────────
export function PreMarketSkeleton() {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <P className="h-8 w-8 rounded-xl" />
          <div className="space-y-1.5"><P className="h-4 w-40" /><P className="h-3 w-28" /></div>
        </div>
        <P className="h-6 w-20 rounded-full" />
      </div>
      <div className="grid grid-cols-[1fr_auto] gap-5">
        <div className="grid grid-cols-3 gap-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.05] bg-white/[0.02] p-3">
              <P className="h-3 w-14 mb-2" /><P className="h-5 w-20 mb-1" /><P className="h-3 w-10" />
            </div>
          ))}
        </div>
        <div className="w-44 space-y-2">
          {[...Array(4)].map((_, i) => <P key={i} className="h-10 w-full rounded-xl" />)}
        </div>
      </div>
    </Card>
  );
}

// ── Market Overview + Sectors ─────────────────────────────────────────────────
export function MarketSkeleton() {
  return (
    <div className="grid grid-cols-[1fr_280px] gap-5 items-start">
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <P className="h-4 w-36" /><P className="h-7 w-28 rounded-full" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.05] p-4">
              <P className="h-3 w-20 mb-3" /><P className="h-7 w-32 mb-2" /><P className="h-3 w-16" />
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <P className="h-4 w-32 mb-4" />
        <div className="space-y-3">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <P className="h-2 w-2 rounded-full shrink-0" />
              <P className="h-3 w-24 shrink-0" />
              <P className="h-1.5 flex-1 rounded-full" />
              <P className="h-3 w-10 shrink-0" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── AI Wrap ───────────────────────────────────────────────────────────────────
export function AIWrapSkeleton() {
  return (
    <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-5">
      <div className="flex items-start gap-6">
        <div className="flex-1 space-y-3">
          <P className="h-5 w-40 rounded-full" />
          <P className="h-5 w-3/4" /><P className="h-4 w-full" /><P className="h-4 w-5/6" />
        </div>
        <div className="grid grid-cols-3 gap-3 shrink-0">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.05] p-3 min-w-[140px]">
              <P className="h-3 w-24 mb-3" />
              {[...Array(3)].map((__, j) => <P key={j} className="h-3 w-full mt-1.5" />)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Events + Opportunities ────────────────────────────────────────────────────
export function EventsOppSkeleton() {
  return (
    <div className="grid grid-cols-[1fr_280px] gap-5 items-start">
      <Card className="p-5">
        <div className="mb-4 flex items-center justify-between">
          <P className="h-4 w-32" /><P className="h-4 w-16" />
        </div>
        <div className="space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="grid grid-cols-[1fr_60px_140px_90px_60px] items-center gap-3 rounded-2xl border border-white/[0.04] px-3 py-2.5">
              <div className="space-y-1.5"><P className="h-3 w-full" /><P className="h-3 w-20" /></div>
              <P className="h-6 w-10 rounded-full mx-auto" />
              <div className="flex gap-1">{[...Array(3)].map((__, j) => <P key={j} className="h-7 w-7 rounded-full" />)}</div>
              <P className="h-5 w-16 rounded-full" />
              <P className="h-3 w-10 ml-auto" />
            </div>
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <P className="h-4 w-40 mb-4" />
        <div className="space-y-2.5">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="rounded-2xl border border-white/[0.04] p-3">
              <div className="flex items-center gap-2 mb-2">
                <P className="h-6 w-6 rounded-lg shrink-0" /><P className="h-3 w-32" />
              </div>
              <P className="h-3 w-full mb-1" /><P className="h-3 w-4/5" />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ── Top Movers ────────────────────────────────────────────────────────────────
export function MoversSkeleton() {
  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center justify-between">
        <P className="h-4 w-28" /><P className="h-7 w-48 rounded-full" />
      </div>
      <div className="grid grid-cols-3 gap-4">
        {[...Array(3)].map((_, col) => (
          <div key={col} className="space-y-2">
            {[...Array(4)].map((__, i) => (
              <div key={i} className="flex items-center justify-between rounded-2xl border border-white/[0.04] px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <P className="h-7 w-7 rounded-lg shrink-0" />
                  <div className="space-y-1"><P className="h-3 w-12" /><P className="h-2.5 w-16" /></div>
                </div>
                <P className="h-3 w-12" />
              </div>
            ))}
          </div>
        ))}
      </div>
    </Card>
  );
}

// ── Right Sidebar ─────────────────────────────────────────────────────────────
export function RightSidebarSkeleton() {
  return (
    <aside className="hidden xl:flex xl:flex-col gap-4 min-w-0 sticky top-[88px] self-start max-h-[calc(100vh-100px)] overflow-y-auto scrollbar-hide pb-16">
      {[...Array(3)].map((_, i) => (
        <div key={i} className="rounded-[24px] border border-white/[0.06] bg-white/[0.02] p-4">
          <P className="h-4 w-32 mb-4" />
          <div className="space-y-2.5">
            {[...Array(4)].map((__, j) => (
              <div key={j} className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <P className="h-7 w-7 rounded-lg shrink-0" />
                  <div className="space-y-1"><P className="h-3 w-20" /><P className="h-2.5 w-14" /></div>
                </div>
                <P className="h-3 w-10" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </aside>
  );
}

// ── Ticker Bar ────────────────────────────────────────────────────────────────
export function TickerSkeleton() {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-40 glass-bar">
      <div className="mx-auto flex max-w-[1600px] items-center gap-8 overflow-x-auto px-6 py-2.5">
        {[...Array(8)].map((_, i) => (
          <div key={i} className="flex shrink-0 items-center gap-2">
            <P className="h-3 w-14" /><P className="h-3.5 w-20" /><P className="h-3 w-12" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Full Dashboard Skeleton (for loading.tsx) ─────────────────────────────────
export function DashboardSkeleton() {
  return (
    <>
      <div className="min-w-0 space-y-5 pb-36">
        {/* Hero */}
        <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-6">
          <div className="flex items-center justify-between mb-5">
            <div className="space-y-2"><P className="h-5 w-48" /><P className="h-8 w-72" /></div>
            <div className="flex gap-3">{[...Array(4)].map((_, i) => <P key={i} className="h-16 w-32 rounded-2xl" />)}</div>
          </div>
        </div>
        <PreMarketSkeleton />
        <MarketSkeleton />
        <AIWrapSkeleton />
        <EventsOppSkeleton />
        <MoversSkeleton />
      </div>
      <RightSidebarSkeleton />
      <TickerSkeleton />
    </>
  );
}

// ── Market Intelligence Skeleton ──────────────────────────────────────────────
export function MarketIntelligenceSkeleton() {
  return (
    <>
      <div className="min-w-0 space-y-5 pb-36">
        <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-5">
          <div className="mb-5 flex items-center gap-2">
            {[...Array(6)].map((_, i) => <P key={i} className="h-9 w-32 rounded-full" />)}
          </div>
          <div className="space-y-4">
            <P className="h-32 w-full rounded-2xl" />
            <div className="grid grid-cols-2 gap-4">
              <P className="h-48 w-full rounded-2xl" /><P className="h-48 w-full rounded-2xl" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <P className="h-40 w-full rounded-2xl" /><P className="h-40 w-full rounded-2xl" />
            </div>
          </div>
        </div>
      </div>
      <RightSidebarSkeleton />
    </>
  );
}

// ── List Page Skeleton (events, news, radar, stocks) ──────────────────────────
export function ListPageSkeleton() {
  return (
    <div className="min-w-0 space-y-4 pb-20">
      {/* Header + filters */}
      <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="space-y-2"><P className="h-5 w-48" /><P className="h-3 w-32" /></div>
          <div className="flex gap-2">{[...Array(4)].map((_, i) => <P key={i} className="h-8 w-24 rounded-full" />)}</div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {[...Array(5)].map((_, i) => <P key={i} className="h-7 w-28 rounded-full" />)}
        </div>
      </div>
      {/* List items */}
      {[...Array(8)].map((_, i) => (
        <div key={i} className="rounded-[24px] border border-white/[0.06] bg-white/[0.02] p-4">
          <div className="flex items-start gap-4">
            <P className="h-10 w-10 rounded-xl shrink-0" />
            <div className="flex-1 space-y-2">
              <P className="h-4 w-3/4" /><P className="h-3 w-full" /><P className="h-3 w-5/6" />
              <div className="flex gap-2 mt-2">{[...Array(3)].map((__, j) => <P key={j} className="h-5 w-16 rounded-full" />)}</div>
            </div>
            <P className="h-8 w-14 rounded-full shrink-0" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Radar Page Skeleton ───────────────────────────────────────────────────────
export function RadarPageSkeleton() {
  return (
    <div className="min-w-0 pb-10">
      {/* Header */}
      <div className="mb-6 space-y-2">
        <P className="h-7 w-52" />
        <P className="h-4 w-64" />
      </div>
      {/* Filter row */}
      <div className="mb-6 flex gap-2 flex-wrap">
        {[...Array(5)].map((_, i) => <P key={i} className="h-9 w-28 rounded-xl" />)}
      </div>
      {/* 2-col layout */}
      <div className="grid grid-cols-[1fr_220px] gap-5 items-start">
        {/* Cards grid */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-[20px] border border-white/[0.07] bg-white/[0.02] p-4 space-y-3">
              <div className="flex items-start gap-3">
                <P className="h-14 w-14 rounded-full shrink-0" />
                <div className="flex-1 space-y-2 pt-1">
                  <P className="h-4 w-full" />
                  <P className="h-3 w-2/3" />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <P className="h-12 w-12 rounded-full shrink-0" />
                <div className="flex-1 space-y-1.5">
                  <P className="h-3 w-20" />
                  <P className="h-2 w-full rounded-full" />
                </div>
              </div>
              <P className="h-3 w-full" />
              <P className="h-3 w-4/5" />
              <div className="flex gap-1.5">
                {[...Array(4)].map((__, j) => <P key={j} className="h-7 w-7 rounded-full" />)}
              </div>
            </div>
          ))}
        </div>
        {/* Sidebar */}
        <div className="rounded-[20px] border border-white/[0.07] bg-white/[0.02] p-4 space-y-4">
          <P className="h-4 w-28" />
          {[...Array(5)].map((_, i) => (
            <div key={i} className="space-y-1.5">
              <div className="flex justify-between">
                <P className="h-3 w-24" />
                <P className="h-3 w-8" />
              </div>
              <P className="h-2 w-full rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Detail Page Skeleton (events/[id], news/[id], stocks/[symbol]) ────────────
export function DetailPageSkeleton() {
  return (
    <div className="min-w-0 space-y-5 pb-20">
      {/* Breadcrumb */}
      <P className="h-4 w-48" />
      {/* Hero card */}
      <div className="rounded-[28px] border border-white/[0.06] bg-white/[0.02] p-6">
        <div className="flex items-start gap-6">
          <div className="flex-1 space-y-3">
            <div className="flex gap-2">{[...Array(3)].map((_, i) => <P key={i} className="h-6 w-20 rounded-full" />)}</div>
            <P className="h-8 w-full" /><P className="h-8 w-3/4" />
            <P className="h-4 w-full" /><P className="h-4 w-5/6" />
          </div>
          <div className="w-64 shrink-0 space-y-3">
            <P className="h-32 w-full rounded-2xl" /><P className="h-24 w-full rounded-2xl" />
          </div>
        </div>
      </div>
      {/* Tabs */}
      <div className="flex gap-1">
        {[...Array(5)].map((_, i) => <P key={i} className="h-10 w-28 rounded-full" />)}
      </div>
      {/* Content */}
      <div className="grid grid-cols-[1fr_280px] gap-5">
        <div className="space-y-4">
          <P className="h-48 w-full rounded-2xl" /><P className="h-32 w-full rounded-2xl" />
        </div>
        <div className="space-y-3">
          <P className="h-40 w-full rounded-2xl" /><P className="h-32 w-full rounded-2xl" />
        </div>
      </div>
    </div>
  );
}
