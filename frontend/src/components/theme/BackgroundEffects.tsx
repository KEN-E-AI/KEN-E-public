import { useState, useEffect, useId } from "react";

export function BackgroundEffects() {
  const [reducedMotion, setReducedMotion] = useState(false);
  const uid = useId();
  const filterId = `grain-${uid.replace(/:/g, "")}`;

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  if (reducedMotion) {
    return (
      <div
        aria-hidden="true"
        data-testid="bg-static"
        className="fixed inset-0 pointer-events-none z-background"
        style={{
          background:
            "linear-gradient(135deg, var(--color-blob-blue), var(--color-blob-violet), var(--color-blob-teal), var(--color-blob-slate))",
        }}
      />
    );
  }

  return (
    <>
      <div
        aria-hidden="true"
        data-testid="bg-blobs"
        className="fixed inset-0 pointer-events-none overflow-hidden z-background"
      >
        <div
          className="absolute rounded-full blur-[5rem] animate-blob-drift"
          style={{
            top: "-3.75rem",
            left: "10%",
            width: "25rem",
            height: "25rem",
            backgroundColor: "var(--color-blob-blue)",
          }}
        />
        <div
          className="absolute rounded-full blur-[5rem] animate-blob-drift-delayed"
          style={{
            top: "30%",
            right: "-5rem",
            width: "21.875rem",
            height: "21.875rem",
            backgroundColor: "var(--color-blob-violet)",
            animationDelay: "5s",
          }}
        />
        <div
          className="absolute rounded-full blur-[5rem] animate-blob-drift"
          style={{
            bottom: "-2.5rem",
            left: "30%",
            width: "28.125rem",
            height: "28.125rem",
            backgroundColor: "var(--color-blob-teal)",
            animationDelay: "10s",
          }}
        />
        <div
          className="absolute rounded-full blur-[5rem] animate-blob-drift-delayed"
          style={{
            top: "50%",
            left: "-6.25rem",
            width: "18.75rem",
            height: "18.75rem",
            backgroundColor: "var(--color-blob-slate)",
            animationDelay: "15s",
          }}
        />
      </div>

      <div
        aria-hidden="true"
        className="fixed inset-0 pointer-events-none z-background [opacity:var(--grain-opacity)]"
      >
        <svg className="w-full h-full">
          <filter id={filterId}>
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.8"
              numOctaves={4}
              stitchTiles="stitch"
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter={`url(#${filterId})`} />
        </svg>
      </div>
    </>
  );
}
