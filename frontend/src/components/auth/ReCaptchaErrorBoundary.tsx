import React, { Component, ErrorInfo, ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ReCaptchaErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      "ReCAPTCHA Error Boundary caught an error:",
      error,
      errorInfo,
    );
  }

  render() {
    if (this.state.hasError) {
      console.warn("ReCAPTCHA failed to load, proceeding without it");
      // Return children without ReCAPTCHA functionality
      return this.props.fallback || this.props.children;
    }

    return this.props.children;
  }
}

export default ReCaptchaErrorBoundary;
