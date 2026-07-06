import Link from "next/link";
import { AlertTriangle } from "lucide-react";

interface AIDisclaimerProps {
  compact?: boolean;
  className?: string;
}

export function AIDisclaimer({ compact = false, className = "" }: AIDisclaimerProps) {
  if (compact) {
    return (
      <p className={`text-[10px] text-slate-600 leading-4 ${className}`} role="note">
        AI-generated analysis. Not investment advice.{" "}
        <Link href="/legal#disclaimer" className="underline hover:text-slate-400 transition">
          Disclaimer
        </Link>
      </p>
    );
  }

  return (
    <div
      className={`flex items-start gap-2 rounded-[10px] border border-amber-500/10 bg-amber-500/[0.04] px-3 py-2.5 ${className}`}
      role="note"
      aria-label="AI disclaimer"
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-amber-500/60" aria-hidden="true" />
      <p className="text-[11px] text-slate-500 leading-5">
        AI-generated analysis is intended to assist research and should not be considered investment advice.
        Always perform your own due diligence before making investment decisions.{" "}
        <Link href="/legal#disclaimer" className="text-slate-400 underline hover:text-slate-300 transition">
          Full disclaimer
        </Link>
      </p>
    </div>
  );
}
