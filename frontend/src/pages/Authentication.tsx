import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import api from "@/lib/api";
import {
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signInWithPopup,
  sendEmailVerification,
  type User as FirebaseAuthUser,
} from "firebase/auth";
import { auth, googleProvider } from "@/lib/firebase";
import { useAuth } from "@/contexts/AuthContext";
import { verifyInvitationToken, type Invitation } from "@/data/teamApi";
import type {
  FirebaseUser,
  FirestoreUserData,
  UserDataResponse,
  AuthHelperDeps,
  NotificationSettings,
  SecuritySettings,
} from "@/types/auth";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  User,
  Mail,
  Lock,
  Eye,
  EyeOff,
  ArrowRight,
  CheckCircle,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import ReCaptchaWrapper from "@/components/auth/ReCaptchaWrapper";
import ReCaptchaV3 from "@/components/auth/ReCaptchaV3";
import ReCaptchaErrorBoundary from "@/components/auth/ReCaptchaErrorBoundary";

interface AuthenticationProps {
  onAuthenticated: () => void;
}

const Authentication = ({ onAuthenticated }: AuthenticationProps) => {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
  const { login, setNotificationSettings, setSecuritySettings } = useAuth();
  const [searchParams] = useSearchParams();
  const [showPassword, setShowPassword] = useState(false);
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
    firstName: "",
    lastName: "",
    email: "",
    password: "",
    confirmPassword: "",
    agreeToTerms: false,
  });
  const [isSignInCaptchaVerified, setIsSignInCaptchaVerified] = useState(false);
  const [isSignUpCaptchaVerified, setIsSignUpCaptchaVerified] = useState(false);
  const [emailVerificationSent, setEmailVerificationSent] = useState(false);
  const [showResendButton, setShowResendButton] = useState(false);

  // Check for invitation token in URL
  const invitationToken = searchParams.get("invitation");

  useEffect(() => {
    // Sign out any existing Firebase user when landing on auth page
    auth.signOut().catch((error) => {
      console.error("Error signing out:", error);
    });
  }, []);

  useEffect(() => {
    let mounted = true;

    const verifyInvitation = async () => {
      if (!invitationToken) return;

      try {
        const invitation = await verifyInvitationToken(invitationToken);

        // Only update state if component is still mounted
        if (mounted) {
          setInvitationData(invitation);
          // Pre-fill email if available
          setSignInData((prev) => ({ ...prev, email: invitation.email }));
          setSignUpData((prev) => ({ ...prev, email: invitation.email }));
        }
      } catch (error: any) {
        // Only update state if component is still mounted
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

    // Cleanup function to prevent state updates after unmount
    return () => {
      mounted = false;
    };
  }, [invitationToken]);

  // Helper function to fetch user data and settings from Firestore
  const fetchUserDataAndSettings = async (
    uid: string,
    apiBaseUrl: string,
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

  // Helper function to process login after authentication
  const processUserLogin = (
    firebaseUser: FirebaseUser,
    firestoreData: FirestoreUserData,
    notificationsData: Array<{ data: NotificationSettings }>,
    securityData: Array<{ data: SecuritySettings }>,
    deps: AuthHelperDeps,
  ): void => {
    deps.login({
      id: firebaseUser.uid,
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

    // Set notification and security settings
    if (notificationsData.length > 0) {
      const notificationSettings = notificationsData[0].data;
      deps.setNotificationSettings(notificationSettings);
    }

    if (securityData.length > 0) {
      const securitySettings = securityData[0].data;
      deps.setSecuritySettings(securitySettings);
    }
  };

  // Helper function to create a new user in Firestore
  const createUserInFirestore = async (
    firebaseUser: FirebaseUser,
    apiBaseUrl: string,
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
      },
      preferences: {},
      metadata: {
        createdAt: new Date().toISOString(),
        lastUpdated: new Date().toISOString(),
      },
    };

    await api.post(`/api/v1/firestore/documents`, {
      account_id: firebaseUser.uid,
      collection: "users",
      document_id: firebaseUser.uid,
      data: newUserData,
    });

    return newUserData;
  };

  // Helper function to handle API errors
  const handleApiError = (error: unknown): string => {
    // Check if it's an axios-like error with a response property
    if (!error || typeof error !== "object" || !("response" in error)) {
      throw error;
    }

    const axiosError = error as any;
    switch (axiosError.response?.status) {
      case 404:
        return ""; // User doesn't exist, not an error
      case 403:
        return "Access denied. Please contact support.";
      case 500:
        return "Server error. Please try again later.";
      default:
        return "Failed to retrieve user data. Please try again.";
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    // Check if reCAPTCHA v3 has been verified
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

      // Check if email is verified
      if (!firebaseUser.emailVerified) {
        setErrorMessage(
          "Please verify your email before signing in. Check your inbox for the verification link.",
        );
        setShowResendButton(true);
        // Sign out the user since they can't access the app without verification
        await auth.signOut();
        return;
      }

      const { userData, notificationsData, securityData } =
        await fetchUserDataAndSettings(firebaseUser.uid, API_BASE_URL);

      // Update email verification status in Firestore if needed
      if (
        userData.profile &&
        !userData.profile.email_verified &&
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

      const authDeps: AuthHelperDeps = {
        apiBaseUrl: API_BASE_URL,
        login,
        setNotificationSettings,
        setSecuritySettings,
      };

      processUserLogin(
        firebaseUser as FirebaseUser,
        userData,
        notificationsData,
        securityData,
        authDeps,
      );
      onAuthenticated();
    } catch (error: any) {
      // handle errors...
    } finally {
      setIsLoading(false);
    }
  };

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage("");

    // Check if reCAPTCHA v3 has been verified
    if (!isSignUpCaptchaVerified) {
      setErrorMessage(
        "Security verification in progress. Please wait a moment.",
      );
      setIsLoading(false);
      return;
    }

    if (signUpData.password !== signUpData.confirmPassword) {
      setErrorMessage("Passwords do not match.");
      setIsLoading(false);
      return;
    }

    try {
      console.log("Attempting signup with email:", signUpData.email);
      console.log("Email validation check:", {
        email: signUpData.email,
        isValidFormat: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(signUpData.email),
        trimmedEmail: signUpData.email.trim(),
        length: signUpData.email.length,
      });

      const result = await createUserWithEmailAndPassword(
        auth,
        signUpData.email.trim(),
        signUpData.password,
      );
      const firebaseUser = result.user;

      // Send email verification
      await sendEmailVerification(firebaseUser);
      setEmailVerificationSent(true);

      await api.post(`/api/v1/firestore/documents`, {
        account_id: firebaseUser.uid, // Using user ID as account_id
        collection: "users",
        document_id: firebaseUser.uid,
        data: {
          profile: {
            email: signUpData.email,
            first_name: signUpData.firstName,
            last_name: signUpData.lastName,
            job_title: "", // Default empty
            email_verified: false, // Track email verification status
          },
          permissions: {
            organizations: {},
            accounts: {},
          },
          preferences: {
            language: "en",
            theme: "light",
            date_format: "mm-dd-yyyy",
          },
        },
      });

      // Show success message instead of logging in immediately
      setErrorMessage("");
      setShowResendButton(true);

      // Clear form data
      setSignUpData({
        firstName: "",
        lastName: "",
        email: "",
        password: "",
        confirmPassword: "",
        agreeToTerms: false,
      });
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
    setIsLoading(true);
    setErrorMessage("");

    try {
      const currentUser = auth.currentUser;
      if (currentUser && !currentUser.emailVerified) {
        await sendEmailVerification(currentUser);
        setErrorMessage("Verification email sent! Please check your inbox.");
        setTimeout(() => setErrorMessage(""), 5000); // Clear message after 5 seconds
      } else {
        setErrorMessage("No user session found. Please sign up again.");
      }
    } catch (error: any) {
      console.error("Resend verification error:", error);
      if (error.code === "auth/too-many-requests") {
        setErrorMessage(
          "Too many requests. Please wait a moment before trying again.",
        );
      } else {
        setErrorMessage(
          "Failed to resend verification email. Please try again.",
        );
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setErrorMessage("");

    try {
      // Authenticate with Google
      const result = await signInWithPopup(auth, googleProvider);
      const firebaseUser = result.user as FirebaseUser;

      const authDeps: AuthHelperDeps = {
        apiBaseUrl: API_BASE_URL,
        login,
        setNotificationSettings,
        setSecuritySettings,
      };

      try {
        // Try to fetch existing user data
        const { userData, notificationsData, securityData } =
          await fetchUserDataAndSettings(firebaseUser.uid, API_BASE_URL);

        // User exists, process login
        processUserLogin(
          firebaseUser,
          userData,
          notificationsData,
          securityData,
          authDeps,
        );
        onAuthenticated();
      } catch (error) {
        const errorMessage = handleApiError(error);

        if (errorMessage === "") {
          // User doesn't exist (404), create new user
          const newUserData = await createUserInFirestore(
            firebaseUser,
            API_BASE_URL,
          );

          // For Google sign-in, email is already verified by Google
          // Update the email_verified status in the created user data
          const updatedUserData = {
            ...newUserData,
            profile: {
              ...newUserData.profile,
              email_verified: true,
            },
          };

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

          processUserLogin(firebaseUser, updatedUserData, [], [], authDeps);
          onAuthenticated();
        } else {
          // Other API errors
          console.error("API error during Google sign-in:", error);
          setErrorMessage(errorMessage);
        }
      }
    } catch (error: any) {
      console.error("Google sign-in error:", error);

      // Handle Firebase auth errors
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
        // Don't show error if it was already handled by API error block
        setErrorMessage("Failed to sign in with Google. Please try again.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <ReCaptchaErrorBoundary
      fallback={
        <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md">
            <Card className="border-red-200 bg-red-50">
              <CardContent className="p-6">
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    ReCAPTCHA failed to load. Please refresh the page or try
                    again later.
                  </AlertDescription>
                </Alert>
              </CardContent>
            </Card>
          </div>
        </div>
      }
    >
      <ReCaptchaWrapper>
        <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md">
            {/* Header */}
            <div className="text-center mb-8">
              <div className="flex items-center justify-center mb-4">
                <img
                  src="/KEN-E Logo Full.png"
                  alt="KEN-E Logo"
                  className="h-32 w-auto"
                />
              </div>
              <p className="text-gray-600">Marketing Assistant</p>
            </div>

            <Card className="shadow-lg border-0 bg-white/80 backdrop-blur-sm">
              {invitationData && !invitationError && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mx-6 mt-4">
                  <div className="flex items-start gap-3">
                    <Mail className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-blue-900">
                        You've been invited!
                      </h4>
                      <p className="text-sm text-blue-700 mt-1">
                        Sign in or create an account to accept your invitation
                        to join{" "}
                        <strong>{invitationData.organization_name}</strong> with{" "}
                        <strong>{invitationData.access_level}</strong> access.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {invitationError && (
                <div className="bg-red-50 border border-red-200 rounded-md p-4 mx-6 mt-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-red-900">
                        Invalid Invitation
                      </h4>
                      <p className="text-sm text-red-700 mt-1">
                        {invitationError}
                      </p>
                    </div>
                  </div>
                </div>
              )}
              {errorMessage && (
                <div
                  className={`text-sm font-medium pt-4 px-6 ${
                    errorMessage.includes("sent!")
                      ? "text-green-600"
                      : "text-red-600"
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {errorMessage.includes("sent!") ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <AlertCircle className="h-4 w-4" />
                    )}
                    {errorMessage}
                  </div>
                </div>
              )}
              {emailVerificationSent && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-4 mx-6 mt-4">
                  <div className="flex items-start gap-3">
                    <Mail className="h-5 w-5 text-blue-600 mt-0.5" />
                    <div className="flex-1">
                      <h4 className="text-sm font-semibold text-blue-900">
                        Verify your email
                      </h4>
                      <p className="text-sm text-blue-700 mt-1">
                        We've sent a verification email to{" "}
                        {signUpData.email || "your email address"}. Please check
                        your inbox and click the verification link to complete
                        your registration.
                      </p>
                      {showResendButton && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3"
                          onClick={handleResendVerificationEmail}
                          disabled={isLoading}
                        >
                          <RefreshCw
                            className={`h-4 w-4 mr-2 ${isLoading ? "animate-spin" : ""}`}
                          />
                          Resend verification email
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              )}
              <CardHeader className="space-y-1 pb-4">
                <CardTitle className="text-center text-xl">
                  Sign in to your account
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Tabs defaultValue="signin" className="space-y-4">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="signin" className="text-sm">
                      Sign In
                    </TabsTrigger>
                    <TabsTrigger value="signup" className="text-sm">
                      Create Account
                    </TabsTrigger>
                  </TabsList>

                  {/* Sign In Tab */}
                  <TabsContent value="signin" className="space-y-4">
                    <form onSubmit={handleSignIn} className="space-y-4">
                      <div className="space-y-2 flex flex-col">
                        <Label
                          htmlFor="signin-email"
                          className="text-left mr-auto"
                        >
                          Email address
                        </Label>
                        <div className="relative">
                          <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            id="signin-email"
                            type="email"
                            placeholder="Enter your email"
                            value={signInData.email}
                            onChange={(e) =>
                              setSignInData({
                                ...signInData,
                                email: e.target.value,
                              })
                            }
                            className="pl-10"
                            required
                          />
                        </div>
                      </div>

                      <div className="space-y-2 flex flex-col">
                        <Label htmlFor="signin-password" className="mr-auto">
                          Password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            id="signin-password"
                            type={showPassword ? "text" : "password"}
                            placeholder="Enter your password"
                            value={signInData.password}
                            onChange={(e) =>
                              setSignInData({
                                ...signInData,
                                password: e.target.value,
                              })
                            }
                            className="pl-10 pr-10"
                            required
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-3 text-gray-400 hover:text-gray-600"
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <Checkbox
                            id="remember"
                            checked={signInData.rememberMe}
                            onCheckedChange={(checked) =>
                              setSignInData({
                                ...signInData,
                                rememberMe: checked as boolean,
                              })
                            }
                          />
                          <Label
                            htmlFor="remember"
                            className="text-sm font-normal"
                          >
                            Remember me
                          </Label>
                        </div>
                        <Button variant="link" className="p-0 h-auto text-sm">
                          Forgot password?
                        </Button>
                      </div>

                      <ReCaptchaV3
                        onVerify={setIsSignInCaptchaVerified}
                        action="signin"
                        className="my-4"
                      />

                      <Button
                        type="submit"
                        className="w-full"
                        disabled={isLoading}
                      >
                        {isLoading ? (
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Signing in...
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            Sign in
                            <ArrowRight className="h-4 w-4" />
                          </div>
                        )}
                      </Button>
                    </form>

                    <div className="relative">
                      <div className="absolute inset-0 flex items-center">
                        <Separator />
                      </div>
                      <div className="relative flex justify-center text-xs uppercase">
                        <span className="bg-white px-2 text-gray-500">
                          Or continue with
                        </span>
                      </div>
                    </div>

                    <div className="w-full">
                      <Button
                        variant="outline"
                        className="w-full"
                        onClick={handleGoogleSignIn}
                        disabled={isLoading}
                      >
                        <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24">
                          <path
                            fill="currentColor"
                            d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                          />
                          <path
                            fill="currentColor"
                            d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                          />
                          <path
                            fill="currentColor"
                            d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                          />
                          <path
                            fill="currentColor"
                            d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                          />
                        </svg>
                        Google
                      </Button>
                    </div>
                  </TabsContent>

                  {/* Sign Up Tab */}
                  <TabsContent value="signup" className="space-y-4">
                    <form onSubmit={handleSignUp} className="space-y-4">
                      <div className="grid grid-cols-2 gap-3">
                        <div className="flex flex-col">
                          <Label htmlFor="first-name" className="mr-auto">
                            First name
                          </Label>
                          <div className="relative">
                            <User className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                            <Input
                              id="first-name"
                              placeholder="First name"
                              value={signUpData.firstName}
                              onChange={(e) =>
                                setSignUpData({
                                  ...signUpData,
                                  firstName: e.target.value,
                                })
                              }
                              className="pl-10"
                              required
                            />
                          </div>
                        </div>
                        <div className="flex flex-col">
                          <Label htmlFor="last-name" className="mr-auto">
                            Last name
                          </Label>
                          <Input
                            id="last-name"
                            placeholder="Last name"
                            value={signUpData.lastName}
                            onChange={(e) =>
                              setSignUpData({
                                ...signUpData,
                                lastName: e.target.value,
                              })
                            }
                            required
                          />
                        </div>
                      </div>

                      <div className="flex flex-col">
                        <Label htmlFor="signup-email" className="mr-auto">
                          Email address
                        </Label>
                        <div className="relative">
                          <Mail className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            id="signup-email"
                            type="email"
                            placeholder="Enter your email"
                            value={signUpData.email}
                            onChange={(e) =>
                              setSignUpData({
                                ...signUpData,
                                email: e.target.value,
                              })
                            }
                            className="pl-10"
                            required
                          />
                        </div>
                      </div>

                      <div className="flex flex-col">
                        <Label htmlFor="signup-password" className="mr-auto">
                          Password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            id="signup-password"
                            type={showPassword ? "text" : "password"}
                            placeholder="Create a password"
                            value={signUpData.password}
                            onChange={(e) =>
                              setSignUpData({
                                ...signUpData,
                                password: e.target.value,
                              })
                            }
                            className="pl-10 pr-10"
                            required
                          />
                          <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="absolute right-3 top-3 text-gray-400 hover:text-gray-600"
                          >
                            {showPassword ? (
                              <EyeOff className="h-4 w-4" />
                            ) : (
                              <Eye className="h-4 w-4" />
                            )}
                          </button>
                        </div>
                      </div>

                      <div className="flex flex-col">
                        <Label htmlFor="confirm-password" className="mr-auto">
                          Confirm password
                        </Label>
                        <div className="relative">
                          <Lock className="absolute left-3 top-3 h-4 w-4 text-gray-400" />
                          <Input
                            id="confirm-password"
                            type="password"
                            placeholder="Confirm your password"
                            value={signUpData.confirmPassword}
                            onChange={(e) =>
                              setSignUpData({
                                ...signUpData,
                                confirmPassword: e.target.value,
                              })
                            }
                            className="pl-10"
                            required
                          />
                        </div>
                      </div>

                      <div className="flex items-center space-x-2">
                        <Checkbox
                          id="terms"
                          checked={signUpData.agreeToTerms}
                          onCheckedChange={(checked) =>
                            setSignUpData({
                              ...signUpData,
                              agreeToTerms: checked as boolean,
                            })
                          }
                          required
                        />
                        <Label htmlFor="terms" className="text-sm font-normal">
                          I agree to the{" "}
                          <Button variant="link" className="p-0 h-auto text-sm">
                            Terms of Service
                          </Button>{" "}
                          and{" "}
                          <Button variant="link" className="p-0 h-auto text-sm">
                            Privacy Policy
                          </Button>
                        </Label>
                      </div>

                      <ReCaptchaV3
                        onVerify={setIsSignUpCaptchaVerified}
                        action="signup"
                        className="my-4"
                      />

                      <Button
                        type="submit"
                        className="w-full"
                        disabled={isLoading || !signUpData.agreeToTerms}
                      >
                        {isLoading ? (
                          <div className="flex items-center gap-2">
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            Creating account...
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <CheckCircle className="h-4 w-4" />
                            Create account
                          </div>
                        )}
                      </Button>
                    </form>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            <div className="text-center mt-6">
              <p className="text-sm text-gray-600">
                Need help?{" "}
                <Button variant="link" className="p-0 h-auto text-sm">
                  Contact support
                </Button>
              </p>
            </div>
          </div>
        </div>
      </ReCaptchaWrapper>
    </ReCaptchaErrorBoundary>
  );
};

export default Authentication;
