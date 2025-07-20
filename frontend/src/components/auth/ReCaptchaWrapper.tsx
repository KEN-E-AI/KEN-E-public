import { ReactNode } from "react";
import { GoogleReCaptchaProvider } from "react-google-recaptcha-v3";

interface ReCaptchaWrapperProps {
  children: ReactNode;
}

// This wrapper ensures ReCAPTCHA provider is always available
// It reads the site key directly from environment variables
const ReCaptchaWrapper = ({ children }: ReCaptchaWrapperProps) => {
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY || "";

  console.log(
    "ReCaptchaWrapper initialized with site key:",
    siteKey ? siteKey.substring(0, 20) + "..." : "NO KEY",
  );

  if (!siteKey) {
    console.warn("ReCAPTCHA site key not found in environment variables");
    // Return children without provider - authentication will work without reCAPTCHA
    return <>{children}</>;
  }

  return (
    <GoogleReCaptchaProvider
      reCaptchaKey={siteKey}
      scriptProps={{
        async: true,
        defer: true,
        appendTo: "head",
      }}
    >
      {children}
    </GoogleReCaptchaProvider>
  );
};

export default ReCaptchaWrapper;
