import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "../../packages/ui/src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#0f172a",
        surface2: "#111827",
        accent: "#60a5fa"
      },
      boxShadow: {
        glow: "0 20px 80px rgba(30, 58, 138, 0.35)"
      }
    }
  },
  plugins: []
};

export default config;
