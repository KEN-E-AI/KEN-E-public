import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { applyActionCode, checkActionCode } from "firebase/auth";
import { auth } from "@/lib/firebase";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, CheckCircle, XCircle, Mail, ArrowRight } from "lucide-react";

type ActionMode = "verifyEmail" | "resetPassword" | "recoverEmail";

interface ActionCodeInfo {
  data: {
    email?: string;
  };
}

const EmailActionHandler = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [email, setEmail] = useState<string | null>(null);

  const mode = searchParams.get("mode") as ActionMode | null;
  const oobCode = searchParams.get("oobCode");
  const continueUrl = searchParams.get("continueUrl");

  // Pre-validate continueUrl: only allow same-origin redirects
  const safeContinueUrl = (() => {
    if (!continueUrl) return null;
    try {
      const u = new URL(continueUrl);
      return u.origin === window.location.origin ? continueUrl : null;
    } catch {
      return null;
    }
  })();

  useEffect(() => {
    handleAction();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAction = async () => {
    if (!mode || !oobCode) {
      setError(
        "Invalid verification link. Please request a new verification email.",
      );
      setIsLoading(false);
      return;
    }

    if (mode !== "verifyEmail") {
      setError(
        "Invalid verification link. Please request a new verification email.",
      );
      setIsLoading(false);
      return;
    }

    try {
      // Check the action code first to get the email and metadata
      const actionCodeInfo = (await checkActionCode(
        auth,
        oobCode,
      )) as ActionCodeInfo;
      const userEmail = actionCodeInfo.data.email;

      if (userEmail) {
        setEmail(userEmail);
      }

      // Apply the action code to verify the email
      await applyActionCode(auth, oobCode);

      setSuccess(true);
      setError(null);
    } catch (error: any) {
      let errorMessage = "Failed to verify email. ";

      switch (error.code) {
        case "auth/expired-action-code":
          errorMessage +=
            "The verification link has expired. Please request a new one.";
          break;
        case "auth/invalid-action-code":
          errorMessage +=
            "The verification link is invalid. Please request a new one.";
          break;
        case "auth/user-disabled":
          errorMessage +=
            "This account has been disabled. Please contact support.";
          break;
        case "auth/user-not-found":
          errorMessage += "No user found for this verification link.";
          break;
        default:
          errorMessage +=
            "Please try again or request a new verification link.";
      }

      setError(errorMessage);
      setSuccess(false);
    } finally {
      setIsLoading(false);
    }
  };

  const handleContinue = () => {
    if (safeContinueUrl) {
      window.location.href = safeContinueUrl;
      return;
    }
    navigate("/", { replace: true });
  };

  const handleSignIn = () => {
    navigate("/", { replace: true });
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] w-full max-w-md p-12 shadow-lg">
          <div className="flex flex-col items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-[var(--color-violet-500)] mb-4" />
            <p className="text-muted-foreground">Verifying your email...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="relative inline-block mb-4">
            <div
              className="size-16 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center mx-auto"
              style={{ boxShadow: "var(--shadow-color-violet)" }}
            >
              <Mail className="h-8 w-8 text-white" />
            </div>
          </div>
          <h1 className="mb-2">Email Verification</h1>
        </div>

        <Card className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] shadow-lg">
          <CardHeader>
            <h2
              data-slot="card-title"
              className="leading-none font-bold text-[var(--text-heading-md)] text-center"
              style={{ fontFamily: "var(--font-display)" }}
            >
              {success ? "Email Verified!" : "Verification Failed"}
            </h2>
          </CardHeader>
          <CardContent className="space-y-4">
            {success ? (
              <>
                <Alert className="border-green-200 bg-green-50">
                  <CheckCircle className="h-4 w-4 text-green-600" />
                  <AlertTitle className="text-green-800">Success!</AlertTitle>
                  <AlertDescription className="text-green-700">
                    {email ? (
                      <>
                        Your email <strong>{email}</strong> has been
                        successfully verified.
                      </>
                    ) : (
                      "Your email has been successfully verified."
                    )}
                  </AlertDescription>
                </Alert>

                <div className="text-center text-sm text-muted-foreground">
                  <p>
                    You can now sign in to your account with your verified
                    email.
                  </p>
                </div>

                <div className="flex flex-col gap-2">
                  <Button onClick={handleSignIn} className="w-full">
                    <ArrowRight className="h-4 w-4 mr-2" />
                    Go to Sign In
                  </Button>

                  {safeContinueUrl && (
                    <Button
                      variant="outline"
                      onClick={handleContinue}
                      className="w-full"
                    >
                      Continue
                    </Button>
                  )}
                </div>
              </>
            ) : (
              <>
                <Alert variant="destructive">
                  <XCircle className="h-4 w-4" />
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>

                <div className="text-center text-sm text-muted-foreground">
                  <p>
                    If you continue to have issues, please sign in and request a
                    new verification email.
                  </p>
                </div>

                <Button
                  onClick={handleSignIn}
                  variant="outline"
                  className="w-full"
                >
                  Go to Sign In
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default EmailActionHandler;
