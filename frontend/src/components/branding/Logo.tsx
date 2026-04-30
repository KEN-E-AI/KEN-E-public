interface LogoProps {
  size?: "sm" | "md" | "lg" | "xl" | "2xl";
  variant?: "full" | "icon";
}

export function Logo({ size = "md", variant = "full" }: LogoProps) {
  const sizeClasses = {
    sm: "size-15",
    md: "size-18",
    lg: "size-24",
    xl: "size-32",
    "2xl": "size-48",
  };

  const textSizeClasses = {
    sm: "text-lg",
    md: "text-xl",
    lg: "text-3xl",
    xl: "text-5xl",
    "2xl": "text-7xl",
  };

  return (
    <div className="flex items-center gap-3">
      <div
        className={`${sizeClasses[size]} shrink-0 transition-transform hover:rotate-0`}
        style={{
          transitionTimingFunction: "var(--ease-bounce)",
          transitionDuration: "var(--duration-default)",
        }}
      >
        <svg
          width="100%"
          height="100%"
          viewBox="5 53 190 156"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
        >
          <title>KEN-E</title>
          <defs>
            {/* Ribbon gradients */}
            <linearGradient
              id="ribPink"
              x1="60"
              y1="70"
              x2="180"
              y2="110"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#FDA4AF" />
              <stop offset="1" stopColor="#DB2777" />
            </linearGradient>

            <linearGradient
              id="ribYellow"
              x1="60"
              y1="90"
              x2="165"
              y2="140"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#FDE68A" />
              <stop offset="1" stopColor="#F59E0B" />
            </linearGradient>

            <linearGradient
              id="ribTeal"
              x1="60"
              y1="120"
              x2="180"
              y2="180"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#5EEAD4" />
              <stop offset="1" stopColor="#14B8A6" />
            </linearGradient>

            {/* Violet spine */}
            <linearGradient
              id="ribViolet"
              x1="150"
              y1="210"
              x2="60"
              y2="60"
              gradientUnits="userSpaceOnUse"
            >
              <stop stopColor="#C4B5FD" />
              <stop offset="1" stopColor="#7C3AED" />
            </linearGradient>

            {/* Soft drop shadow */}
            <filter
              id="ribbonShadow"
              x="-40"
              y="-40"
              width="336"
              height="336"
              colorInterpolationFilters="sRGB"
            >
              <feDropShadow
                dx="0"
                dy="4"
                stdDeviation="5"
                floodColor="#0B102A"
                floodOpacity="0.15"
              />
            </filter>
          </defs>

          {/* Tilt group */}
          <g
            transform="translate(128 128) rotate(-3) translate(-128 -128)"
            filter="url(#ribbonShadow)"
          >
            {/* Bolder dash marker for "KEN-E" */}
            <rect x="22" y="120" width="40" height="16" rx="8" fill="#FDE68A" />

            {/* Vertical spine (violet) */}
            <rect
              x="64"
              y="70"
              width="44"
              height="120"
              rx="22"
              fill="url(#ribViolet)"
            />

            {/* Horizontal bars */}
            <rect
              x="88"
              y="70"
              width="89.6"
              height="36"
              rx="18"
              fill="url(#ribPink)"
            />
            <rect
              x="88"
              y="110"
              width="70.4"
              height="36"
              rx="18"
              fill="url(#ribYellow)"
            />
            <rect
              x="88"
              y="150"
              width="89.6"
              height="36"
              rx="18"
              fill="url(#ribTeal)"
            />
          </g>
        </svg>
      </div>
      {variant === "full" && (
        <div>
          <h2
            className={`${textSizeClasses[size]} font-extrabold text-[var(--color-text-primary)]`}
            style={{ fontFamily: "var(--font-display)" }}
          >
            KEN-E
          </h2>
        </div>
      )}
    </div>
  );
}
