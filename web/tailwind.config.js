/** Tailwind theme ported verbatim from the Google Stitch "Forensic Precision" export
 *  (design-reference/) so the exact utility class names from those files render 1:1. */

const inter = ["Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"];
const mono = ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"];
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
const TOKENS = [
  "primary", "primary-container", "on-primary", "on-primary-container", "primary-fixed",
  "primary-fixed-dim", "inverse-primary", "surface-tint",
  "secondary", "secondary-container", "secondary-fixed", "secondary-fixed-dim",
  "on-secondary", "on-secondary-container",
  "tertiary", "tertiary-container", "tertiary-fixed", "tertiary-fixed-dim",
  "on-tertiary", "on-tertiary-container",
  "error", "error-container", "on-error", "on-error-container",
  "surface", "surface-dim", "surface-bright", "surface-container-lowest",
  "surface-container-low", "surface-container", "surface-container-high",
  "surface-container-highest", "surface-variant",
  "on-surface", "on-surface-variant", "outline", "outline-variant",
  "background", "on-background", "inverse-surface", "inverse-on-surface",
];

export default {
  darkMode: ["class", '[data-theme="dark"]'],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: Object.fromEntries(TOKENS.map((t) => [t, v(t)])),
      borderRadius: {
        none: "0",
        sm: "0.125rem",
        DEFAULT: "0.25rem",
        md: "0.375rem",
        lg: "0.375rem",
        xl: "0.5rem",
        full: "9999px",
      },
      spacing: {
        "space-xs": "0.125rem",
        "space-sm": "0.25rem",
        "space-md": "0.5rem",
        "space-lg": "0.75rem",
        "space-xl": "1rem",
        gutter: "0.75rem",
        margin: "1rem",
      },
      fontFamily: {
        "body-lg": inter, "body-md": inter, "body-sm": inter,
        "headline-lg": inter, "headline-md": inter, "headline-sm": inter,
        "label-ui": inter,
        "code-lg": mono, "code-md": mono, "code-sm": mono, "label-mono": mono,
      },
      fontSize: {
        "body-lg": ["14px", { lineHeight: "20px", fontWeight: "400" }],
        "body-md": ["12px", { lineHeight: "16px", fontWeight: "400" }],
        "body-sm": ["11px", { lineHeight: "14px", fontWeight: "400" }],
        "headline-lg": ["20px", { lineHeight: "28px", letterSpacing: "-0.015em", fontWeight: "600" }],
        "headline-md": ["16px", { lineHeight: "24px", letterSpacing: "-0.01em", fontWeight: "600" }],
        "headline-sm": ["13px", { lineHeight: "18px", letterSpacing: "-0.005em", fontWeight: "600" }],
        "label-ui": ["11px", { lineHeight: "14px", letterSpacing: "0.01em", fontWeight: "500" }],
        "code-lg": ["13px", { lineHeight: "20px", fontWeight: "400" }],
        "code-md": ["12px", { lineHeight: "18px", fontWeight: "400" }],
        "code-sm": ["11px", { lineHeight: "16px", fontWeight: "400" }],
        "label-mono": ["10px", { lineHeight: "12px", letterSpacing: "0.04em", fontWeight: "600" }],
      },
    },
  },
  plugins: [],
};
