import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      screens: {
        xl: "1200px",
      },
      // SoMx spacing extras — only keys outside Tailwind's default scale (1–12) are defined
      // here to avoid silently shifting existing p-7 / p-8 / m-9 etc. usages.
      // The SoMx CSS vars (--space-7 through --space-12) remain in index.css for direct
      // CSS use; new components should use those vars or utility classes once the component
      // sweep (follow-up PR) migrates existing references.
      spacing: {
        "15": "3.75rem",
        "18": "4.5rem",
      },
      width: {
        "15": "3.75rem",
        "18": "4.5rem",
      },
      height: {
        "15": "3.75rem",
        "18": "4.5rem",
      },
      colors: {
        border: "var(--border)",
        input: "var(--input)",
        ring: "var(--ring)",
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary)",
          foreground: "var(--secondary-foreground)",
        },
        destructive: {
          DEFAULT: "var(--destructive)",
          foreground: "var(--destructive-foreground)",
        },
        muted: {
          DEFAULT: "var(--muted)",
          foreground: "var(--muted-foreground)",
        },
        accent: {
          DEFAULT: "var(--accent)",
          foreground: "var(--accent-foreground)",
        },
        popover: {
          DEFAULT: "var(--popover)",
          foreground: "var(--popover-foreground)",
        },
        card: {
          DEFAULT: "var(--card)",
          foreground: "var(--card-foreground)",
        },
        sidebar: {
          DEFAULT: "var(--sidebar-background)",
          foreground: "var(--sidebar-foreground)",
          primary: "var(--sidebar-primary)",
          "primary-foreground": "var(--sidebar-primary-foreground)",
          accent: "var(--sidebar-accent)",
          "accent-foreground": "var(--sidebar-accent-foreground)",
          border: "var(--sidebar-border)",
          ring: "var(--sidebar-ring)",
        },
        // SoMx primitive color scales — namespaced as somx-* to avoid partially clobbering
        // Tailwind's default palette (extend.colors shallow-merges, so blue-50 and blue-600..950
        // would survive at Tailwind defaults while 100..500 became SoMx values — inconsistent
        // dark-mode behavior across the range). Use bg-somx-violet-500, text-somx-teal-300, etc.
        "somx-slate": {
          100: "var(--color-slate-100)",
          200: "var(--color-slate-200)",
          300: "var(--color-slate-300)",
          400: "var(--color-slate-400)",
          500: "var(--color-slate-500)",
        },
        "somx-blue": {
          100: "var(--color-blue-100)",
          200: "var(--color-blue-200)",
          300: "var(--color-blue-300)",
          400: "var(--color-blue-400)",
          500: "var(--color-blue-500)",
        },
        "somx-teal": {
          100: "var(--color-teal-100)",
          200: "var(--color-teal-200)",
          300: "var(--color-teal-300)",
          400: "var(--color-teal-400)",
          500: "var(--color-teal-500)",
        },
        "somx-violet": {
          100: "var(--color-violet-100)",
          200: "var(--color-violet-200)",
          300: "var(--color-violet-300)",
          400: "var(--color-violet-400)",
          500: "var(--color-violet-500)",
        },
        "somx-amber": {
          100: "var(--color-amber-100)",
          200: "var(--color-amber-200)",
          300: "var(--color-amber-300)",
          400: "var(--color-amber-400)",
          500: "var(--color-amber-500)",
        },
        // SoMx surface colors
        "bg-elevated": "var(--color-bg-elevated)",
        "bg-secondary": "var(--color-bg-secondary)",
        "bg-overlay": "var(--color-bg-overlay)",
        surface: {
          muted: "var(--color-surface-muted)",
        },
        // SoMx named borders
        "border-default": "var(--color-border-default)",
        "border-subtle": "var(--color-border-subtle)",
        "border-strong": "var(--color-border-strong)",
        // Semantic groups
        success: {
          DEFAULT: "var(--color-success)",
          bg: "var(--color-success-bg)",
          text: "var(--color-success-text)",
        },
        error: {
          DEFAULT: "var(--color-error)",
          bg: "var(--color-error-bg)",
          text: "var(--color-error-text)",
        },
        warning: {
          DEFAULT: "var(--color-warning)",
          bg: "var(--color-warning-bg)",
          text: "var(--color-warning-text)",
        },
        info: {
          DEFAULT: "var(--color-info)",
          bg: "var(--color-info-bg)",
          text: "var(--color-info-text)",
        },
        disconnected: {
          DEFAULT: "var(--color-disconnected)",
          bg: "var(--color-disconnected-bg)",
        },
        // Card accent slots
        "accent-slot": {
          1: "var(--color-accent-slot-1)",
          2: "var(--color-accent-slot-2)",
          3: "var(--color-accent-slot-3)",
          4: "var(--color-accent-slot-4)",
          5: "var(--color-accent-slot-5)",
          6: "var(--color-accent-slot-6)",
        },
        // @deprecated — legacy color groups retained to prevent ~863 silent regressions
        // across the existing codebase while a component sweep is completed in a follow-up PR.
        // Do NOT use these in new components; use SoMx tokens (somx-*, success, error, etc.) instead.
        // Values backed by --color-legacy-* CSS vars (defined in index.css :root) so all color
        // references go through the custom property system. These vars intentionally have no .dark
        // override because the legacy colors are fixed marketing values that don't participate in theming.
        brand: {
          charcoal: "var(--color-legacy-charcoal)",
          "dark-blue": "var(--color-legacy-dark-blue)",
          "medium-blue": "var(--color-legacy-medium-blue)",
          "light-green": "var(--color-legacy-light-green)",
          "dark-green": "var(--color-legacy-dark-green)",
          red: "var(--color-legacy-red)",
          "light-red": "var(--color-legacy-light-red)",
          yellow: "var(--color-legacy-yellow)",
          "light-blue": "var(--color-legacy-light-blue)",
        },
        effectiveness: {
          DEFAULT: "var(--color-legacy-effectiveness)",
          foreground: "var(--color-legacy-effectiveness-fg)",
        },
        efficiency: {
          DEFAULT: "var(--color-legacy-efficiency)",
          foreground: "var(--color-legacy-efficiency-fg)",
        },
        dashboard: {
          gray: {
            50: "var(--color-legacy-gray-50)",
            100: "var(--color-legacy-gray-100)",
            200: "var(--color-legacy-gray-200)",
            300: "var(--color-legacy-gray-300)",
            400: "var(--color-legacy-gray-400)",
            500: "var(--color-legacy-gray-500)",
            600: "var(--color-legacy-gray-600)",
            700: "var(--color-legacy-gray-700)",
            800: "var(--color-legacy-gray-800)",
            900: "var(--color-legacy-gray-900)",
          },
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        body: ["var(--font-body)"],
        sans: ["var(--font-body)"],
      },
      fontSize: {
        "display-xl": [
          "var(--text-display-xl)",
          { lineHeight: "var(--lh-display-xl)" },
        ],
        "display-lg": [
          "var(--text-display-lg)",
          { lineHeight: "var(--lh-display-lg)" },
        ],
        "display-md": [
          "var(--text-display-md)",
          { lineHeight: "var(--lh-display-md)" },
        ],
        "heading-lg": [
          "var(--text-heading-lg)",
          { lineHeight: "var(--lh-heading-lg)" },
        ],
        "heading-md": [
          "var(--text-heading-md)",
          { lineHeight: "var(--lh-heading-md)" },
        ],
        "heading-sm": [
          "var(--text-heading-sm)",
          { lineHeight: "var(--lh-heading-sm)" },
        ],
        "body-lg": ["var(--text-body-lg)", { lineHeight: "var(--lh-body)" }],
        "body-md": ["var(--text-body-md)", { lineHeight: "var(--lh-body-md)" }],
        "body-sm": ["var(--text-body-sm)", { lineHeight: "var(--lh-body-sm)" }],
        caption: ["var(--text-caption)", { lineHeight: "var(--lh-caption)" }],
        overline: ["var(--text-overline)", { lineHeight: "var(--lh-caption)" }],
      },
      borderRadius: {
        none: "var(--radius-none)",
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        pill: "var(--radius-pill)",
        circle: "var(--radius-circle)",
        DEFAULT: "var(--radius)",
      },
      boxShadow: {
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
        xl: "var(--shadow-xl)",
        "color-violet": "var(--shadow-color-violet)",
        "color-teal": "var(--shadow-color-teal)",
        "color-blue": "var(--shadow-color-blue)",
        glow: "var(--shadow-glow)",
      },
      backgroundImage: {
        "gradient-rainbow": "var(--gradient-rainbow)",
        "gradient-cta": "var(--gradient-cta)",
        "gradient-subtle": "var(--gradient-subtle)",
      },
      // `default` key maps --ease-default as the `ease-default` utility class.
      // Tailwind's .transition shorthand uses the uppercase DEFAULT key (deep-merged from
      // Tailwind's own config via `extend`) — the lowercase `default` key here has no effect on it.
      transitionTimingFunction: {
        default: "var(--ease-default)",
        bounce: "var(--ease-bounce)",
        spring: "var(--ease-spring)",
        smooth: "var(--ease-smooth)",
        out: "var(--ease-out)",
      },
      // Named duration tokens only — DEFAULT is intentionally absent.
      // Tailwind's transition shorthand (.transition, .transition-all, etc.) uses the DEFAULT
      // key from transitionDuration to set transition-duration, so setting DEFAULT would change
      // every transition in the app from Tailwind's stock 150ms to var(--duration-default) (300ms).
      // Use explicit named utilities (duration-fast, duration-moderate, etc.) on individual elements.
      transitionDuration: {
        instant: "var(--duration-instant)",
        fast: "var(--duration-fast)",
        moderate: "var(--duration-moderate)",
        slow: "var(--duration-slow)",
        dramatic: "var(--duration-dramatic)",
      },
      // CSS var references; Tailwind emits `z-index: var(--z-*)` — values resolve at runtime from :root
      zIndex: {
        background: "var(--z-background)",
        base: "var(--z-base)",
        card: "var(--z-card)",
        sticky: "var(--z-sticky)",
        dropdown: "var(--z-dropdown)",
        modal: "var(--z-modal)",
        toast: "var(--z-toast)",
        tooltip: "var(--z-tooltip)",
        max: "var(--z-max)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      // 0.2s matches --duration-fast (200ms); ease-out matches --ease-out.
      // If either token changes, update these string values to stay in sync.
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
} satisfies Config;
