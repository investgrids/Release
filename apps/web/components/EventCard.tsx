import React from "react";

interface EventCardProps {
  title: string;
  summary: string;
  score: number;
  confidence: number;
  sectors: string[];
  companies: string[];
}

export function EventCard({ title, summary, score, confidence, sectors, companies }: EventCardProps) {
  return (
    <article className="rounded-3xl border border-surface-border/10 bg-bg/80 p-6 shadow-glow transition hover:-translate-y-1 hover:border-sky-400/30">
      <div className="flex items-center justify-between gap-4">
        <span className="rounded-full bg-sky-500/10 px-3 py-1 text-xs uppercase tracking-[0.24em] text-sky-700 dark:text-sky-200">Impact {score.toFixed(1)}</span>
        <span className="text-xs text-text-secondary">Conf: {Math.round(confidence * 100)}%</span>
      </div>
      <h3 className="mt-4 text-xl font-semibold text-text-primary">{title}</h3>
      <p className="mt-3 text-sm leading-6 text-text-secondary">{summary}</p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-text-secondary">
        {sectors.map((sector) => (
          <span key={sector} className="rounded-full bg-text-primary/5 px-3 py-1">{sector}</span>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2 text-xs text-text-secondary">
        {companies.map((company) => (
          <span key={company} className="rounded-2xl bg-text-primary/[0.07] px-3 py-1">{company}</span>
        ))}
      </div>
    </article>
  );
}
