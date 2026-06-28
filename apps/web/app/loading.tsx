export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-100">
      <div className="flex flex-col items-center gap-4 rounded-3xl border border-white/10 bg-slate-900/80 px-10 py-8 shadow-glow">
        <div className="h-4 w-24 animate-pulse rounded-full bg-sky-400/30" />
        <p className="text-sm text-slate-400">Loading the market intelligence experience...</p>
      </div>
    </div>
  );
}
