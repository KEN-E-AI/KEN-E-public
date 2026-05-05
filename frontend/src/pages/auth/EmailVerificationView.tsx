import { Mail, RefreshCw, CheckCircle2, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Link } from "react-router-dom";

type EmailVerificationViewProps = {
  email: string;
  resendStatus: "idle" | "sending" | "sent" | "error";
  countdown: number;
  onResend: () => void;
};

export function EmailVerificationView({
  email,
  resendStatus,
  countdown,
  onResend,
}: EmailVerificationViewProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="relative inline-block mb-4">
            <div
              className="size-24 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center"
              style={{ boxShadow: "var(--shadow-color-violet)" }}
            >
              <Mail className="size-12 text-white" />
            </div>
            <div className="absolute inset-0 rounded-full bg-[var(--color-violet-500)] opacity-20 animate-ping" />
          </div>
          <h1 className="mb-2">Check your email</h1>
          <p className="text-sm text-muted-foreground">
            We've sent a verification link to
          </p>
          <p className="text-sm font-medium text-[var(--color-violet-500)] mt-1">
            {email}
          </p>
        </div>

        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
          <div className="space-y-4">
            <div className="p-4 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)]">
              <h3 className="text-sm font-medium mb-2">Next steps:</h3>
              <ol className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-[var(--color-violet-500)] font-medium shrink-0">
                    1.
                  </span>
                  <span>Check your inbox for an email from KEN-E</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--color-violet-500)] font-medium shrink-0">
                    2.
                  </span>
                  <span>Click the verification link in the email</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-[var(--color-violet-500)] font-medium shrink-0">
                    3.
                  </span>
                  <span>You'll be redirected to complete your setup</span>
                </li>
              </ol>
            </div>

            {resendStatus === "sent" && (
              <div className="p-3 rounded-[var(--radius-md)] bg-green-50 border border-green-200 flex items-center gap-2">
                <CheckCircle2 className="size-4 text-green-600 shrink-0" />
                <p className="text-sm text-green-600">
                  Verification email sent successfully!
                </p>
              </div>
            )}

            {resendStatus === "error" && (
              <div className="p-3 rounded-[var(--radius-md)] bg-red-50 border border-red-200 flex items-center gap-2">
                <XCircle className="size-4 text-red-600 shrink-0" />
                <p className="text-sm text-red-600">
                  Failed to resend email. Please try again.
                </p>
              </div>
            )}

            <Button
              variant="outline"
              className="w-full gap-2"
              onClick={onResend}
              disabled={resendStatus === "sending" || countdown > 0}
            >
              {resendStatus === "sending" ? (
                <>
                  <RefreshCw className="size-4 animate-spin" />
                  Sending...
                </>
              ) : countdown > 0 ? (
                <>
                  <RefreshCw className="size-4" />
                  Resend in {countdown}s
                </>
              ) : (
                <>
                  <RefreshCw className="size-4" />
                  Resend verification email
                </>
              )}
            </Button>

            <div className="text-center">
              <p className="text-xs text-muted-foreground">
                Didn't receive the email? Check your spam folder or{" "}
                <a
                  href="mailto:support@ken-e.com"
                  className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]"
                >
                  contact support
                </a>
              </p>
            </div>

            <div className="relative my-6">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-[var(--color-border-default)]"></div>
              </div>
            </div>

            <div className="space-y-2 text-center">
              <p className="text-sm text-muted-foreground">
                Wrong email address?{" "}
                <Link
                  to="/create-account"
                  className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium"
                >
                  Create a new account
                </Link>
              </p>
              <p className="text-sm text-muted-foreground">
                Already verified?{" "}
                <Link
                  to="/sign-in"
                  className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </div>

        <div className="mt-6 p-4 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)] border border-[var(--color-border-default)]">
          <p className="text-xs text-muted-foreground text-center">
            For your security, this verification link will expire in 24 hours
          </p>
        </div>
      </div>
    </div>
  );
}
