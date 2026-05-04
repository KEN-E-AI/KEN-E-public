import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { applyActionCode, checkActionCode } from "firebase/auth";
import { auth } from "@/lib/firebase";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Loader2,
  CheckCircle,
  XCircle,
  Mail,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";

type ActionMode = "verifyEmail" | "resetPassword" | "recoverEmail";

interface ActionCodeInfo {
  data: {
    email?: string;
  };
}

const EmailActionHandler = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [email, setEmail] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const mode = searchParams.get("mode") as ActionMode | null;
  const oobCode = searchParams.get("oobCode");
  const continueUrl = searchParams.get("continueUrl");

  // Helper function to find user by email
  const findUserByEmail = async (userEmail: string) => {
    const queryResponse = await axios.post(
      `${API_BASE_URL}/api/v1/firestore/documents/query`,
      {
        account_id: "system", // Using system as account_id for query
        collection: "users",
        field: "profile.email",
        operator: "==",
        value: userEmail,
      },
    );

    if (
      queryResponse.data.documents &&
      queryResponse.data.documents.length > 0
    ) {
      return queryResponse.data.documents[0];
    }
    return null;
  };

  // Helper function to update user's email verification status
  const updateUserEmailVerified = async (userId: string) => {
    // Update email_verified field
    await axios.put(
      `${API_BASE_URL}/api/v1/firestore/documents/users/${userId}?account_id=${userId}`,
      {
        update: {
          field: "profile.email_verified",
          operator: "set",
          value: true,
        },
      },
    );

    // Update lastUpdated timestamp
    await axios.put(
      `${API_BASE_URL}/api/v1/firestore/documents/users/${userId}?account_id=${userId}`,
      {
        update: {
          field: "metadata.lastUpdated",
          operator: "set",
          value: new Date().toISOString(),
        },
      },
    );
  };

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
        `This page only handles email verification. Mode "${mode}" is not supported.`,
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

      // The email is now verified in Firebase Auth
      // Update Firestore to reflect this change
      if (userEmail) {
        try {
          const userDoc = await findUserByEmail(userEmail);

          if (userDoc) {
            await updateUserEmailVerified(userDoc.id);
            // Email verified successfully with no warnings
            setWarning(null);
          } else {
            // Email is verified in Firebase but user not found in Firestore
            setWarning(
              "Your email has been verified, but we couldn't update your profile. " +
                "Please sign in to complete the verification process.",
            );
          }
        } catch (apiError) {
          // Email is verified in Firebase but Firestore update failed
          setWarning(
            "Your email has been verified, but we couldn't update your profile. " +
              "Please sign in to complete the verification process.",
          );
        }
      }

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
    if (continueUrl) {
      try {
        const url = new URL(continueUrl);
        if (url.origin === window.location.origin) {
          window.location.href = continueUrl;
          return;
        }
      } catch {
        // invalid URL — fall through to default navigate
      }
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
            <CardTitle className="text-center">
              {success ? "Email Verified!" : "Verification Failed"}
            </CardTitle>
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

                {warning && (
                  <Alert className="border-yellow-200 bg-yellow-50">
                    <AlertTriangle className="h-4 w-4 text-yellow-600" />
                    <AlertTitle className="text-yellow-800">Note</AlertTitle>
                    <AlertDescription className="text-yellow-700">
                      {warning}
                    </AlertDescription>
                  </Alert>
                )}

                {!warning && (
                  <div className="text-center text-sm text-muted-foreground">
                    <p>
                      You can now sign in to your account with your verified
                      email.
                    </p>
                  </div>
                )}

                <div className="flex flex-col gap-2">
                  <Button onClick={handleSignIn} className="w-full">
                    <ArrowRight className="h-4 w-4 mr-2" />
                    Go to Sign In
                  </Button>

                  {continueUrl && (
                    <Button
                      variant="outline"
                      onClick={handleContinue}
                      className="w-full"
                    >
                      Continue to {new URL(continueUrl).hostname}
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
