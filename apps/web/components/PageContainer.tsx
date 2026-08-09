import type { ReactNode } from "react";

// The single horizontal-alignment system for the whole app — copied verbatim
// from the homepage's own container (app/page.tsx), which is the golden
// reference. Every page's left/right boundary, max-width, and responsive
// padding come from here; pages should not invent their own mx-auto/max-w/
// px-* wrapper for this purpose (a narrower reading-width column, e.g.
// max-w-[1100px] on a detail page, may still nest mx-auto+max-w inside this
// without its own horizontal padding — this container already provides it).
export function PageContainer({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`mx-auto w-full max-w-[1600px] px-5 md:px-8 ${className}`}>
      {children}
    </div>
  );
}
