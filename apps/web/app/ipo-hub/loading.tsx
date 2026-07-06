export default function IPOHubLoading() {
  return (
    <main className="min-w-0 space-y-5 pb-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="h-8 w-40 animate-pulse rounded-xl bg-white/10" />
          <div className="h-3 w-56 animate-pulse rounded-full bg-white/5" />
        </div>
        <div className="h-24 w-72 animate-pulse rounded-[16px] bg-white/5" />
      </div>
      <div className="grid grid-cols-3 gap-3">
        {[0,1,2].map(i => (
          <div key={i} className="h-20 animate-pulse rounded-[18px] bg-white/5" />
        ))}
      </div>
      <div className="flex gap-1">
        {[0,1,2,3,4].map(i => (
          <div key={i} className="h-8 w-28 animate-pulse rounded-[12px] bg-white/5" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <div className="h-[560px] animate-pulse rounded-[24px] bg-white/5" />
        <div className="h-[560px] animate-pulse rounded-[24px] bg-white/[0.03]" />
      </div>
    </main>
  );
}
