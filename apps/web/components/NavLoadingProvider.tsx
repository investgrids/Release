"use client";

import { createContext, useContext, useState, useEffect, useRef, useCallback } from "react";
import { usePathname } from "next/navigation";

interface NavLoadingCtx {
  start: () => void;
  stop: () => void;
}

const Ctx = createContext<NavLoadingCtx>({ start: () => {}, stop: () => {} });

export function useNavLoading() {
  return useContext(Ctx);
}

export function NavLoadingProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);
  // Track when the loader started so we show it for at least 400ms
  const startedAt = useRef<number>(0);
  const hideTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const start = useCallback(() => {
    if (hideTimer.current) clearTimeout(hideTimer.current);
    startedAt.current = Date.now();
    setVisible(true);
  }, []);

  const stop = useCallback(() => {
    const elapsed = Date.now() - startedAt.current;
    const remaining = Math.max(0, 400 - elapsed);
    hideTimer.current = setTimeout(() => setVisible(false), remaining);
  }, []);

  // Auto-stop when the route finishes (server components / RSC)
  useEffect(() => { stop(); }, [pathname]);

  return (
    <Ctx.Provider value={{ start, stop }}>
      {children}

      {visible && (
        <>
          {/* Blur backdrop — covers content + sidebar below header */}
          <div
            className="fixed inset-0 z-40 pointer-events-none"
            style={{ backdropFilter: "blur(6px)", WebkitBackdropFilter: "blur(6px)", background: "rgba(6,7,10,0.45)" }}
          />

          {/* Centered spinner — above blur */}
          <div className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none">
            <div className="flex flex-col items-center gap-5">
              {/* Rings */}
              <div className="relative h-16 w-16">
                {/* Track ring */}
                <div className="absolute inset-0 rounded-full border-[2.5px] border-white/[0.07]" />
                {/* Outer spinning ring */}
                <div className="absolute inset-0 animate-spin rounded-full border-[2.5px] border-t-indigo-500 border-r-transparent border-b-transparent border-l-transparent [animation-duration:1s]" />
                {/* Inner counter-spinning ring */}
                <div className="absolute inset-[6px] animate-spin rounded-full border-[2px] border-t-violet-400 border-r-transparent border-b-transparent border-l-transparent [animation-duration:700ms] [animation-direction:reverse]" />
                {/* Center pulse */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="h-2 w-2 rounded-full bg-indigo-400 opacity-90 animate-pulse" />
                </div>
              </div>

              {/* Label */}
              <div className="flex flex-col items-center gap-1">
                <p className="text-xs font-semibold tracking-[0.22em] uppercase text-white/70">
                  Loading
                </p>
                {/* Animated dots */}
                <div className="flex gap-1">
                  {[0, 1, 2].map(i => (
                    <span
                      key={i}
                      className="h-1 w-1 rounded-full bg-indigo-400/60 animate-pulse"
                      style={{ animationDelay: `${i * 200}ms` }}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </Ctx.Provider>
  );
}
