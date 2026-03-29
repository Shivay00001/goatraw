/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg:       "#0a0a0f",
        surface:  "#111118",
        surface2: "#1a1a24",
        border:   "#232330",
        border2:  "#2e2e40",
        accent:   "#7c6af7",
        accent2:  "#a594ff",
        muted:    "#6b6b80",
      },
      fontFamily: {
        mono: ["'Space Mono'", "monospace"],
        sans: ["'DM Sans'", "sans-serif"],
      },
      animation: {
        "pulse-slow": "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "spin-slow":  "spin 2s linear infinite",
        "fade-in":    "fadeIn 0.3s ease",
        "slide-up":   "slideUp 0.2s ease",
      },
      keyframes: {
        fadeIn:  { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideUp: { from: { opacity: "0", transform: "translateY(16px)" }, to: { opacity: "1", transform: "translateY(0)" } },
      },
    },
  },
  plugins: [],
};
