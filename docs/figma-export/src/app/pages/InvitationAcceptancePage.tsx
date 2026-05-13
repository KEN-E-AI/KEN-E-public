import { useState, useEffect } from 'react';
import { Users, Building2, CheckCircle2, XCircle, Loader2, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Link } from 'react-router';

interface InvitationDetails {
  type: 'organization' | 'account';
  organizationName: string;
  accountName?: string;
  inviterName: string;
  inviterEmail: string;
  role: string;
  expiresAt: Date;
}

export function InvitationAcceptancePage() {
  const [status, setStatus] = useState<'loading' | 'valid' | 'invalid' | 'expired' | 'accepting' | 'accepted' | 'error'>('loading');
  const [invitation, setInvitation] = useState<InvitationDetails | null>(null);

  // Get invitation token from URL
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('token');

  useEffect(() => {
    // Simulate fetching invitation details
    const fetchInvitation = async () => {
      setStatus('loading');
      
      // Simulate API call
      setTimeout(() => {
        // Mock invitation data
        const mockInvitation: InvitationDetails = {
          type: urlParams.get('type') as 'organization' | 'account' || 'organization',
          organizationName: 'Acme Marketing Co.',
          accountName: urlParams.get('type') === 'account' ? 'Instagram Ads Campaign' : undefined,
          inviterName: urlParams.get('inviter') || 'Sarah Johnson',
          inviterEmail: 'sarah@acmemarketing.com',
          role: 'Member',
          expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days from now
        };

        setInvitation(mockInvitation);
        setStatus('valid');
      }, 1500);
    };

    if (token) {
      fetchInvitation();
    } else {
      setStatus('invalid');
    }
  }, [token]);

  const handleAcceptInvitation = async () => {
    setStatus('accepting');
    
    // Simulate API call to accept invitation
    setTimeout(() => {
      setStatus('accepted');
    }, 2000);
  };

  const handleDeclineInvitation = () => {
    // Handle decline logic
    console.log('Invitation declined');
  };

  // Loading state
  if (status === 'loading') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
        <div className="text-center">
          <Loader2 className="size-12 text-[var(--color-violet-500)] animate-spin mx-auto mb-4" />
          <p className="text-sm text-muted-foreground">Loading invitation...</p>
        </div>
      </div>
    );
  }

  // Invalid token
  if (status === 'invalid') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="size-24 rounded-full bg-red-100 flex items-center justify-center mx-auto mb-6">
            <XCircle className="size-12 text-red-600" />
          </div>
          <h1 className="mb-2">Invalid Invitation</h1>
          <p className="text-sm text-muted-foreground mb-6">
            This invitation link is invalid or has already been used.
          </p>
          <Button asChild>
            <Link to="/sign-in">Go to Sign In</Link>
          </Button>
        </div>
      </div>
    );
  }

  // Accepted state
  if (status === 'accepted') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
        <div className="w-full max-w-md text-center">
          <div className="relative inline-block mb-6">
            <div className="size-24 rounded-full bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center"
              style={{ boxShadow: '0 0.5rem 1.5rem rgba(34, 197, 94, 0.3)' }}
            >
              <CheckCircle2 className="size-12 text-white" />
            </div>
            <div className="absolute inset-0 rounded-full bg-green-500 opacity-20 animate-ping" />
          </div>
          <h1 className="mb-2">Welcome aboard! 🎉</h1>
          <p className="text-sm text-muted-foreground mb-6">
            You've successfully joined <span className="font-medium text-[var(--color-violet-500)]">{invitation?.organizationName}</span>
            {invitation?.accountName && (
              <> and have access to the <span className="font-medium text-[var(--color-violet-500)]">{invitation.accountName}</span> account</>
            )}
          </p>
          <Button 
            asChild
            className="bg-[#F97066] hover:bg-[#e85f55] text-white gap-2"
            style={{ boxShadow: '0 0.25rem 0.75rem rgba(249, 112, 102, 0.3)' }}
          >
            <Link to="/">
              Get Started
              <ArrowRight className="size-4" />
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  // Valid invitation - show details and accept/decline options
  return (
    <div className="min-h-screen bg-gradient-to-br from-[var(--color-violet-50)] via-[var(--color-bg-default)] to-[var(--color-blue-50)] flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center size-16 rounded-[var(--radius-lg)] bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] mb-4"
            style={{ boxShadow: 'var(--shadow-color-violet)' }}
          >
            {invitation?.type === 'organization' ? (
              <Building2 className="size-8 text-white" />
            ) : (
              <Users className="size-8 text-white" />
            )}
          </div>
          <h1 className="mb-2">You're invited!</h1>
          <p className="text-sm text-muted-foreground">
            Join your team on KEN-E
          </p>
        </div>

        {/* Invitation Details Card */}
        <div className="bg-card rounded-[var(--radius-lg)] border-2 border-[var(--color-border-default)] p-6 shadow-lg mb-6">
          <div className="space-y-4">
            {/* Inviter Info */}
            <div className="flex items-start gap-4 pb-4 border-b border-[var(--color-border-default)]">
              <div className="size-12 rounded-full bg-gradient-to-br from-[var(--color-violet-500)] to-[var(--color-blue-500)] flex items-center justify-center shrink-0 text-white font-medium">
                {invitation?.inviterName.split(' ').map(n => n[0]).join('')}
              </div>
              <div>
                <p className="text-sm font-medium">{invitation?.inviterName}</p>
                <p className="text-xs text-muted-foreground">{invitation?.inviterEmail}</p>
                <p className="text-xs text-muted-foreground mt-1">invited you to join</p>
              </div>
            </div>

            {/* Invitation Details */}
            <div className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground mb-1">
                  {invitation?.type === 'organization' ? 'Organization' : 'Account'}
                </p>
                <p className="text-sm font-medium">{invitation?.organizationName}</p>
                {invitation?.accountName && (
                  <p className="text-sm text-muted-foreground">{invitation.accountName}</p>
                )}
              </div>

              <div>
                <p className="text-xs text-muted-foreground mb-1">Your role</p>
                <p className="text-sm font-medium">{invitation?.role}</p>
              </div>

              <div className="p-3 rounded-[var(--radius-md)] bg-[var(--color-bg-elevated)]">
                <p className="text-xs text-muted-foreground">
                  This invitation expires on{' '}
                  <span className="font-medium text-[var(--color-text-primary)]">
                    {invitation?.expiresAt.toLocaleDateString('en-US', { 
                      month: 'long', 
                      day: 'numeric', 
                      year: 'numeric' 
                    })}
                  </span>
                </p>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col gap-3 pt-2">
              <Button
                onClick={handleAcceptInvitation}
                disabled={status === 'accepting'}
                className="w-full gap-2 bg-[#F97066] hover:bg-[#e85f55] text-white"
                style={{ boxShadow: '0 0.25rem 0.75rem rgba(249, 112, 102, 0.3)' }}
              >
                {status === 'accepting' ? (
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
                onClick={handleDeclineInvitation}
                disabled={status === 'accepting'}
                className="w-full"
              >
                Decline
              </Button>
            </div>
          </div>
        </div>

        {/* Additional Actions */}
        <div className="text-center space-y-3">
          <p className="text-sm text-muted-foreground">
            Don't have an account?{' '}
            <Link
              to={`/create-account?invitation=${token}&type=${invitation?.type}&inviter=${invitation?.inviterName}`}
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium"
            >
              Create one now
            </Link>
          </p>
          <p className="text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link
              to={`/sign-in?invitation=${token}&type=${invitation?.type}&inviter=${invitation?.inviterName}`}
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)] font-medium"
            >
              Sign in
            </Link>
          </p>
        </div>

        {/* Contact Support */}
        <div className="mt-6 text-center">
          <p className="text-sm text-muted-foreground">
            Need help?{' '}
            <a
              href="mailto:support@mer-e.com"
              className="text-[var(--color-violet-500)] hover:text-[var(--color-violet-600)]"
            >
              Contact Support
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}