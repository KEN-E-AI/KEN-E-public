import { ReactNode, useEffect, useState } from "react";
import { GoogleReCaptchaProvider } from "react-google-recaptcha-v3";

interface ReCaptchaWrapperProps {
  children: ReactNode;
}

// This wrapper ensures ReCAPTCHA provider is always available
// It reads the site key directly from environment variables
const ReCaptchaWrapper = ({ children }: ReCaptchaWrapperProps) => {
  const [isReady, setIsReady] = useState(false);
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY || "";

  useEffect(() => {
    // Small delay to ensure proper initialization after page refresh
    const timer = setTimeout(() => {
      setIsReady(true);
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  console.log(
    "ReCaptchaWrapper initialized with site key:",
    siteKey ? siteKey.substring(0, 20) + "..." : "NO KEY",
  );

  if (!siteKey) {
    console.warn("ReCAPTCHA site key not found in environment variables");
    // Return children without provider - authentication will work without reCAPTCHA
    return <>{children}</>;
  }

  // Always wrap with provider, but only render children when ready
  // This ensures the provider context is available when useGoogleReCaptcha hook is called
  return (
    <GoogleReCaptchaProvider
      reCaptchaKey={siteKey}
      scriptProps={{
        async: true,
        defer: true,
        appendTo: "head",
      }}
      container={{ parameters: { theme: "light" } }}
    >
      {isReady ? children : <div>Loading...</div>}
    </GoogleReCaptchaProvider>
  );
};

export default ReCaptchaWrapper;
