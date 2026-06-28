export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 text-slate-100 px-6 py-20">
      <div className="w-full max-w-xl rounded-[2rem] border border-white/10 bg-slate-900/80 p-10 text-center shadow-glow">
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">404</p>
        <h1 className="mt-4 text-4xl font-semibold text-white">Page not found</h1>
        <p className="mt-4 text-sm leading-7 text-slate-400">The route you tried does not exist. Return to the dashboard or explore events and stories.</p>
      </div>
    </main>
  );
}
