export default function MarketsLoading() {
  return (
    <main className="min-w-0 space-y-5 pb-10">
      <div className="space-y-1">
        <div className="h-3 w-32 animate-pulse rounded-full bg-white/10" />
        <div className="h-9 w-72 animate-pulse rounded-xl bg-white/10" />
        <div className="h-3 w-64 animate-pulse rounded-full bg-white/5" />
      </div>
      {[0, 1].map(s => (
        <div key={s} className="rounded-[24px] border border-white/8 bg-white/[0.02] p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="h-4 w-40 animate-pulse rounded-full bg-white/10" />
            <div className="h-3 w-28 animate-pulse rounded-full bg-white/5" />
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {[0, 1, 2, 3].map(i => (
              <div key={i} className="rounded-[20px] border border-white/8 bg-white/[0.02] p-4 space-y-3">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 animate-pulse rounded-[12px] bg-white/10" />
                  <div className="space-y-1">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-white/10" />
                    <div className="h-2 w-12 animate-pulse rounded-full bg-white/5" />
                  </div>
                </div>
                <div className="h-6 w-24 animate-pulse rounded-lg bg-white/10" />
                <div className="h-3 w-20 animate-pulse rounded-full bg-white/5" />
                <div className="h-12 animate-pulse rounded-lg bg-white/[0.02]" />
              </div>
            ))}
          </div>
        </div>
      ))}
    </main>
  );
}
