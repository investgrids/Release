export default function ThemesLoading() {
  return (
    <main className="min-w-0 space-y-5 pb-10">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2">
          <div className="h-8 w-36 animate-pulse rounded-xl bg-white/10" />
          <div className="h-3 w-64 animate-pulse rounded-full bg-white/5" />
        </div>
        <div className="h-10 w-40 animate-pulse rounded-[14px] bg-white/5" />
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
        {[0,1,2,3,4].map(i => (
          <div key={i} className="h-20 animate-pulse rounded-[18px] bg-white/5" />
        ))}
      </div>

      {/* Two panels */}
      <div className="grid gap-4 xl:grid-cols-[1fr_440px]">
        <div className="space-y-3">
          {[0,1,2,3,4,5].map(i => (
            <div key={i} className="h-32 animate-pulse rounded-[20px] bg-white/5" />
          ))}
        </div>
        <div className="hidden xl:block h-[700px] animate-pulse rounded-[24px] bg-white/[0.03]" />
      </div>
    </main>
  );
}
