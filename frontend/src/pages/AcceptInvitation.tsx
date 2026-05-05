import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import api from "@/lib/api";
import {
  Building2,
  Users,
  CheckCircle2,
  XCircle,
  Loader2,
  ArrowRight,
} from "lucide-react";
import { verifyInvitationToken, acceptInvitation } from "@/data/teamApi";
import type { Invitation } from "@/data/teamApi";

type InvitationStatus =
  | "loading"
  | "valid"
  | "accepting"
  | "accepted"
  | "error";

const AcceptInvitation = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user, logout } = useAuth();
  const [status, setStatus] = useState<InvitationStatus>("loading");
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const verifyInvite = async () => {
      if (!token) {
        setError("Invalid invitation link");
        setStatus("error");
        return;
      }

      try {
        const inviteData = await verifyInvitationToken(token);
        if (!inviteData) {
          setError("Invalid invitation link");
          setStatus("error");
          return;
        }
        setInvitation(inviteData);
        setStatus("valid");
      } catch (err: any) {
        if (err.response?.status === 404) {
          setError("Invalid invitation link");
        } else if (err.response?.status === 400) {
          const detail = err.response.data?.detail;
          if (detail?.includes("expired")) {
            setError("This invitation has expired");
          } else if (detail?.includes("already been accepted")) {
            setError("This invitation has already been accepted");
          } else {
            setError(detail || "Invalid invitation");
          }
        } else {
          setError("Failed to verify invitation. Please try again later.");
        }
        setStatus("error");
      }
    };

    verifyInvite();
  }, [token]);

  // Redirect unauthenticated users after successful verification
  useEffect(() => {
    if (status === "valid" && !user && token && invitation) {
      navigate("/sign-in", {
        replace: true,
        state: { from: `/invite/${token}` },
      });
    }
  }, [status, user, token, invitation, navigate]);

  const handleAcceptInvitation = async () => {
    if (!invitation || !token || !user) return;

    setStatus("accepting");
    try {
      await acceptInvitation(token, {
        user_id: user.id,
        user_email: user.email,
        user_name: `${user.firstName} ${user.lastName}`.trim() || user.email,
      });

      // Check if user has notification preferences, create if missing
      try {
        await api.get(
          `/api/v1/firestore/documents/users/${user.id}/preferences/notifications`,
        );
      } catch (prefErr: any) {
        if (prefErr.response?.status === 404) {
          await api.post(`/api/v1/firestore/documents`, {
            account_id: user.id,
            collection: `users/${user.id}/preferences`,
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
        }
      }

      toast({
        title: "Success",
        description: `You have been added to ${invitation.organization_name}`,
      });

      setStatus("accepted");
    } catch (err: any) {
      const errorMessage =
        err.response?.data?.detail || "Failed to accept invitation";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
      setStatus("valid");
    }
  };

  const outerClass =
    "min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4";

  // Loading state
  if (status === "loading") {
    return (
      <div className={outerClass}>
        <div className="text-center">
          <Loader2 className="size-12 text-[var(--color-violet-500)] animate-spin mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">
            Verifying your invitation...
          </p>
        </div>
      </div>
    );
  }

  // Error state (invalid / expired / already-accepted / network error)
  if (status === "error") {
    return (
      <div className={outerClass}>
        <div className="w-full max-w-md">
          <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
            <Alert variant="destructive" className="mb-6">
              <XCircle className="size-4" />
              <AlertTitle>Invalid Invitation</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
            <div className="text-center">
              <Button
                variant="outline"
                onClick={() => navigate(user ? "/" : "/sign-in")}
              >
                {user ? "Go to Dashboard" : "Go to Sign In"}
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Accepted state
  if (status === "accepted") {
    return (
      <div className={outerClass}>
        <div className="w-full max-w-md text-center">
          <div className="relative inline-block mb-6">
            <div
              className="size-24 rounded-full bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center"
              style={{ boxShadow: "0 8px 24px rgba(34, 197, 94, 0.3)" }}
            >
              <CheckCircle2 className="size-12 text-white" />
            </div>
            <div className="absolute inset-0 rounded-full bg-green-500 opacity-20 animate-ping" />
          </div>
          <h1 className="mb-2">Welcome aboard! 🎉</h1>
          <p className="text-sm text-muted-foreground mb-6">
            You've successfully joined{" "}
            <span className="font-medium text-[var(--color-violet-500)]">
              {invitation?.organization_name}
            </span>
          </p>
          <Button
            onClick={() => navigate("/")}
            className="gap-2 bg-[var(--color-cta-coral)] hover:bg-[var(--color-cta-coral-hover)] text-[var(--color-text-inverse)]"
            style={{ boxShadow: "var(--shadow-color-coral)" }}
          >
            Get Started
            <ArrowRight className="size-4" />
          </Button>
        </div>
      </div>
    );
  }

  // Email mismatch — user is signed in with wrong account
  if (invitation && user && user.email !== invitation.email) {
    return (
      <div className={outerClass}>
        <div className="w-full max-w-md">
          <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
            <Alert variant="destructive" className="mb-6">
              <XCircle className="size-4" />
              <AlertTitle>Email Mismatch</AlertTitle>
              <AlertDescription>
                This invitation was sent to {invitation.email}, but you're
                signed in as {user.email}. Please sign in with the correct email
                address to accept this invitation.
              </AlertDescription>
            </Alert>
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => navigate("/")}
              >
                Go to Dashboard
              </Button>
              <Button
                className="flex-1"
                onClick={() => {
                  logout();
                  navigate("/sign-in", { state: { from: `/invite/${token}` } });
                }}
              >
                Sign In with Different Account
              </Button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Valid invitation — show invite details and accept / decline
  if (invitation && user) {
    return (
      <div className={outerClass}>
        <div className="w-full max-w-md">
          {/* Header */}
          <div className="text-center mb-8">
            <div
              className="inline-flex items-center justify-center size-16 rounded-[var(--radius-lg)] bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] mb-4"
              style={{ boxShadow: "var(--shadow-color-violet)" }}
            >
              {invitation.account_permissions ? (
                <Users className="size-8 text-white" />
              ) : (
                <Building2 className="size-8 text-white" />
              )}
            </div>
            <h1 className="mb-2">You&apos;re invited!</h1>
            <p className="text-sm text-muted-foreground">
              Join your team on KEN-E
            </p>
          </div>

          {/* Invitation details card */}
          <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg mb-6">
            <div className="space-y-4">
              {/* Inviter info */}
              <div className="flex items-start gap-4 pb-4 border-b border-[var(--color-border-default)]">
                <div className="size-12 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center shrink-0 text-white font-medium">
                  {invitation.inviter_name
                    .split(" ")
                    .map((n) => n[0])
                    .filter(Boolean)
                    .join("") || "?"}
                </div>
                <div>
                  <p className="text-sm font-medium">
                    {invitation.inviter_name}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    invited you to join
                  </p>
                </div>
              </div>

              {/* Invitation details */}
              <div className="space-y-3">
                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Organization
                  </p>
                  <p className="text-sm font-medium">
                    {invitation.organization_name}
                  </p>
                </div>

                <div>
                  <p className="text-xs text-muted-foreground mb-1">
                    Your role
                  </p>
                  <p className="text-sm font-medium capitalize">
                    {invitation.access_level}
                  </p>
                </div>

                <div className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)]">
                  <p className="text-xs text-muted-foreground">
                    This invitation expires on{" "}
                    <span className="font-medium text-[var(--color-text-primary)]">
                      {new Date(invitation.expires_at).toLocaleDateString(
                        "en-US",
                        { month: "long", day: "numeric", year: "numeric" },
                      )}
                    </span>
                  </p>
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex flex-col gap-3 pt-2">
                <Button
                  onClick={handleAcceptInvitation}
                  disabled={status === "accepting"}
                  className="w-full gap-2 bg-[var(--color-cta-coral)] hover:bg-[var(--color-cta-coral-hover)] text-[var(--color-text-inverse)]"
                  style={{ boxShadow: "var(--shadow-color-coral)" }}
                >
                  {status === "accepting" ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      Accepting...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-4" />
                      Accept Invitation
                    </>
                  )}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => navigate("/")}
                  disabled={status === "accepting"}
                  className="w-full"
                >
                  Decline
                </Button>
              </div>
            </div>
          </div>

          {/* Footer links */}
          <div className="text-center space-y-3">
            <p className="text-sm text-muted-foreground">
              Already have an account?{" "}
              <a
                href="/auth/signin"
                className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium underline"
              >
                Sign in
              </a>
            </p>
            <p className="text-sm text-muted-foreground">
              Need help?{" "}
              <a
                href="mailto:support@mer-e.com"
                className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] underline"
              >
                Contact Support
              </a>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Fallback — unauthenticated redirect in progress (shown briefly while useEffect fires)
  return (
    <div className={outerClass}>
      <div className="text-center">
        <Loader2 className="size-12 text-[var(--color-violet-500)] animate-spin mx-auto mb-4" />
        <p className="text-sm text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
};

export default AcceptInvitation;
