import { useEffect, useState } from "react";
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

  useEffect(() => {
    // Automatically execute reCAPTCHA when component mounts
    // Add a small delay to ensure provider is ready
    const timer = setTimeout(() => {
      if (executeRecaptcha) {
        handleReCaptchaVerify();
      } else {
        // If reCAPTCHA is not available, consider it verified to not block auth
        console.warn("ReCAPTCHA not available, bypassing verification");
        setIsVerified(true);
        onVerify(true);
      }
    }, 200);
    
    return () => clearTimeout(timer);
  }, [executeRecaptcha]);

  const handleReCaptchaVerify = async () => {
    if (!executeRecaptcha) {
      console.warn("reCAPTCHA not available, bypassing verification");
      setIsVerified(true);
      onVerify(true);
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
        className={`flex items-center justify-center gap-2 text-sm text-gray-500 ${className}`}
      >
        <div className="w-4 h-4 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
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
