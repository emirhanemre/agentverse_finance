import type { Config } from "tailwindcss";

const config: Config = {
  content: { relative: true, files: ["./src/**/*.{ts,tsx}"] },
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        fg: "var(--fg)",
        "fg-2": "var(--fg-2)",
        "fg-3": "var(--fg-3)",
        accent: "var(--accent)",
        "accent-strong": "var(--accent-strong)",
        "accent-wash": "var(--accent-wash)",
        positive: "var(--positive)",
        "positive-wash": "var(--positive-wash)",
        negative: "var(--negative)",
        "negative-wash": "var(--negative-wash)",
        warning: "var(--warning)",
        "warning-wash": "var(--warning-wash)",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "4px",
        md: "6px",
      },
      boxShadow: {
        overlay: "0 8px 24px rgba(0, 0, 0, 0.45)",
      },
    },
  },
  plugins: [],
};
export default config;
