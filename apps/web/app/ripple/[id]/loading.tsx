export default function RippleLoading() {
  return (
    <div className="space-y-5 animate-pulse">
      <div className="h-[140px] rounded-xl border border-white/[0.05] bg-white/[0.02]" />
      <div className="h-10 rounded-xl border border-white/[0.05] bg-white/[0.02]" />
      <div className="flex gap-5" style={{ height: 640 }}>
        <div className="flex-1 rounded-xl border border-white/[0.05] bg-white/[0.02]" />
        <div className="w-[320px] space-y-4">
          {[1,2,3,4,5].map(i => <div key={i} className="h-28 rounded-xl border border-white/[0.05] bg-white/[0.02]" />)}
        </div>
      </div>
    </div>
  );
}
