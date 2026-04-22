/**
 * BackgroundEffects - Ambient visual effects for KEN-E design system
 * Includes: color blobs and grain texture overlay
 */

export function BackgroundEffects() {
  return (
    <>
      {/* Background Blobs */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden" style={{ zIndex: 'var(--z-background)' }}>
        {/* Blob 1 - Blue (top left) */}
        <div 
          className="absolute rounded-full blur-[80px] animate-blob-drift"
          style={{
            top: '-60px',
            left: '10%',
            width: '400px',
            height: '400px',
            backgroundColor: 'var(--color-blob-blue)',
          }}
        />
        
        {/* Blob 2 - Violet (top right) */}
        <div 
          className="absolute rounded-full blur-[80px] animate-blob-drift-delayed"
          style={{
            top: '30%',
            right: '-80px',
            width: '350px',
            height: '350px',
            backgroundColor: 'var(--color-blob-violet)',
            animationDelay: '5s',
          }}
        />
        
        {/* Blob 3 - Teal (bottom left) */}
        <div 
          className="absolute rounded-full blur-[80px] animate-blob-drift"
          style={{
            bottom: '-40px',
            left: '30%',
            width: '450px',
            height: '450px',
            backgroundColor: 'var(--color-blob-teal)',
            animationDelay: '10s',
          }}
        />
        
        {/* Blob 4 - Slate (middle left) */}
        <div 
          className="absolute rounded-full blur-[80px] animate-blob-drift-delayed"
          style={{
            top: '50%',
            left: '-100px',
            width: '300px',
            height: '300px',
            backgroundColor: 'var(--color-blob-slate)',
            animationDelay: '15s',
          }}
        />
      </div>

      {/* Grain Texture Overlay */}
      <div 
        className="fixed inset-0 pointer-events-none"
        style={{ 
          zIndex: 'var(--z-background)',
          opacity: 'var(--grain-opacity)',
        }}
      >
        <svg className="w-full h-full">
          <filter id="grain">
            <feTurbulence 
              type="fractalNoise" 
              baseFrequency="0.8" 
              numOctaves="4" 
              stitchTiles="stitch"
            />
            <feColorMatrix type="saturate" values="0"/>
          </filter>
          <rect width="100%" height="100%" filter="url(#grain)" />
        </svg>
      </div>

      {/* Animation keyframes */}
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