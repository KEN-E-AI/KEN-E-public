"""Custom exceptions for KEN-E API."""


class SecretManagerError(Exception):
    """Raised when Secret Manager operations fail."""

    def __init__(self, message: str, env_var: str | None = None, secret_path: str | None = None):
        super().__init__(message)
        self.env_var = env_var
        self.secret_path = secret_path

    def __str__(self):
        """Return detailed error message."""
        base_msg = super().__str__()
        if self.env_var:
            base_msg += f" (env_var: {self.env_var})"
        if self.secret_path:
            base_msg += f" (path: {self.secret_path})"
        return base_msg


class EmailServiceInitializationError(Exception):
    """Raised when email service fails to initialize."""
    pass

