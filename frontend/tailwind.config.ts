import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#07090c",
        surface: "#0e1218",
        panel: "#11161d",
        elevated: "#161c25",
        border: "#1f2731",
        "border-strong": "#2b3540",
        muted: "#7c8794",
        "muted-strong": "#a3aebc",
        text: "#e7eef7",
        accent: "#7aa2ff",
        "accent-strong": "#9cb8ff",
        warn: "#f0b429",
        critical: "#ef6b6b",
        ok: "#5cd9a3",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      boxShadow: {
        card: "0 1px 0 rgba(255,255,255,0.03) inset, 0 8px 24px -12px rgba(0,0,0,0.6)",
        glow: "0 0 0 1px rgba(122,162,255,0.25), 0 8px 32px -8px rgba(122,162,255,0.25)",
      },
      backgroundImage: {
        "grad-accent": "linear-gradient(135deg,#7aa2ff 0%,#5cd9a3 100%)",
        "grad-critical": "linear-gradient(135deg,#ef6b6b 0%,#f0b429 100%)",
        "grad-panel": "linear-gradient(180deg,#11161d 0%,#0e1218 100%)",
        "grad-surface": "radial-gradient(1200px 600px at 20% -10%, rgba(122,162,255,0.08), transparent 60%), radial-gradient(800px 400px at 90% 110%, rgba(92,217,163,0.06), transparent 60%)",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in-slow": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
        pulse_dot: {
          "0%, 80%, 100%": { opacity: "0.25" },
          "40%": { opacity: "1" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.35s ease-out both",
        "fade-in-slow": "fade-in-slow 0.6s ease-out both",
        shimmer: "shimmer 1.4s linear infinite",
        "pulse-dot": "pulse_dot 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};

export default config;
