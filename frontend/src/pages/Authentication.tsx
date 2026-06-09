import { useState, useEffect } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  getRedirectResult,
  sendEmailVerification,
} from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { useAuth } from "@/contexts/AuthContext";
import { verifyInvitationToken, type Invitation } from "@/data/teamApi";
import {
  getSignupPolicy,
  validateAccessCode,
  EARLY_RELEASE_CODE_STORAGE_KEY,
} from "@/data/earlyReleaseApi";
import type {
  FirebaseUser,
  FirestoreUserData,
  UserDataResponse,
  NotificationSettings,
  SecuritySettings,
} from "@/types/auth";
import { toUserId } from "@/lib/branded-types";
import type {
  NotificationSetting,
  SecuritySetting,
} from "@/data/userSettingsData";
import ReCaptchaWrapper from "@/components/auth/ReCaptchaWrapper";
import ReCaptchaV3 from "@/components/auth/ReCaptchaV3";
import ReCaptchaErrorBoundary from "@/components/auth/ReCaptchaErrorBoundary";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { SignInView } from "./auth/SignInView";
import { CreateAccountView } from "./auth/CreateAccountView";
import { EmailVerificationView } from "./auth/EmailVerificationView";

type View = "signin" | "signup" | "email-verification";

const SIGN_UP_PATHS = new Set([
  "/signup",
  "/sign-up",
  "/create-account",
  "/auth/signup",
]);

interface AuthenticationProps {
  onAuthenticated: () => void;
}

const Authentication = ({ onAuthenticated }: AuthenticationProps) => {
  const { login, setNotificationSettings, setSecuritySettings } = useAuth();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [invitationData, setInvitationData] = useState<Invitation | null>(null);
  const [invitationError, setInvitationError] = useState<string | null>(null);
  const [signInData, setSignInData] = useState({
    email: "",
    password: "",
    rememberMe: false,
  });
  const [signUpData, setSignUpData] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
    agreeToTerms: false,
  });
  const [signUpFieldErrors, setSignUpFieldErrors] = useState<
    Record<string, string>
  >({});
  const [isSignInCaptchaVerified, setIsSignInCaptchaVerified] = useState(false);
  const [isSignUpCaptchaVerified, setIsSignUpCaptchaVerified] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [resendStatus, setResendStatus] = useState<
    "idle" | "sending" | "sent" | "error"
  >("idle");
  const [countdown, setCountdown] = useState(0);

  // Early Release gate state
  const [inviteOnly, setInviteOnly] = useState(false);
  const [accessCode, setAccessCode] = useState("");
  const [accessCodeStatus, setAccessCodeStatus] = useState<
    "idle" | "validating" | "valid" | "invalid"
  >("idle");
  const [accessCodeError, setAccessCodeError] = useState<string | null>(null);
  const [lastValidatedCode, setLastValidatedCode] = useState("");

  // Derive which view to show from the URL pathname (exact-match to avoid false positives)
  const pathname = location.pathname;
  const isSignUp = SIGN_UP_PATHS.has(pathname);
  const isVerifyEmail = pathname === "/verify-email";

  const [internalView, setInternalView] = useState<View | null>(null);

  // Reset internalView override when the user navigates to a different page
  useEffect(() => {
    setInternalView(null);
  }, [pathname]);

  const activeView: View = (() => {
    if (internalView === "email-verification") return "email-verification";
    if (isVerifyEmail) return "email-verification";
    if (isSignUp) return "signup";
    return "signin";
  })();

  const invitationToken = searchParams.get("invitation");

  // No client-side email-domain exemption: signup is pre-auth, so the client
  // cannot know whether the caller holds the super_admin role. The server gate
  // (onboarding_gate.py) bypasses on the super_admin role only — an "@ken-e.ai"
  // email is not a trustworthy signal because Firebase signup is open. Staff
  // therefore onboard via the shared code, an invitation, or (if super-admin)
  // by entering the code at signup and passing the server gate regardless.
  // See DM-PRD-11 §4.3 and DESIGN-REVIEW-LOG (2026-06-08).
  const requiresAccessCode = inviteOnly && !invitationToken;

  // Fetch signup policy on signup-view mount
  useEffect(() => {
    if (!isSignUp) return;
    let mounted = true;
    getSignupPolicy()
      .then((policy) => {
        if (mounted) setInviteOnly(policy.invite_only);
      })
      .catch((err) => {
        console.warn(
          "[earlyRelease] Failed to fetch signup policy; defaulting to open",
          err,
        );
      });
    return () => {
      mounted = false;
    };
  }, [isSignUp]);

  // Reset code status when the gate transitions off (flag turns off, or an
  // invitation token appears).
  useEffect(() => {
    if (!requiresAccessCode) {
      setAccessCodeStatus("idle");
      setAccessCodeError(null);
      setLastValidatedCode("");
      sessionStorage.removeItem(EARLY_RELEASE_CODE_STORAGE_KEY);
    }
  }, [requiresAccessCode]);

  // Countdown timer for resend cooldown
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }
  }, [countdown]);

  useEffect(() => {
    // Sign out any existing Firebase user when landing on auth page
    auth.signOut().catch((error) => {
      console.error("Error signing out:", error);
    });

    // Check for redirect result (in case we're coming back from Google OAuth)
    getRedirectResult(auth)
      .then((result) => {
        if (result && result.user) {
          handleGoogleSignInSuccess(result.user as FirebaseUser);
        }
      })
      .catch((error) => {
        console.error("Redirect result error:", error);
        if (error.code) {
          setErrorMessage("Failed to sign in with Google. Please try again.");
        }
      });
  }, []);

  useEffect(() => {
    let mounted = true;

    const verifyInvitation = async () => {
      if (!invitationToken) return;

      try {
        const invitation = await verifyInvitationToken(invitationToken);

        if (mounted) {
          setInvitationData(invitation);
          setSignInData((prev) => ({ ...prev, email: invitation.email }));
          setSignUpData((prev) => ({ ...prev, email: invitation.email }));
        }
      } catch (error: any) {
        if (mounted) {
          console.error("[Authentication] Error verifying invitation:", error);
          if (error.response?.status === 404) {
            setInvitationError("Invalid invitation link");
          } else if (error.response?.status === 400) {
            const detail = error.response.data?.detail;
            if (detail?.includes("expired")) {
              setInvitationError("This invitation has expired");
            } else if (detail?.includes("already been accepted")) {
              setInvitationError("This invitation has already been accepted");
            } else {
              setInvitationError(detail || "Invalid invitation");
            }
          } else {
            setInvitationError("Failed to verify invitation");
          }
        }
      }
    };

    verifyInvitation();

    return () => {
      mounted = false;
    };
  }, [invitationToken]);

  const fetchUserDataAndSettings = async (
    uid: string,
  ): Promise<UserDataResponse> => {
    const [userRes, notificationsRes, securityRes] = await Promise.all([
      api.get<{ data: FirestoreUserData }>(
        `/api/v1/firestore/documents/users/${uid}`,
      ),
      api.post<{ documents: Array<{ data: NotificationSettings }> }>(
        `/api/v1/firestore/documents/query`,
        {
          account_id: uid,
          collection: `users/${uid}/notifications`,
          limit: 20,
        },
      ),
      api.post<{ documents: Array<{ data: SecuritySettings }> }>(
        `/api/v1/firestore/documents/query`,
        {
          account_id: uid,
          collection: `users/${uid}/security`,
          limit: 20,
        },
      ),
    ]);

    return {
      userData: userRes.data.data,
      notificationsData: notificationsRes.data.documents || [],
      securityData: securityRes.data.documents || [],
    };
  };

  const processUserLogin = (
    firebaseUser: FirebaseUser,
    firestoreData: FirestoreUserData,
    notificationsData: Array<{ data: NotificationSettings }>,
    securityData: Array<{ data: SecuritySettings }>,
    login: (user: any) => void,
    setNotificationSettings: (settings: NotificationSetting[]) => void,
    setSecuritySettings: (settings: SecuritySetting[]) => void,
  ): void => {
    login({
      id: toUserId(firebaseUser.uid),
      email: firestoreData.profile?.email || firebaseUser.email || "",
      firstName: firestoreData.profile?.first_name || "",
      lastName: firestoreData.profile?.last_name || "",
      jobTitle: firestoreData.profile?.job_title || "",
      permissions: firestoreData.permissions || {
        organizations: {},
        accounts: {},
      },
      preferences: firestoreData.preferences || {},
    });

    if (notificationsData.length > 0) {
      const settings: NotificationSetting[] = notificationsData.map(
        (item) =>
          ({
            ...item.data,
            id: "default",
          }) as NotificationSetting,
      );
      setNotificationSettings(settings);
    }

    if (securityData.length > 0) {
      const settings: SecuritySetting[] = securityData.map(
        (item) =>
          ({
            ...item.data,
            id: "default",
          }) as SecuritySetting,
      );
      setSecuritySettings(settings);
    }
  };

  const createUserInFirestore = async (
    firebaseUser: FirebaseUser,
  ): Promise<FirestoreUserData> => {
    const displayName = firebaseUser.displayName || "";
    const [firstName, ...lastNameParts] = displayName.split(" ");
    const lastName = lastNameParts.join(" ");

    const newUserData: FirestoreUserData = {
      profile: {
        email: firebaseUser.email || "",
        first_name: firstName || "",
        last_name: lastName || "",
        job_title: "",
        uid: firebaseUser.uid,
      },
      permissions: {
        organizations: {},
        accounts: {},
        account_permissions: {},
      },
      preferences: {},
      metadata: {
        createdAt: new Date().toISOString(),
        lastUpdated: new Date().toISOString(),
      },
    };

    // `permissions` is intentionally NOT sent: the API rejects client writes
    // of permissions to a user doc (DM-81 write-path hardening). It is a
    // server-owned field, populated by the grant/revoke and invitation flows.
    await api.post(`/api/v1/firestore/documents`, {
      account_id: firebaseUser.uid,
      collection: "users",
      document_id: firebaseUser.uid,
      data: {
        profile: newUserData.profile,
        preferences: newUserData.preferences,
        metadata: newUserData.metadata,
      },
    });

    return newUserData;
  };

  const handleApiError = (error: unknown): string => {
    if (!error || typeof error !== "object" || !("response" in error)) {
      throw error;
    }

    const axiosError = error as any;
    switch (axiosError.response?.status) {
      case 404:
        return "";
      case 403:
        return "Access denied. Please contact support.";
      case 500:
        return "Server error. Please try again later.";
      default:
        return "Failed to retrieve user data. Please try again.";
    }
  };

  const handleAccessCodeChange = (value: string) => {
    setAccessCode(value);
    if (value.trim() !== lastValidatedCode) {
      setAccessCodeStatus("idle");
      setAccessCodeError(null);
    }
  };

  const handleAccessCodeBlur = async () => {
    const trimmed = accessCode.trim();
    if (!trimmed || trimmed === lastValidatedCode) return;

    setAccessCodeStatus("validating");
    setAccessCodeError(null);

    try {
      const { valid } = await validateAccessCode(trimmed);
      if (valid) {
        setAccessCodeStatus("valid");
        setLastValidatedCode(trimmed);
        sessionStorage.setItem(EARLY_RELEASE_CODE_STORAGE_KEY, trimmed);
      } else {
        setAccessCodeStatus("invalid");
        setAccessCodeError("Invalid Early Release code");
      }
    } catch {
      setAccessCodeStatus("invalid");
      setAccessCodeError("Couldn't validate — please try again");
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    if (!isSignInCaptchaVerified) {
      setErrorMessage(
        "Security verification in progress. Please wait a moment.",
      );
      setIsLoading(false);
      return;
    }

    try {
      const result = await signInWithEmailAndPassword(
        auth,
        signInData.email,
        signInData.password,
      );
      const firebaseUser = result.user;

      if (!firebaseUser.emailVerified) {
        setErrorMessage(
          "Please verify your email before signing in. Check your inbox for the verification link.",
        );
        await auth.signOut();
        return;
      }

      const { userData, notificationsData, securityData } =
        await fetchUserDataAndSettings(firebaseUser.uid);

      if (
        userData.profile &&
        !(userData.profile as any).email_verified &&
        firebaseUser.emailVerified
      ) {
        await api.put(
          `/api/v1/firestore/documents/users/${firebaseUser.uid}?account_id=${firebaseUser.uid}`,
          {
            update: {
              field: "profile.email_verified",
              operator: "set",
              value: true,
            },
          },
        );
      }

      processUserLogin(
        firebaseUser as FirebaseUser,
        userData,
        notificationsData,
        securityData,
        login,
        setNotificationSettings,
        setSecuritySettings,
      );
      onAuthenticated();
    } catch (error: any) {
      switch (error.code) {
        case "auth/invalid-credential":
        case "auth/user-not-found":
        case "auth/wrong-password":
          setErrorMessage("Invalid email or password.");
          break;
        case "auth/too-many-requests":
          setErrorMessage("Too many failed attempts. Please try again later.");
          break;
        case "auth/user-disabled":
          setErrorMessage(
            "This account has been disabled. Please contact support.",
          );
          break;
        case "auth/network-request-failed":
          setErrorMessage("Network error. Please check your connection.");
          break;
        default:
          setErrorMessage("Failed to sign in. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");
    setSignUpFieldErrors({});

    if (requiresAccessCode && accessCodeStatus !== "valid") {
      setErrorMessage(
        "Please enter a valid Early Release code to create an account.",
      );
      setIsLoading(false);
      return;
    }

    if (signUpData.password !== signUpData.confirmPassword) {
      setSignUpFieldErrors({ confirmPassword: "Passwords do not match" });
      setIsLoading(false);
      return;
    }

    if (!signUpData.agreeToTerms) {
      setSignUpFieldErrors({
        terms: "You must agree to the Terms of Service to continue.",
      });
      setIsLoading(false);
      return;
    }

    if (!isSignUpCaptchaVerified) {
      setErrorMessage(
        "Security verification in progress. Please wait a moment.",
      );
      setIsLoading(false);
      return;
    }

    // Split single name field into first/last for backend payload
    const nameParts = signUpData.name.trim().split(" ");
    const firstName = nameParts[0] || "";
    const lastName = nameParts.slice(1).join(" ");

    try {
      const result = await createUserWithEmailAndPassword(
        auth,
        signUpData.email.trim(),
        signUpData.password,
      );
      const firebaseUser = result.user;

      await sendEmailVerification(firebaseUser);
      setVerificationEmail(signUpData.email.trim());

      // `permissions` is intentionally omitted: the API rejects client writes
      // of permissions to a user doc (DM-81 write-path hardening). It is a
      // server-owned field, populated by the grant/revoke and invitation flows.
      await api.post(`/api/v1/firestore/documents`, {
        account_id: firebaseUser.uid,
        collection: "users",
        document_id: firebaseUser.uid,
        data: {
          profile: {
            email: signUpData.email,
            first_name: firstName,
            last_name: lastName,
            job_title: "",
          },
          preferences: {
            language: "en",
            theme: "light",
            date_format: "mm-dd-yyyy",
          },
        },
      });

      await api.post(`/api/v1/firestore/documents`, {
        account_id: firebaseUser.uid,
        collection: `users/${firebaseUser.uid}/preferences`,
        document_id: "notifications",
        data: {
          categories: [
            "Data Quality Alert",
            "News & Press",
            "Industry News",
            "Competitor Activities",
            "Scheduled Report Status",
            "KPI Performance",
            "New Features",
          ],
          channels: ["ui"],
          updated_at: new Date().toISOString(),
        },
      });

      setErrorMessage("");
      setSignUpData({
        name: "",
        email: "",
        password: "",
        confirmPassword: "",
        agreeToTerms: false,
      });

      // Flip to email-verification view after successful signup
      setInternalView("email-verification");
    } catch (error: any) {
      console.error("Sign-up error:", error);
      switch (error.code) {
        case "auth/email-already-in-use":
          setErrorMessage("This email is already registered.");
          break;
        case "auth/weak-password":
          setErrorMessage("Password is too weak (min 6 characters).");
          break;
        default:
          setErrorMessage("Failed to create account. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendVerificationEmail = async () => {
    setResendStatus("sending");

    try {
      const currentUser = auth.currentUser;
      if (currentUser && !currentUser.emailVerified) {
        await sendEmailVerification(currentUser);
        setResendStatus("sent");
        setCountdown(60);
        setTimeout(() => setResendStatus("idle"), 3000);
      } else {
        setResendStatus("error");
      }
    } catch (error: any) {
      console.error("Resend verification error:", error);
      setResendStatus("error");
    }
  };

  const handleGoogleSignInSuccess = async (firebaseUser: FirebaseUser) => {
    try {
      const { userData, notificationsData, securityData } =
        await fetchUserDataAndSettings(firebaseUser.uid);

      processUserLogin(
        firebaseUser,
        userData,
        notificationsData,
        securityData,
        login,
        setNotificationSettings,
        setSecuritySettings,
      );
      onAuthenticated();
    } catch (error) {
      const errorMessage = handleApiError(error);

      if (errorMessage === "") {
        const newUserData = await createUserInFirestore(firebaseUser);

        await api.post(`/api/v1/firestore/documents`, {
          account_id: firebaseUser.uid,
          collection: `users/${firebaseUser.uid}/preferences`,
          document_id: "notifications",
          data: {
            categories: [
              "Data Quality Alert",
              "News & Press",
              "Industry News",
              "Competitor Activities",
              "Scheduled Report Status",
              "KPI Performance",
              "New Features",
            ],
            channels: ["ui"],
            updated_at: new Date().toISOString(),
          },
        });

        processUserLogin(
          firebaseUser,
          newUserData,
          [],
          [],
          login,
          setNotificationSettings,
          setSecuritySettings,
        );
        onAuthenticated();
      } else {
        console.error("API error during Google sign-in:", error);
        setErrorMessage(errorMessage);
      }
    }
  };

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setErrorMessage("");

    if (
      activeView === "signup" &&
      requiresAccessCode &&
      accessCodeStatus !== "valid"
    ) {
      setErrorMessage(
        "Please enter a valid Early Release code to create an account.",
      );
      setIsLoading(false);
      return;
    }

    try {
      const result = await signInWithPopup(auth, googleProvider);
      const firebaseUser = result.user as FirebaseUser;
      await handleGoogleSignInSuccess(firebaseUser);
    } catch (error: any) {
      console.error("Google sign-in error:", error);

      if (error.code === "auth/popup-closed-by-user") {
        setErrorMessage("Sign-in cancelled. Please try again.");
      } else if (error.code === "auth/popup-blocked") {
        setErrorMessage("Pop-up blocked. Please allow pop-ups for this site.");
      } else if (
        error.code === "auth/account-exists-with-different-credential"
      ) {
        setErrorMessage("An account already exists with this email address.");
      } else if (error.code === "auth/invalid-credential") {
        setErrorMessage("Invalid credentials. Please try again.");
      } else if (error.code === "auth/operation-not-allowed") {
        setErrorMessage(
          "Google sign-in is not enabled. Please contact support.",
        );
      } else if (error.code === "auth/network-request-failed") {
        setErrorMessage("Network error. Please check your connection.");
      } else if (!error.response) {
        setErrorMessage("Failed to sign in with Google. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  const recaptchaFallback = (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              ReCAPTCHA failed to load. Please refresh the page or try again
              later.
            </AlertDescription>
          </Alert>
        </div>
      </div>
    </div>
  );

  return (
    <ReCaptchaErrorBoundary fallback={recaptchaFallback}>
      <ReCaptchaWrapper>
        {activeView === "email-verification" ? (
          <EmailVerificationView
            email={verificationEmail}
            resendStatus={resendStatus}
            countdown={countdown}
            onResend={handleResendVerificationEmail}
          />
        ) : activeView === "signup" ? (
          <>
            <ReCaptchaV3
              onVerify={setIsSignUpCaptchaVerified}
              action="signup"
              className="hidden"
            />
            <CreateAccountView
              name={signUpData.name}
              email={signUpData.email}
              password={signUpData.password}
              confirmPassword={signUpData.confirmPassword}
              agreedToTerms={signUpData.agreeToTerms}
              isLoading={isLoading}
              errorMessage={errorMessage}
              fieldErrors={signUpFieldErrors}
              invitationToken={invitationToken}
              invitationData={invitationData}
              invitationError={invitationError}
              onNameChange={(v) => setSignUpData({ ...signUpData, name: v })}
              onEmailChange={(v) => setSignUpData({ ...signUpData, email: v })}
              onPasswordChange={(v) =>
                setSignUpData({ ...signUpData, password: v })
              }
              onConfirmPasswordChange={(v) =>
                setSignUpData({ ...signUpData, confirmPassword: v })
              }
              onAgreedToTermsChange={(v) =>
                setSignUpData({ ...signUpData, agreeToTerms: v })
              }
              onSubmit={handleSignUp}
              onGoogleSignUp={handleGoogleSignIn}
              requiresAccessCode={requiresAccessCode}
              accessCode={accessCode}
              accessCodeStatus={accessCodeStatus}
              accessCodeError={accessCodeError}
              onAccessCodeChange={handleAccessCodeChange}
              onAccessCodeBlur={handleAccessCodeBlur}
            />
          </>
        ) : (
          <>
            <ReCaptchaV3
              onVerify={setIsSignInCaptchaVerified}
              action="signin"
              className="hidden"
            />
            <SignInView
              email={signInData.email}
              password={signInData.password}
              rememberMe={signInData.rememberMe}
              isLoading={isLoading}
              isCaptchaVerified={isSignInCaptchaVerified}
              errorMessage={errorMessage}
              invitationToken={invitationToken}
              invitationData={invitationData}
              invitationError={invitationError}
              onEmailChange={(v) => setSignInData({ ...signInData, email: v })}
              onPasswordChange={(v) =>
                setSignInData({ ...signInData, password: v })
              }
              onRememberMeChange={(v) =>
                setSignInData({ ...signInData, rememberMe: v })
              }
              onSubmit={handleSignIn}
              onGoogleSignIn={handleGoogleSignIn}
            />
          </>
        )}
      </ReCaptchaWrapper>
    </ReCaptchaErrorBoundary>
  );
};

export default Authentication;
