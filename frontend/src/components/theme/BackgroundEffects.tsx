import { useState, useEffect } from "react";

export function BackgroundEffects() {
  const [reducedMotion, setReducedMotion] = useState(false);

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
        data-testid="bg-static"
        style={{
          position: "fixed",
          inset: 0,
          pointerEvents: "none",
          zIndex: "var(--z-background)" as string,
          background:
            "linear-gradient(135deg, var(--color-blob-blue), var(--color-blob-violet), var(--color-blob-teal), var(--color-blob-slate))",
        }}
      />
    );
  }

  return (
    <>
      <div
        data-testid="bg-blobs"
        className="fixed inset-0 pointer-events-none overflow-hidden"
        style={{ zIndex: "var(--z-background)" as string }}
      >
        <div
          className="absolute rounded-full blur-[80px] animate-blob-drift"
          style={{
            top: "-60px",
            left: "10%",
            width: "400px",
            height: "400px",
            backgroundColor: "var(--color-blob-blue)",
          }}
        />
        <div
          className="absolute rounded-full blur-[80px] animate-blob-drift-delayed"
          style={{
            top: "30%",
            right: "-80px",
            width: "350px",
            height: "350px",
            backgroundColor: "var(--color-blob-violet)",
            animationDelay: "5s",
          }}
        />
        <div
          className="absolute rounded-full blur-[80px] animate-blob-drift"
          style={{
            bottom: "-40px",
            left: "30%",
            width: "450px",
            height: "450px",
            backgroundColor: "var(--color-blob-teal)",
            animationDelay: "10s",
          }}
        />
        <div
          className="absolute rounded-full blur-[80px] animate-blob-drift-delayed"
          style={{
            top: "50%",
            left: "-100px",
            width: "300px",
            height: "300px",
            backgroundColor: "var(--color-blob-slate)",
            animationDelay: "15s",
          }}
        />
      </div>

      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          zIndex: "var(--z-background)" as string,
          opacity: "var(--grain-opacity)" as string,
        }}
      >
        <svg className="w-full h-full">
          <filter id="grain">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.8"
              numOctaves={4}
              stitchTiles="stitch"
            />
            <feColorMatrix type="saturate" values="0" />
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </div>

      <style>{`
        @keyframes blobDrift {
          0%, 100% { transform: translate(0, 0); }
          33% { transform: translate(15px, -10px); }
          66% { transform: translate(-10px, 15px); }
        }

        @keyframes blobDriftDelayed {
          0%, 100% { transform: translate(0, 0); }
          33% { transform: translate(-15px, 10px); }
          66% { transform: translate(10px, -15px); }
        }

        .animate-blob-drift {
          animation: blobDrift 20s ease-in-out infinite;
        }

        .animate-blob-drift-delayed {
          animation: blobDriftDelayed 25s ease-in-out infinite;
        }
      `}</style>
    </>
  );
}
