import React from "react";

interface PageShellProps {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}

export function PageShell({ title, subtitle, children }: PageShellProps) {
  return (
    <main className="mx-auto max-w-7xl px-6 py-10">
      <div className="mb-10">
        <p className="text-sm uppercase tracking-[0.24em] text-sky-300">{title}</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white">{subtitle}</h1>
      </div>
      {children}
    </main>
  );
}
