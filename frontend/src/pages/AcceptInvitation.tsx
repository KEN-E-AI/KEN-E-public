import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import {
  Building,
  Mail,
  Shield,
  CheckCircle,
  AlertCircle,
  Clock,
  ArrowRight,
} from "lucide-react";
import {
  verifyInvitationToken,
  acceptInvitation,
  type Invitation,
} from "@/data/teamApi";

const AcceptInvitation = () => {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { user, logout } = useAuth();
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isAccepting, setIsAccepting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const verifyInvite = async () => {
      if (!token) {
        setError("Invalid invitation link");
        setIsLoading(false);
        return;
      }

      try {
        const inviteData = await verifyInvitationToken(token);
        setInvitation(inviteData);
      } catch (error: any) {
        console.error("[AcceptInvitation] Error verifying invitation:", error);
        if (error.response?.status === 404) {
          setError("Invalid invitation link");
        } else if (error.response?.status === 400) {
          const detail = error.response.data?.detail;
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
      } finally {
        setIsLoading(false);
      }
    };

    verifyInvite();
  }, [token]);

  const handleAcceptInvitation = async () => {
    if (!invitation || !token || !user) return;

    setIsAccepting(true);
    try {
      await acceptInvitation(token, {
        user_id: user.id,
        user_email: user.email,
        user_name: `${user.firstName} ${user.lastName}`.trim() || user.email,
      });

      toast({
        title: "Success",
        description: `You have been added to ${invitation.organization_name}`,
      });

      // Navigate to the dashboard or home page
      navigate("/");
    } catch (error: any) {
      console.error("[AcceptInvitation] Error accepting invitation:", error);
      const errorMessage =
        error.response?.data?.detail || "Failed to accept invitation";
      toast({
        title: "Error",
        description: errorMessage,
        variant: "destructive",
      });
    } finally {
      setIsAccepting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-lg border-0 bg-white/80 backdrop-blur-sm">
          <CardContent className="pt-8 pb-8">
            <div className="flex flex-col items-center space-y-4">
              <div className="w-16 h-16 bg-brand-medium-blue/10 rounded-full flex items-center justify-center animate-pulse">
                <Mail className="h-8 w-8 text-brand-medium-blue" />
              </div>
              <p className="text-gray-600">Verifying your invitation...</p>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-lg border-0 bg-white/80 backdrop-blur-sm">
          <CardContent className="pt-8 pb-8">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Invalid Invitation</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
            <div className="mt-6 text-center">
              <Button
                variant="outline"
                onClick={() => navigate(user ? "/" : "/login")}
              >
                {user ? "Go to Dashboard" : "Go to Login"}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-lg border-0 bg-white/80 backdrop-blur-sm">
          <CardHeader className="text-center">
            <div className="flex items-center justify-center mb-4">
              <div className="w-12 h-12 bg-brand-medium-blue rounded-lg flex items-center justify-center">
                <Building className="h-6 w-6 text-white" />
              </div>
            </div>
            <CardTitle className="text-2xl">Sign In Required</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-center text-gray-600">
              You need to sign in or create an account to accept this
              invitation.
            </p>
            {invitation && (
              <Alert>
                <Mail className="h-4 w-4" />
                <AlertDescription>
                  You've been invited to join{" "}
                  <strong>{invitation.organization_name}</strong> with{" "}
                  <strong>{invitation.access_level}</strong> access.
                </AlertDescription>
              </Alert>
            )}
            <div className="flex gap-3">
              <Button
                className="flex-1"
                onClick={() =>
                  navigate("/login", { state: { from: `/invite/${token}` } })
                }
              >
                Sign In
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                onClick={() =>
                  navigate("/signup", { state: { from: `/invite/${token}` } })
                }
              >
                Create Account
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Check if user email matches invitation email
  if (invitation && user.email !== invitation.email) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-lg border-0 bg-white/80 backdrop-blur-sm">
          <CardContent className="pt-8 pb-8">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Email Mismatch</AlertTitle>
              <AlertDescription>
                This invitation was sent to {invitation.email}, but you're
                signed in as {user.email}. Please sign in with the correct email
                address to accept this invitation.
              </AlertDescription>
            </Alert>
            <div className="mt-6 flex gap-3">
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
                  navigate("/login", { state: { from: `/invite/${token}` } });
                }}
              >
                Sign In with Different Account
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-light-blue/20 via-white to-slate-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg shadow-lg border-0 bg-white/80 backdrop-blur-sm">
        <CardHeader className="text-center">
          <div className="flex items-center justify-center mb-4">
            <div className="w-16 h-16 bg-brand-medium-blue rounded-lg flex items-center justify-center">
              <Building className="h-8 w-8 text-white" />
            </div>
          </div>
          <CardTitle className="text-2xl">You're Invited!</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          {invitation && (
            <>
              <div className="text-center space-y-2">
                <p className="text-lg text-gray-700">
                  <strong>{invitation.inviter_name}</strong> has invited you to
                  join
                </p>
                <h3 className="text-2xl font-bold text-brand-medium-blue">
                  {invitation.organization_name}
                </h3>
              </div>

              <Separator />

              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-light-blue/30 rounded-full flex items-center justify-center">
                    <Mail className="h-5 w-5 text-brand-medium-blue" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Your email</p>
                    <p className="font-medium">{invitation.email}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-light-blue/30 rounded-full flex items-center justify-center">
                    <Shield className="h-5 w-5 text-brand-medium-blue" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Access level</p>
                    <p className="font-medium capitalize">
                      {invitation.access_level}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-brand-light-blue/30 rounded-full flex items-center justify-center">
                    <Clock className="h-5 w-5 text-brand-medium-blue" />
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Expires</p>
                    <p className="font-medium">
                      {new Date(invitation.expires_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </div>

              <Alert>
                <CheckCircle className="h-4 w-4" />
                <AlertDescription>
                  By accepting this invitation, you'll gain{" "}
                  <strong>{invitation.access_level}</strong> access to{" "}
                  {invitation.organization_name}'s KEN-E workspace.
                </AlertDescription>
              </Alert>

              <div className="flex gap-3 pt-4">
                <Button
                  variant="outline"
                  className="flex-1"
                  onClick={() => navigate("/")}
                  disabled={isAccepting}
                >
                  Decline
                </Button>
                <Button
                  className="flex-1"
                  onClick={handleAcceptInvitation}
                  disabled={isAccepting}
                >
                  {isAccepting ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Accepting...
                    </div>
                  ) : (
                    <>
                      Accept Invitation
                      <CheckCircle className="ml-2 h-4 w-4" />
                    </>
                  )}
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default AcceptInvitation;
