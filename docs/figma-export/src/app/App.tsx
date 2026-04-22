import { Component, ReactNode } from 'react';
import { RouterProvider } from 'react-router';
import { ThemeProvider } from './components/ThemeProvider';
import { createRouter } from './routes';
import { BackgroundEffects } from './components/BackgroundEffects';
import { ActivitiesProvider } from './contexts/ActivitiesContext';
import { ToastProvider } from './components/ToastProvider';

// CRITICAL: Router must be created outside the component body
// to avoid creating a new router instance on every render.
let router: ReturnType<typeof createRouter> | null = null;
try {
  router = createRouter();
} catch (e) {
  console.error('Failed to create router:', e);
}

// Error boundary to prevent uncaught rendering errors from crashing the app
class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif' }}>
          <h2 style={{ color: '#EF4444', marginBottom: 8 }}>Something went wrong</h2>
          <p style={{ color: '#64748B' }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App() {
  if (!router) {
    return (
      <div style={{ padding: 32, fontFamily: 'system-ui, sans-serif' }}>
        <h2 style={{ color: '#EF4444' }}>Failed to initialize router</h2>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ActivitiesProvider>
          <ToastProvider>
            <BackgroundEffects />
            <RouterProvider router={router} />
          </ToastProvider>
        </ActivitiesProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}