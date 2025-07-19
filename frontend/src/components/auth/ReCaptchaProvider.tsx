import { GoogleReCaptchaProvider } from "react-google-recaptcha-v3";
import { ReactNode, useEffect, useState } from "react";
import axios from "axios";

interface ReCaptchaProviderProps {
  children: ReactNode;
}

const ReCaptchaProvider = ({ children }: ReCaptchaProviderProps) => {
  const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY;
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const [siteKey, setSiteKey] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Use environment variable if available, otherwise fetch from backend
    if (RECAPTCHA_SITE_KEY) {
      setSiteKey(RECAPTCHA_SITE_KEY);
      setLoading(false);
    } else {
      // Fetch the site key from the backend
      const fetchSiteKey = async () => {
        try {
          const response = await axios.get(
            `${API_BASE_URL}/api/v1/auth/recaptcha-site-key`,
          );
          setSiteKey(response.data.site_key);
        } catch (err) {
          // Silently fail - component will render without provider
        } finally {
          setLoading(false);
        }
      };

      fetchSiteKey();
    }
  }, [API_BASE_URL, RECAPTCHA_SITE_KEY]);

  if (loading || !siteKey) {
    // Return children without provider if no key available
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

export default ReCaptchaProvider;
