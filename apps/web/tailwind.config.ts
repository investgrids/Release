import type { Config } from "tailwindcss";
import plugin from "tailwindcss/plugin";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "../../packages/ui/src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        surface:  "#0f172a",
        surface2: "#111827",
        accent:   "#60a5fa",
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
