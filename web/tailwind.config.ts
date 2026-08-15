import type { Config } from "tailwindcss";

// Design system tokens (design.md) — colors are CSS vars stored as "R G B"
// triplets and wired through the `rgb(var(--x) / <alpha-value>)` pattern so
// Tailwind's opacity modifiers (bg-coral/15, etc.) work correctly. Tailwind's
// *built-in* `stone` scale already matches design.md's stone-50/100/200/
// 400/500/800 values exactly, so it's used as-is rather than redefined here.
const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        "bg-base": "rgb(var(--bg-base) / <alpha-value>)",
        "text-dark": "rgb(var(--text-dark) / <alpha-value>)",
        "text-muted": "rgb(var(--text-muted) / <alpha-value>)",
        sage: "rgb(var(--sage) / <alpha-value>)",
        lavender: "rgb(var(--lavender) / <alpha-value>)",
        coral: "rgb(var(--coral) / <alpha-value>)",
        "coral-dark": "rgb(var(--coral-dark) / <alpha-value>)",
        "blob-pink": "rgb(var(--blob-pink) / <alpha-value>)",
        "blob-lavender": "rgb(var(--blob-lavender) / <alpha-value>)",
      },
      fontFamily: {
        sans: ["var(--font-outfit)", "ui-sans-serif", "system-ui", "sans-serif"],
        accent: ["var(--font-reenie-beanie)", "cursive"],
      },
      boxShadow: {
        // design.md §5 — the system's single resting elevation.
        soft: "0 4px 20px -2px rgba(0,0,0,0.05)",
      },
      keyframes: {
        reveal: {
          "0%": { opacity: "0", transform: "translateY(30px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0px)" },
          "50%": { transform: "translateY(-10px)" },
        },
        "timer-pulse": {
          "0%, 100%": { transform: "scale(1)" },
          "50%": { transform: "scale(1.08)" },
        },
        "dot-pulse": {
          "0%, 100%": { opacity: "0.3" },
          "50%": { opacity: "1" },
        },
      },
      animation: {
        // design.md §6 motion tokens.
        reveal: "reveal 0.8s ease both",
        float: "float 6s ease-in-out infinite",
        "float-delayed": "float 6s ease-in-out infinite 2s",
        "timer-pulse": "timer-pulse 1s ease-in-out infinite",
        "dot-pulse": "dot-pulse 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
export default config;
