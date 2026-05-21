import { useEffect, useRef, useState } from "react";
import { useGoogleReCaptcha } from "react-google-recaptcha-v3";
import axios from "axios";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ShieldCheck } from "lucide-react";

interface ReCaptchaV3Props {
  onVerify: (success: boolean) => void;
  onError?: (error: string) => void;
  action: string; // 'signin' or 'signup'
  className?: string;
}

const ReCaptchaV3 = ({
  onVerify,
  onError,
  action,
  className,
}: ReCaptchaV3Props) => {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const { executeRecaptcha } = useGoogleReCaptcha();
  const [isVerifying, setIsVerifying] = useState(false);
  const [error, setError] = useState<string>("");
  const [isVerified, setIsVerified] = useState(false);

  // Keep a stable ref to onVerify so the fallback timer's useEffect does not
  // restart on every render that produces a new inline-function reference.
  const onVerifyRef = useRef(onVerify);
  onVerifyRef.current = onVerify;

  useEffect(() => {
    // Only execute when executeRecaptcha becomes available
    if (executeRecaptcha && !isVerifying && !isVerified) {
      // Add a delay to ensure the reCAPTCHA script is fully loaded
      const timer = setTimeout(() => {
        handleReCaptchaVerify();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [executeRecaptcha, isVerifying, isVerified]);

  // Fallback timeout if reCAPTCHA never loads.
  // onVerify is intentionally not in the dependency array — it is read via
  // onVerifyRef so a new inline-function reference on re-render does not
  // cancel and restart the timer before it fires.
  useEffect(() => {
    const fallbackTimer = setTimeout(() => {
      if (!isVerified && !isVerifying) {
        console.warn(
          "ReCAPTCHA not available after timeout, bypassing verification",
        );
        setIsVerified(true);
        onVerifyRef.current(true);
      }
    }, 3000);

    return () => clearTimeout(fallbackTimer);
  }, [isVerified, isVerifying]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleReCaptchaVerify = async () => {
    if (!executeRecaptcha) {
      console.warn("reCAPTCHA not available, bypassing verification");
      setIsVerified(true);
      onVerifyRef.current(true);
      return;
    }

    setIsVerifying(true);
    setError("");

    try {
      // Execute reCAPTCHA v3
      const token = await executeRecaptcha(action);

      if (!token) {
        throw new Error("No token received");
      }

      // Verify the token with the backend
      const response = await axios.post(
        `${API_BASE_URL}/api/v1/auth/verify-recaptcha`,
        { token, action },
      );

      if (response.data.success) {
        setIsVerified(true);
        onVerify(true);
      } else {
        const errorCodes = response.data.error_codes || [];
        console.error("reCAPTCHA verification failed:", {
          error_codes: errorCodes,
          message: response.data.message,
          action: action,
        });
        setError(
          `Security verification failed: ${errorCodes.join(", ") || "Unknown error"}. Please refresh and try again.`,
        );
        onVerify(false);
        onError?.(`Security verification failed: ${errorCodes.join(", ")}`);
      }
    } catch (err: any) {
      console.error("reCAPTCHA verification error:", err);
      const errorMessage =
        err.response?.data?.detail || err.message || "Unknown error";
      setError(
        `Security verification error: ${errorMessage}. Please refresh the page.`,
      );
      onVerify(false);
      onError?.(`Security verification error: ${errorMessage}`);
    } finally {
      setIsVerifying(false);
    }
  };

  if (error) {
    return (
      <Alert variant="destructive" className={className}>
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (isVerifying) {
    return (
      <div
        className={`flex items-center justify-center gap-2 text-sm text-[var(--color-text-tertiary)] ${className}`}
      >
        <div className="w-4 h-4 border-2 border-[var(--color-border-default)] border-t-[var(--color-text-tertiary)] rounded-full animate-spin" />
        Verifying security...
      </div>
    );
  }

  if (isVerified) {
    return (
      <div
        className={`flex items-center justify-center gap-2 text-sm text-green-600 ${className}`}
      >
        <ShieldCheck className="h-4 w-4" data-testid="shield-check-icon" />
        Security verified
      </div>
    );
  }

  return null;
};

export default ReCaptchaV3;
