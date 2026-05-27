import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "1.5rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          accent: "hsl(var(--sidebar-accent))",
        },
        table: {
          header: "hsl(var(--table-header))",
          "row-border": "hsl(var(--table-row-border))",
        },
        /* Figma brand literals (Compliance 360) */
        navy: "#003B5C",
        brand: {
          green: "#86BC25",
          navy: "#003B5C",
          slate: "#6B7A8D",
          ink: "#111827",
        },
        risk: {
          high: "hsl(0 78% 55%)",
          medium: "hsl(36 96% 52%)",
          low: "hsl(143 64% 38%)",
        },
      },
      fontSize: {
        /* Figma base 15px + dashboard scale */
        xs: ["0.75rem", { lineHeight: "1rem" }], /* 12px labels */
        sm: ["0.875rem", { lineHeight: "1.25rem" }], /* 14px body */
        base: ["0.9375rem", { lineHeight: "1.5rem" }], /* 15px — Figma --font-size */
        lg: ["1.125rem", { lineHeight: "1.75rem" }],
        xl: ["1.25rem", { lineHeight: "1.75rem" }],
        "2xl": ["1.5rem", { lineHeight: "2rem" }],
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 4px rgba(0, 0, 0, 0.05)",
      },
    },
  },
  plugins: [],
};

export default config;
