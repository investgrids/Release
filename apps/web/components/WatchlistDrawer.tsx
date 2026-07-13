"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { X, Bookmark, Trash2, Building2, BarChart2, Zap, Lightbulb, TrendingUp, Package, ArrowRight, Search } from "lucide-react";
import { useWatchlist, type WatchlistItem, type WatchlistItemType } from "@/hooks/useWatchlist";

const TYPE_META: Record<WatchlistItemType, { icon: React.ReactNode; label: string; color: string; bg: string; href: (item: WatchlistItem) => string }> = {
  company:   { icon: <Building2 width={12} height={12}/>, label: "Company",   color: "#818cf8", bg: "rgba(99,102,241,0.12)",  href: i => `/companies/${i.ticker ?? i.id}` },
  sector:    { icon: <BarChart2  width={12} height={12}/>, label: "Sector",    color: "#34d399", bg: "rgba(52,211,153,0.12)",  href: i => `/sectors` },
  event:     { icon: <Zap        width={12} height={12}/>, label: "Event",     color: "#fbbf24", bg: "rgba(251,191,36,0.12)",  href: i => `/events/${i.id}` },
  theme:     { icon: <Lightbulb  width={12} height={12}/>, label: "Theme",     color: "#c084fc", bg: "rgba(192,132,252,0.12)", href: i => `/themes` },
  index:     { icon: <TrendingUp width={12} height={12}/>, label: "Index",     color: "#38bdf8", bg: "rgba(56,189,248,0.12)",  href: i => `/market-indices` },
  commodity: { icon: <Package    width={12} height={12}/>, label: "Commodity", color: "#fb923c", bg: "rgba(251,146,60,0.12)",  href: i => `/` },
};

const TYPE_ORDER: WatchlistItemType[] = ["company", "sector", "event", "theme", "index", "commodity"];

interface Props {
  open: boolean;
  onClose: () => void;
}

export function WatchlistDrawer({ open, onClose }: Props) {
  const { items, remove, clear } = useWatchlist();
  const overlayRef = useRef<HTMLDivElement>(null);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Group by type
  const grouped = TYPE_ORDER.reduce<Record<string, WatchlistItem[]>>((acc, t) => {
    const grp = items.filter(i => i.type === t);
    if (grp.length) acc[t] = grp;
    return acc;
  }, {});

  const timeAgo = (ts: number) => {
    const diff = Date.now() - ts;
    if (diff < 60_000) return "just now";
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return `${Math.floor(diff / 86_400_000)}d ago`;
  };

  return (
    <>
      {/* Backdrop */}
      <div
        ref={overlayRef}
        onClick={onClose}
        style={{
          position: "fixed", inset: 0, zIndex: 199,
          background: "rgba(0,0,0,0.5)", backdropFilter: "blur(2px)",
          opacity: open ? 1 : 0, pointerEvents: open ? "auto" : "none",
          transition: "opacity 0.2s",
        }}
      />

      {/* Drawer */}
      <div style={{
        position: "fixed", top: 0, right: 0, bottom: 0, zIndex: 200,
        width: 360, background: "#0a0f1c",
        borderLeft: "1px solid rgba(255,255,255,0.07)",
        display: "flex", flexDirection: "column",
        transform: open ? "translateX(0)" : "translateX(100%)",
        transition: "transform 0.25s cubic-bezier(0.4,0,0.2,1)",
        boxShadow: "-20px 0 60px rgba(0,0,0,0.5)",
      }}>

        {/* Header */}
        <div style={{ padding: "18px 18px 14px", borderBottom: "1px solid rgba(255,255,255,0.06)", flexShrink: 0 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <div style={{ width: 30, height: 30, borderRadius: 9, background: "rgba(124,58,237,0.2)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Bookmark width={14} height={14} style={{ color: "#a78bfa" }} fill="currentColor"/>
              </div>
              <div>
                <h2 style={{ fontSize: 14, fontWeight: 800, color: "#fff", margin: 0, lineHeight: 1 }}>Watchlist</h2>
                <p style={{ fontSize: 10.5, color: "#475569", marginTop: 2 }}>
                  {items.length === 0 ? "Nothing saved yet" : `${items.length} item${items.length !== 1 ? "s" : ""} saved`}
                </p>
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
              {items.length > 0 && (
                <button onClick={clear} title="Clear all" style={{ display: "flex", alignItems: "center", gap: 4, padding: "5px 9px", borderRadius: 7, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.15)", cursor: "pointer", color: "#f87171", fontSize: 11, fontWeight: 600 }}>
                  <Trash2 width={11} height={11}/> Clear
                </button>
              )}
              <button onClick={onClose} style={{ width: 30, height: 30, borderRadius: 8, background: "rgba(255,255,255,0.06)", border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#475569" }}>
                <X width={14} height={14}/>
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: "auto", padding: "12px 14px" }}>
          {items.length === 0 ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", textAlign: "center", padding: "0 24px" }}>
              <div style={{ width: 54, height: 54, borderRadius: 16, background: "rgba(124,58,237,0.1)", border: "1px solid rgba(124,58,237,0.2)", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 14 }}>
                <Bookmark width={22} height={22} style={{ color: "#7c3aed" }}/>
              </div>
              <p style={{ fontSize: 13.5, fontWeight: 700, color: "#e2e8f0", marginBottom: 7 }}>Your watchlist is empty</p>
              <p style={{ fontSize: 12, color: "#475569", lineHeight: 1.6, marginBottom: 20 }}>
                Bookmark stocks, sectors, events and themes to track them here — no sign-in required.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 7, width: "100%" }}>
                {[{ label: "Browse Companies", href: "/companies", icon: <Building2 width={13} height={13}/> }, { label: "Explore Events", href: "/events", icon: <Zap width={13} height={13}/> }, { label: "AI Search", href: "/ai-search", icon: <Search width={13} height={13}/> }].map(l => (
                  <Link key={l.href} href={l.href as any} onClick={onClose} style={{ display: "flex", alignItems: "center", gap: 9, padding: "10px 12px", borderRadius: 11, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", textDecoration: "none" }}>
                    <span style={{ color: "#7c3aed" }}>{l.icon}</span>
                    <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{l.label}</span>
                    <ArrowRight width={11} height={11} style={{ color: "#334155", marginLeft: "auto" }}/>
                  </Link>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
              {Object.entries(grouped).map(([type, grpItems]) => {
                const t = type as WatchlistItemType;
                const meta = TYPE_META[t];
                return (
                  <div key={type}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                      <span style={{ color: meta.color, opacity: 0.8 }}>{meta.icon}</span>
                      <span style={{ fontSize: 10, fontWeight: 800, color: "#334155", textTransform: "uppercase", letterSpacing: "0.08em" }}>{meta.label}s</span>
                      <span style={{ fontSize: 10, color: "#1e293b", marginLeft: 2 }}>({grpItems.length})</span>
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
                      {grpItems.map(item => (
                        <div key={item.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "9px 11px", borderRadius: 11, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)" }}>
                          <div style={{ width: 32, height: 32, borderRadius: 9, background: meta.bg, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, color: meta.color }}>
                            {meta.icon}
                          </div>
                          <Link href={meta.href(item) as any} onClick={onClose} style={{ flex: 1, minWidth: 0, textDecoration: "none" }}>
                            <p style={{ fontSize: 12.5, fontWeight: 700, color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.label}</p>
                            <p style={{ fontSize: 10.5, color: "#334155", marginTop: 1.5 }}>
                              {item.ticker && <span style={{ color: meta.color, marginRight: 5, fontWeight: 700 }}>{item.ticker}</span>}
                              {timeAgo(item.addedAt)}
                            </p>
                          </Link>
                          <button onClick={() => remove(item.id)} style={{ width: 26, height: 26, borderRadius: 7, background: "none", border: "1px solid transparent", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", color: "#334155", flexShrink: 0, transition: "all 0.15s" }}
                            onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = "rgba(239,68,68,0.1)"; (e.currentTarget as HTMLButtonElement).style.color = "#f87171"; (e.currentTarget as HTMLButtonElement).style.borderColor = "rgba(239,68,68,0.2)"; }}
                            onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = "none"; (e.currentTarget as HTMLButtonElement).style.color = "#334155"; (e.currentTarget as HTMLButtonElement).style.borderColor = "transparent"; }}>
                            <X width={11} height={11}/>
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer — future sign-in nudge */}
        <div style={{ padding: "12px 14px", borderTop: "1px solid rgba(255,255,255,0.06)", flexShrink: 0 }}>
          <div style={{ padding: "10px 12px", borderRadius: 11, background: "linear-gradient(135deg,rgba(124,58,237,0.1),rgba(59,130,246,0.08))", border: "1px solid rgba(124,58,237,0.2)", display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ flex: 1 }}>
              <p style={{ fontSize: 11.5, fontWeight: 700, color: "#c4b5fd", lineHeight: 1 }}>Sync across devices</p>
              <p style={{ fontSize: 10.5, color: "#475569", marginTop: 3 }}>Sign in to keep your watchlist forever</p>
            </div>
            <div style={{ fontSize: 18, opacity: 0.4 }}>🔒</div>
          </div>
        </div>
      </div>
    </>
  );
}
