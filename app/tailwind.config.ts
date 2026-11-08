import type { Config } from "tailwindcss";

// One spacing scale (tokens.css --space-*): padding, margin, gap and space only take these steps.
const space = {
  0: "0",
  px: "1px",
  "0.5": "var(--space-3xs)",
  1: "var(--space-2xs)",
  2: "var(--space-xs)",
  3: "var(--space-sm)",
  4: "var(--space-md)",
  6: "var(--space-lg)",
  10: "var(--space-xl)",
  16: "var(--space-2xl)",
};

const config: Config = {
  content: { relative: true, files: ["./src/**/*.{ts,tsx}"] },
  theme: {
    // One type scale, ratio 1.2 from a 16px body (tokens.css --text-*).
    fontSize: {
      xs: ["var(--text-xs)", { lineHeight: "1rem" }],
      sm: ["var(--text-sm)", { lineHeight: "1.25rem" }],
      md: ["var(--text-md)", { lineHeight: "1.5rem" }],
      lg: ["var(--text-lg)", { lineHeight: "1.625rem" }],
      xl: ["var(--text-xl)", { lineHeight: "1.2" }],
      "2xl": ["var(--text-2xl)", { lineHeight: "1.1" }],
      "3xl": ["var(--text-3xl)", { lineHeight: "1.08" }],
      "4xl": ["var(--text-4xl)", { lineHeight: "1.04" }],
    },
    padding: space,
    margin: { auto: "auto", ...space },
    gap: space,
    space,
    borderRadius: {
      none: "0",
      DEFAULT: "var(--radius-inner)",
      inner: "var(--radius-inner)",
      card: "var(--radius-card)",
      pill: "var(--radius-pill)",
      full: "9999px",
    },
    extend: {
      colors: {
        bg: "var(--bg)",
        surface: "var(--surface)",
        "surface-2": "var(--surface-2)",
        "surface-3": "var(--surface-3)",
        line: "var(--line)",
        "line-strong": "var(--line-strong)",
        "field-edge": "var(--field-edge)",
        fg: "var(--fg)",
        "fg-2": "var(--fg-2)",
        "fg-3": "var(--fg-3)",
        accent: "var(--accent)",
        "accent-fill": "var(--accent-fill)",
        "accent-hi": "var(--accent-fill-hi)",
        "accent-ink": "var(--accent-ink)",
        "accent-wash": "var(--accent-wash)",
        "accent-edge": "var(--accent-edge)",
        positive: "var(--accent)",
        warning: "var(--warning)",
        "warning-wash": "var(--warning-wash)",
        "warning-edge": "var(--warning-edge)",
        negative: "var(--negative)",
        "negative-wash": "var(--negative-wash)",
      },
      fontFamily: {
        sans: ["var(--font-body)"],
        display: ["var(--font-display)"],
        mono: ["var(--font-code)"],
      },
      transitionDuration: { DEFAULT: "var(--dur-micro)", micro: "var(--dur-micro)", short: "var(--dur-short)", long: "var(--dur-long)" },
      transitionTimingFunction: { DEFAULT: "var(--ease-out)", out: "var(--ease-out)", in: "var(--ease-in)", "in-out": "var(--ease-in-out)" },
      zIndex: { tooltip: "var(--z-tooltip)", modal: "var(--z-modal)" },
    },
  },
  plugins: [],
};
export default config;
