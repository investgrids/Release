// Thin wrapper around the GA4 tag already loaded in app/layout.tsx (gtag.js,
// measurement ID live) — no new analytics infrastructure, just typed event
// helpers so navigation interactions are tracked consistently. Drop-off/
// funnel analysis happens in the GA4 dashboard once data collects; nothing
// further to build here for that.

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
  }
}

function send(eventName: string, params: Record<string, string>) {
  if (typeof window === "undefined" || typeof window.gtag !== "function") return;
  window.gtag("event", eventName, params);
}

/** A primary header item was clicked (Markets, Events, Insights, ...). */
export function trackNavClick(item: string) {
  send("nav_click", { nav_item: item });
}

/** An item inside a hub's mega menu / dropdown was clicked. */
export function trackSubmenuClick(hub: string, item: string) {
  send("nav_submenu_click", { hub, submenu_item: item });
}

/** A hub-scoped search box was used (Search Companies, Search Commodities, ...). */
export function trackHubSearch(hub: string, query: string) {
  if (!query.trim()) return;
  send("hub_search", { hub, query_length: String(query.trim().length) });
}

/** A tab inside a hub page was switched. */
export function trackTabSwitch(hub: string, tab: string) {
  send("hub_tab_switch", { hub, tab });
}
