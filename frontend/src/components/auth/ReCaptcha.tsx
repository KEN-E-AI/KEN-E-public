import { useEffect, useRef, useState } from "react";
import ReCAPTCHA from "react-google-recaptcha";
import axios from "axios";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";

interface ReCaptchaProps {
  onVerify: (success: boolean) => void;
  onError?: (error: string) => void;
  className?: string;
}

const ReCaptcha = ({ onVerify, onError, className }: ReCaptchaProps) => {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY;
  const recaptchaRef = useRef<ReCAPTCHA>(null);
  const [siteKey, setSiteKey] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string>("");

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
          setLoading(false);
        } catch (err) {
          console.error("Failed to fetch reCAPTCHA site key:", err);
          setError("Failed to load reCAPTCHA. Please refresh the page.");
          setLoading(false);
          onError?.("Failed to load reCAPTCHA");
        }
      };

      fetchSiteKey();
    }
  }, [API_BASE_URL, RECAPTCHA_SITE_KEY, onError]);

  const handleCaptchaChange = async (token: string | null) => {
    if (!token) {
      onVerify(false);
      return;
    }

    try {
      // Verify the token with the backend
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/auth/verify-recaptcha`,
        { token },
      );

      if (response.data.success) {
        onVerify(true);
      } else {
        setError("reCAPTCHA verification failed. Please try again.");
        onVerify(false);
        onError?.("reCAPTCHA verification failed");
        // Reset the reCAPTCHA
        recaptchaRef.current?.reset();
      }
    } catch (err) {
      console.error("reCAPTCHA verification error:", err);
      setError("Verification error. Please try again.");
      onVerify(false);
      onError?.("Verification error");
      // Reset the reCAPTCHA
      recaptchaRef.current?.reset();
    }
  };

  const handleCaptchaExpired = () => {
    onVerify(false);
    setError("reCAPTCHA expired. Please complete it again.");
  };

  const handleCaptchaError = () => {
    setError("reCAPTCHA error. Please refresh the page.");
    onVerify(false);
    onError?.("reCAPTCHA error");
  };

  if (loading) {
    return (
      <div className="flex justify-center py-4">
        <div className="text-sm text-[var(--color-text-tertiary)]">
          Loading security check...
        </div>
      </div>
    );
  }

  if (!siteKey) {
    return (
      <Alert variant="destructive" className="my-4">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>
          Security verification unavailable. Please contact support.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className={className}>
      {error && (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <div className="flex justify-center">
        <ReCAPTCHA
          ref={recaptchaRef}
          sitekey={siteKey}
          onChange={handleCaptchaChange}
          onExpired={handleCaptchaExpired}
          onErrored={handleCaptchaError}
        />
      </div>
    </div>
  );
};

export default ReCaptcha;
