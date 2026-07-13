import Link from "next/link";
import { ArrowRight } from "lucide-react";

export interface GuidedAction {
  label: string;
  why:   string;   // "Because..." — always explain the recommendation
  href:  string;
}

export interface ActionGroup {
  label:   string;   // "Continue Research" | "Understand More" | "Compare" | "Monitor" | "Explore Further"
  actions: GuidedAction[];
}

export interface GuidanceConfig {
  takeaway: string;           // Key insight from the current page
  primary:  GuidedAction;     // The single ★ Recommended action
  groups:   ActionGroup[];    // Grouped secondary actions
  path?:    string[];         // Intelligence research chain
}

export function NextSteps({ config }: { config: GuidanceConfig }) {
  if (!config?.groups) return null;
  const activeGroups = config.groups.filter(g => g.actions.length > 0);
  const hasPath      = (config.path?.length ?? 0) > 1;

  return (
    <div className="overflow-hidden rounded-[20px] border border-white/[0.07] bg-[#070e1b]">

      {/* ── Key Takeaway ─────────────────────────────────────────────────────── */}
      <div className="border-b border-white/[0.05] px-5 py-4">
        <p className="mb-1.5 text-[9px] font-black uppercase tracking-[0.25em] text-slate-600">
          Key Takeaway
        </p>
        <p className="text-[13px] leading-5 text-slate-300">{config.takeaway}</p>
      </div>

      {/* ── ★ Recommended Action ─────────────────────────────────────────────── */}
      <Link
        href={config.primary.href}
        className="group block border-b border-white/[0.05] px-5 py-4 transition hover:bg-amber-500/[0.04]"
      >
        <p className="mb-2 text-[9px] font-black uppercase tracking-[0.25em] text-amber-400/70">
          ★ Recommended
        </p>
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <p className="text-[13px] font-semibold text-white transition group-hover:text-amber-200">
              {config.primary.label}
            </p>
            <p className="mt-1 text-[11px] leading-4 text-slate-500">{config.primary.why}</p>
          </div>
          <ArrowRight className="mt-0.5 h-4 w-4 shrink-0 text-amber-500/40 transition group-hover:text-amber-400" />
        </div>
      </Link>

      {/* ── Grouped secondary actions ─────────────────────────────────────────── */}
      {activeGroups.map((group, gi) => (
        <div
          key={gi}
          className={gi < activeGroups.length - 1 || hasPath ? "border-b border-white/[0.05]" : ""}
        >
          <p className="px-5 pb-1 pt-3.5 text-[9px] font-black uppercase tracking-[0.25em] text-slate-600">
            {group.label}
          </p>
          {group.actions.map((a, ai) => (
            <Link
              key={ai}
              href={a.href}
              className={`group flex items-start gap-3 px-5 py-3 transition hover:bg-white/[0.03]${
                ai < group.actions.length - 1 ? " border-b border-white/[0.04]" : ""
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-slate-300 transition group-hover:text-sky-200">
                  {a.label}
                </p>
                <p className="mt-0.5 line-clamp-1 text-[11px] leading-4 text-slate-600">{a.why}</p>
              </div>
              <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-slate-700 transition group-hover:text-slate-500" />
            </Link>
          ))}
        </div>
      ))}

      {/* ── Intelligence Path ─────────────────────────────────────────────────── */}
      {hasPath && (
        <div className="px-5 py-3.5">
          <p className="mb-2 text-[9px] font-black uppercase tracking-[0.25em] text-slate-700">
            Intelligence Path
          </p>
          <div className="flex flex-wrap items-center gap-y-1">
            {config.path!.map((step, i) => (
              <span key={i} className="flex items-center">
                <span className="text-[11px] text-slate-500">{step}</span>
                {i < config.path!.length - 1 && (
                  <span className="mx-1.5 text-[10px] text-slate-700">→</span>
                )}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
