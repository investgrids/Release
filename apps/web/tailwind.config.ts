import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

const config: Config = {
  // Tied to the same [data-theme="dark"] attribute the FOUC-prevention
  // script and globals.css tokens already key off (set by ThemeToggle) —
  // NOT the media-query default, so dark: variants only fire for an
  // explicit user toggle, never OS preference alone. Used narrowly for
  // light-shade accent text (emerald-300 etc.) that reads fine on a dark
  // page but is near-invisible on the light default — everything else
  // keeps using the CSS-var token system, not dark: classes.
  darkMode: ["selector", '[data-theme="dark"]'],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design tokens (redesign) — resolve through the CSS custom
        // properties in globals.css, which flip per data-theme="dark".
        // The rgb(var(...) / <alpha-value>) pattern lets Tailwind's opacity
        // modifiers (e.g. bg-surface-card/50) keep working on top of these.
        // Nested objects so classes read as bg-surface-card, text-text-
        // primary, border-accent-violet, etc. — the old flat `surface`/
        // `surface2`/`accent` string tokens they replace had zero real
        // usage anywhere in the app (confirmed via repo-wide grep).
        bg: "rgb(var(--surface-bg) / <alpha-value>)",
        surface: {
          card: "rgb(var(--surface-card) / <alpha-value>)",
          header: "rgb(var(--surface-header) / <alpha-value>)",
          border: "rgb(var(--surface-border) / <alpha-value>)",
        },
        text: {
          primary: "rgb(var(--text-primary) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary) / <alpha-value>)",
          muted: "rgb(var(--text-muted) / <alpha-value>)",
        },
        accent: {
          violet: "rgb(var(--accent-violet) / <alpha-value>)",
          sky: "rgb(var(--accent-sky) / <alpha-value>)",
          emerald: "rgb(var(--accent-emerald) / <alpha-value>)",
          rose: "rgb(var(--accent-rose) / <alpha-value>)",
        },
      },
      boxShadow: {
        glow: "0 20px 80px rgba(30, 58, 138, 0.35)",
      },
      fontVariantNumeric: {
        tabular: "tabular-nums",
      },
    },
  },
  plugins: [
    // scrollbar-hide: Tailwind v3 has no built-in utility; define here
    plugin(({ addUtilities }) => {
      addUtilities({
        ".scrollbar-hide": {
          "-ms-overflow-style": "none",
          "scrollbar-width":    "none",
          "&::-webkit-scrollbar": { display: "none" },
        },
        // Tabular numeric digits — keeps price/change columns stable on update
        ".num": {
          "font-variant-numeric": "tabular-nums",
          "font-feature-settings": '"tnum" 1',
        },
      });
    }),
  ],
};

export default config;
