import type { FormEvent } from "react";
import { User, Mail, Lock, AlertCircle, Check, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Link } from "react-router-dom";
import { Logo } from "@/components/branding/Logo";

type CreateAccountViewProps = {
  name: string;
  email: string;
  password: string;
  confirmPassword: string;
  agreedToTerms: boolean;
  isLoading: boolean;
  errorMessage: string;
  fieldErrors: Record<string, string>;
  invitationToken: string | null;
  invitationData: { organization_name: string; access_level: string } | null;
  invitationError: string | null;
  onNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onConfirmPasswordChange: (value: string) => void;
  onAgreedToTermsChange: (value: boolean) => void;
  onSubmit: (e: FormEvent) => void;
  onGoogleSignUp: () => void;
};

export function CreateAccountView({
  name,
  email,
  password,
  confirmPassword,
  agreedToTerms,
  isLoading,
  errorMessage,
  fieldErrors,
  invitationToken,
  invitationData,
  invitationError,
  onNameChange,
  onEmailChange,
  onPasswordChange,
  onConfirmPasswordChange,
  onAgreedToTermsChange,
  onSubmit,
  onGoogleSignUp,
}: CreateAccountViewProps) {
  const passwordStrength =
    password.length >= 8
      ? password.length >= 12 &&
        /[A-Z]/.test(password) &&
        /[0-9]/.test(password)
        ? "strong"
        : "medium"
      : "weak";

  const signInHref = invitationToken
    ? `/sign-in?${new URLSearchParams({ invitation: invitationToken }).toString()}`
    : "/sign-in";

  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4 relative overflow-hidden">
      <div className="w-full max-w-md animate-page-enter">
        <div className="text-center mb-8">
          <div className="mb-2 flex justify-center animate-logo-float">
            <Logo size="xl" variant="icon" />
          </div>
          <h1 className="mb-2">Create your account</h1>
          <p className="text-sm text-[var(--color-text-secondary)]">
            The AI Marketing Analyst
          </p>
        </div>

        <div
          className="h-[3px] rounded-full mb-6 mx-auto w-[80%]"
          style={{
            background:
              "linear-gradient(90deg, #3B82F6, #6366F1, #2EC4B6, #F59E0B)",
          }}
        />

        {invitationToken && invitationData && !invitationError && (
          <div className="mb-6 p-4 rounded-[var(--radius-md)] bg-gradient-to-r from-[#F97066]/10 to-[var(--color-violet-500)]/10 border-2 border-[#F97066]/30 animate-slide-in">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-[var(--radius-md)] bg-[#F97066] flex items-center justify-center shrink-0">
                <Mail className="size-5 text-white" aria-hidden="true" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium mb-1">You've been invited!</p>
                <p className="text-xs text-[var(--color-text-secondary)]">
                  Create your account to join{" "}
                  <strong>{invitationData.organization_name}</strong> with{" "}
                  <strong>{invitationData.access_level}</strong> access.
                </p>
              </div>
            </div>
          </div>
        )}

        {invitationError && (
          <div className="mb-6">
            <Alert variant="destructive">
              <AlertCircle className="size-4" />
              <AlertDescription>{invitationError}</AlertDescription>
            </Alert>
          </div>
        )}

        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
          {errorMessage && (
            <div className="mb-4 p-3 rounded-[var(--radius-md)] bg-red-50 border border-red-200 flex items-center gap-2">
              <AlertCircle className="size-4 text-red-600 shrink-0" />
              <p className="text-sm text-red-600">{errorMessage}</p>
            </div>
          )}

          <Button
            type="button"
            variant="outline"
            className="w-full mb-4 gap-2 transition-all duration-200 hover:-translate-y-0.5"
            onClick={onGoogleSignUp}
            disabled={isLoading}
          >
            <svg className="size-5" viewBox="0 0 24 24" aria-hidden="true">
              <path
                fill="#4285F4"
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              />
              <path
                fill="#34A853"
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              />
              <path
                fill="#FBBC05"
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
              />
              <path
                fill="#EA4335"
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
              />
            </svg>
            Continue with Google
          </Button>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--color-border-default)]"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-card px-2 text-[var(--color-text-secondary)]">
                Or continue with email
              </span>
            </div>
          </div>

          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Full Name</Label>
              <div className="relative mt-1.5">
                <User
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  id="name"
                  name="name"
                  type="text"
                  placeholder="Jane Smith"
                  value={name}
                  onChange={(e) => onNameChange(e.target.value)}
                  className="pl-10"
                  aria-invalid={!!fieldErrors.name}
                />
              </div>
              {fieldErrors.name && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {fieldErrors.name}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="email">Email</Label>
              <div className="relative mt-1.5">
                <Mail
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => onEmailChange(e.target.value)}
                  className="pl-10"
                  aria-invalid={!!fieldErrors.email}
                />
              </div>
              {fieldErrors.email && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {fieldErrors.email}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <div className="relative mt-1.5">
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => onPasswordChange(e.target.value)}
                  className="pl-10"
                  aria-invalid={!!fieldErrors.password}
                />
              </div>
              {password && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-[var(--color-surface-muted)] rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        passwordStrength === "strong"
                          ? "bg-green-500 w-full"
                          : passwordStrength === "medium"
                            ? "bg-yellow-500 w-2/3"
                            : "bg-red-500 w-1/3"
                      }`}
                    />
                  </div>
                  <span className="text-xs text-[var(--color-text-secondary)] capitalize">
                    {passwordStrength}
                  </span>
                </div>
              )}
              {fieldErrors.password && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {fieldErrors.password}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <div className="relative mt-1.5">
                <Lock
                  className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground"
                  aria-hidden="true"
                />
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  placeholder="••••••••"
                  value={confirmPassword}
                  onChange={(e) => onConfirmPasswordChange(e.target.value)}
                  className="pl-10"
                  aria-invalid={!!fieldErrors.confirmPassword}
                />
                {confirmPassword && password === confirmPassword && (
                  <Check
                    className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-green-500"
                    aria-hidden="true"
                  />
                )}
              </div>
              {fieldErrors.confirmPassword && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {fieldErrors.confirmPassword}
                </p>
              )}
            </div>

            <div>
              <div className="flex items-start gap-2">
                <Checkbox
                  id="terms"
                  aria-label="I agree to the Terms of Service and Privacy Policy"
                  checked={agreedToTerms}
                  onCheckedChange={(checked) =>
                    onAgreedToTermsChange(checked as boolean)
                  }
                  className="mt-0.5"
                />
                <Label
                  htmlFor="terms"
                  className="text-sm cursor-pointer leading-tight"
                >
                  I agree to the{" "}
                  <a
                    href="/terms"
                    className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]"
                  >
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a
                    href="/privacy"
                    className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]"
                  >
                    Privacy Policy
                  </a>
                </Label>
              </div>
              {fieldErrors.terms && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {fieldErrors.terms}
                </p>
              )}
            </div>

            <Button
              type="submit"
              className="w-full gap-2 bg-[#F97066] hover:bg-[#e85f55] text-white transition-all duration-200 hover:-translate-y-0.5 hover:rotate-[-1deg]"
              style={{ boxShadow: "0 4px 12px rgba(249, 112, 102, 0.3)" }}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="size-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating account...
                </>
              ) : (
                <>
                  <UserPlus className="size-4" aria-hidden="true" />
                  Create Account
                </>
              )}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-[var(--color-text-secondary)]">
              Already have an account?{" "}
              <Link
                to={signInHref}
                className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        <div className="mt-6 text-center">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Need help?{" "}
            <a
              href="mailto:support@ken-e.com"
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] transition-colors"
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>

      <style>{`
        @keyframes page-enter {
          from {
            opacity: 0;
            transform: translateY(40px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        @keyframes logo-float {
          0%, 100% {
            transform: translateY(0);
          }
          50% {
            transform: translateY(-12px);
          }
        }

        @keyframes blob-drift {
          0%, 100% {
            transform: translate(0, 0);
          }
          33% {
            transform: translate(15px, -10px);
          }
          66% {
            transform: translate(-10px, 15px);
          }
        }

        @keyframes blob-drift-delayed {
          0%, 100% {
            transform: translate(0, 0);
          }
          33% {
            transform: translate(-15px, 10px);
          }
          66% {
            transform: translate(10px, -15px);
          }
        }

        @keyframes slide-in {
          from {
            opacity: 0;
            transform: translateX(-20px);
          }
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .animate-page-enter {
          animation: page-enter 600ms cubic-bezier(0.175, 0.885, 0.32, 1.1);
        }

        .animate-logo-float {
          animation: logo-float 6s ease-in-out infinite;
        }

        .animate-blob-drift {
          animation: blob-drift 20s ease-in-out infinite;
        }

        .animate-blob-drift-delayed {
          animation: blob-drift-delayed 20s ease-in-out infinite;
        }

        .animate-slide-in {
          animation: slide-in 400ms cubic-bezier(0.175, 0.885, 0.32, 1.1);
          animation-delay: 200ms;
          animation-fill-mode: backwards;
        }

        @media (prefers-reduced-motion: reduce) {
          .animate-page-enter,
          .animate-logo-float,
          .animate-blob-drift,
          .animate-blob-drift-delayed,
          .animate-slide-in {
            animation: none;
          }

          * {
            transition-duration: 0.01ms !important;
          }
        }
      `}</style>
    </div>
  );
}
