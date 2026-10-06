import type { Config } from "tailwindcss";

// Opacity modifiers (bg-primary/5) work with CSS-variable tokens via color-mix.
const alpha = (v: string) => `color-mix(in srgb, var(${v}) calc(<alpha-value> * 100%), transparent)`;

// Colors come from CSS variables (DESIGN.md tokens) - never hard-coded in components.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  safelist: [{ pattern: /^badge-(neutral|success|warning|danger|info|primary)$/ }],
  theme: {
    extend: {
      colors: Object.fromEntries(Object.entries({
        bg: "--bg", surface: "--surface", muted: "--surface-muted", sidebar: "--sidebar", "sidebar-hover": "--sidebar-hover", ink: "--text", "ink-2": "--text-secondary",
        line: "--border", primary: "--primary", "primary-hover": "--primary-hover", success: "--success", warning: "--warning", danger: "--danger", info: "--info",
      }).map(([k, v]) => [k, alpha(v)])),
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"] },
      borderRadius: { card: "10px", ctl: "7px" },
      boxShadow: { card: "0 1px 2px rgba(15,23,42,0.05)", pop: "0 8px 24px rgba(15,23,42,0.12)" },
      fontSize: { body: ["13.5px", "20px"], small: ["12.5px", "18px"] },
    },
  },
  plugins: [],
};
export default config;
