import React from "react";

interface SectionCardProps {
  title: string;
  description?: string;
  children: React.ReactNode;
}

export function SectionCard({ title, description, children }: SectionCardProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-slate-900/80 p-6 shadow-glow">
      <div className="mb-4">
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {description ? <p className="mt-2 text-sm text-slate-400">{description}</p> : null}
      </div>
      {children}
    </section>
  );
}
