import { useState } from 'react';
import { User, Mail, Lock, AlertCircle, Check, UserPlus } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Checkbox } from '../components/ui/checkbox';
import { Link } from 'react-router';
import { Logo } from '../components/Logo';

export function CreateAccountPage() {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  // Check if user arrived via invitation link
  const urlParams = new URLSearchParams(window.location.search);
  const invitationToken = urlParams.get('invitation');
  const invitationType = urlParams.get('type');
  const inviterName = urlParams.get('inviter');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
    // Clear error when user starts typing
    if (errors[name]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const validateForm = () => {
    const newErrors: Record<string, string> = {};

    if (!formData.name.trim()) {
      newErrors.name = 'Name is required';
    }

    if (!formData.email.trim()) {
      newErrors.email = 'Email is required';
    } else if (!/\S+@\S+\.\S+/.test(formData.email)) {
      newErrors.email = 'Email is invalid';
    }

    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters';
    }

    if (formData.password !== formData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    if (!agreedToTerms) {
      newErrors.terms = 'You must agree to the terms and conditions';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validateForm()) {
      console.log('Create account:', formData);
      // Handle account creation logic here
    }
  };

  const handleGoogleSignUp = () => {
    // Handle Google OAuth
    console.log('Google sign up');
  };

  const passwordStrength = formData.password.length >= 8 
    ? formData.password.length >= 12 && /[A-Z]/.test(formData.password) && /[0-9]/.test(formData.password)
      ? 'strong'
      : 'medium'
    : 'weak';

  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background Blobs */}
      <div className="fixed inset-0 pointer-events-none z-[-1]">
        <div 
          className="absolute rounded-full blur-[5rem] opacity-[0.18] animate-blob-drift"
          style={{
            top: '-60px',
            left: '10%',
            width: '25rem',
            height: '25rem',
            backgroundColor: 'rgba(59, 130, 246, 1)',
          }}
        />
        <div 
          className="absolute rounded-full blur-[5rem] opacity-[0.18] animate-blob-drift-delayed"
          style={{
            top: '30%',
            right: '-80px',
            width: '21.875rem',
            height: '21.875rem',
            backgroundColor: 'rgba(99, 102, 241, 1)',
            animationDelay: '2s',
          }}
        />
        <div 
          className="absolute rounded-full blur-[5rem] opacity-[0.18] animate-blob-drift"
          style={{
            bottom: '-40px',
            left: '30%',
            width: '28.125rem',
            height: '28.125rem',
            backgroundColor: 'rgba(46, 196, 182, 1)',
            animationDelay: '4s',
          }}
        />
        <div 
          className="absolute rounded-full blur-[5rem] opacity-[0.12] animate-blob-drift-delayed"
          style={{
            top: '50%',
            left: '-100px',
            width: '18.75rem',
            height: '18.75rem',
            backgroundColor: 'rgba(100, 116, 139, 1)',
            animationDelay: '6s',
          }}
        />
      </div>

      {/* Grain Texture Overlay */}
      <div 
        className="fixed inset-0 pointer-events-none z-[-1] opacity-[0.06]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 400 400' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.8' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E")`,
          backgroundRepeat: 'repeat',
        }}
      />

      <div className="w-full max-w-md animate-page-enter">
        {/* Logo and Brand */}
        <div className="text-center mb-8">
          <div className="mb-2 flex justify-center animate-logo-float">
            <Logo size="xl" variant="icon" />
          </div>
          <h1 className="mb-2">Create your account</h1>
          <p className="text-sm text-muted-foreground">
            The AI Marketing Analyst
          </p>
        </div>

        {/* Rainbow Gradient Accent */}
        <div 
          className="h-[3px] rounded-full mb-6 mx-auto w-[80%]"
          style={{
            background: 'linear-gradient(90deg, #3B82F6, #6366F1, #2EC4B6, #F59E0B)',
          }}
        />

        {/* Invitation Banner */}
        {invitationToken && (
          <div className="mb-6 p-4 rounded-[var(--radius-md)] bg-gradient-to-r from-[#F97066]/10 to-[var(--color-violet-500)]/10 border-2 border-[#F97066]/30 animate-slide-in">
            <div className="flex items-start gap-3">
              <div className="size-10 rounded-[var(--radius-md)] bg-[#F97066] flex items-center justify-center shrink-0">
                <Mail className="size-5 text-white" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-medium mb-1">You've been invited!</p>
                <p className="text-xs text-muted-foreground">
                  {inviterName || 'Someone'} invited you to join their {invitationType || 'team'}. Create your account to get started.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Create Account Card */}
        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg">
          {/* Google Sign Up */}
          <Button
            type="button"
            variant="outline"
            className="w-full mb-4 gap-2 transition-all duration-200 hover:-translate-y-0.5"
            onClick={handleGoogleSignUp}
          >
            <svg className="size-5" viewBox="0 0 24 24">
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

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-[var(--color-border-default)]"></div>
            </div>
            <div className="relative flex justify-center text-xs">
              <span className="bg-card px-2 text-muted-foreground">Or continue with email</span>
            </div>
          </div>

          {/* Create Account Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="name">Full Name</Label>
              <div className="relative mt-1.5">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  id="name"
                  name="name"
                  type="text"
                  placeholder="Jane Smith"
                  value={formData.name}
                  onChange={handleChange}
                  className="pl-10"
                  aria-invalid={!!errors.name}
                />
              </div>
              {errors.name && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {errors.name}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="email">Email</Label>
              <div className="relative mt-1.5">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="you@example.com"
                  value={formData.email}
                  onChange={handleChange}
                  className="pl-10"
                  aria-invalid={!!errors.email}
                />
              </div>
              {errors.email && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {errors.email}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="password">Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={handleChange}
                  className="pl-10"
                  aria-invalid={!!errors.password}
                />
              </div>
              {formData.password && (
                <div className="mt-2 flex items-center gap-2">
                  <div className="flex-1 h-1.5 bg-[var(--color-surface-muted)] rounded-full overflow-hidden">
                    <div
                      className={`h-full transition-all ${
                        passwordStrength === 'strong'
                          ? 'bg-green-500 w-full'
                          : passwordStrength === 'medium'
                          ? 'bg-yellow-500 w-2/3'
                          : 'bg-red-500 w-1/3'
                      }`}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground capitalize">{passwordStrength}</span>
                </div>
              )}
              {errors.password && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {errors.password}
                </p>
              )}
            </div>

            <div>
              <Label htmlFor="confirmPassword">Confirm Password</Label>
              <div className="relative mt-1.5">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
                <Input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  placeholder="••••••••"
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  className="pl-10"
                  aria-invalid={!!errors.confirmPassword}
                />
                {formData.confirmPassword && formData.password === formData.confirmPassword && (
                  <Check className="absolute right-3 top-1/2 -translate-y-1/2 size-4 text-green-500" />
                )}
              </div>
              {errors.confirmPassword && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {errors.confirmPassword}
                </p>
              )}
            </div>

            {/* Terms Agreement */}
            <div>
              <div className="flex items-start gap-2">
                <Checkbox
                  id="terms"
                  checked={agreedToTerms}
                  onCheckedChange={(checked) => setAgreedToTerms(checked as boolean)}
                  className="mt-0.5"
                />
                <Label htmlFor="terms" className="text-sm cursor-pointer leading-tight">
                  I agree to the{' '}
                  <a href="/terms" className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]">
                    Terms of Service
                  </a>{' '}
                  and{' '}
                  <a href="/privacy" className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]">
                    Privacy Policy
                  </a>
                </Label>
              </div>
              {errors.terms && (
                <p className="text-xs text-red-600 mt-1 flex items-center gap-1">
                  <AlertCircle className="size-3" />
                  {errors.terms}
                </p>
              )}
            </div>

            {/* Create Account Button */}
            <Button
              type="submit"
              className="w-full gap-2 bg-[#F97066] hover:bg-[#e85f55] text-white"
              style={{
                boxShadow: '0 4px 12px rgba(249, 112, 102, 0.3)',
              }}
            >
              <UserPlus className="size-4" />
              Create Account
            </Button>
          </form>

          {/* Sign In Link */}
          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Already have an account?{' '}
              <Link
                to={invitationToken ? `/sign-in?invitation=${invitationToken}&type=${invitationType}&inviter=${inviterName}` : '/sign-in'}
                className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium transition-colors"
              >
                Sign in
              </Link>
            </p>
          </div>
        </div>

        {/* Contact Support */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            Need help?{' '}
            <a
              href="mailto:support@ken-e.com"
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] transition-colors"
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>

      {/* Animation Styles */}
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

        /* Reduced motion support */
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