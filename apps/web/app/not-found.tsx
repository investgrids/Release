export default function NotFound() {
  return (
    <main className="grid min-h-screen place-items-center bg-bg text-text-primary px-6 py-20">
      <div className="w-full max-w-xl rounded-[2rem] border border-surface-border/10 bg-surface-card p-10 text-center shadow-glow">
        <p className="text-sm uppercase tracking-[0.24em] text-sky-600 dark:text-sky-300">404</p>
        <h1 className="mt-4 text-4xl font-semibold text-text-primary">Page not found</h1>
        <p className="mt-4 text-sm leading-7 text-text-secondary">The route you tried does not exist. Return to the dashboard or explore events and stories.</p>
      </div>
    </main>
  );
}
