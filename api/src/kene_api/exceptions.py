"""Custom exceptions for KEN-E API."""


class SecretManagerError(Exception):
    """Raised when Secret Manager operations fail."""

    def __init__(
        self, message: str, env_var: str | None = None, secret_path: str | None = None
    ):
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


# ==================== KNOWLEDGE GRAPH EXCEPTIONS ====================


class NodeCreationException(Exception):
    """Raised when node creation fails in the graph database."""

    def __init__(self, node_type: str, account_id: str, reason: str | None = None):
        self.node_type = node_type
        self.account_id = account_id
        self.reason = reason
        message = f"Failed to create {node_type} in account '{account_id}'"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class NodeNotFoundException(Exception):
    """Raised when a graph node is not found."""

    def __init__(self, node_type: str, node_id: str):
        self.node_type = node_type
        self.node_id = node_id
        super().__init__(f"{node_type} with node_id '{node_id}' not found")


class NodeHasDependenciesException(Exception):
    """Raised when attempting to delete a node that has dependent child nodes."""

    def __init__(self, node_type: str, node_id: str, dependency_type: str, count: int):
        self.node_type = node_type
        self.node_id = node_id
        self.dependency_type = dependency_type
        self.count = count
        super().__init__(
            f"Cannot delete {node_type} '{node_id}': has {count} dependent {dependency_type}(s)"
        )


class DuplicateNodeException(Exception):
    """Raised when attempting to create a node with a duplicate name within the same account."""

    def __init__(
        self, node_type: str, field_name: str, field_value: str, account_id: str
    ):
        self.node_type = node_type
        self.field_name = field_name
        self.field_value = field_value
        self.account_id = account_id
        super().__init__(
            f"{node_type} with {field_name} '{field_value}' already exists in account '{account_id}'"
        )


class ValidationException(Exception):
    """Raised when input validation fails for graph operations."""

    def __init__(self, message: str, field_name: str | None = None):
        self.field_name = field_name
        super().__init__(message)


class ServiceUnavailableError(Exception):
    """Raised when a required upstream service (Neo4j, Firestore, Agent Engine) is unreachable.

    Callers should surface this as HTTP 503.
    """

    def __init__(self, service: str, reason: str, error_id: str | None = None):
        self.service = service
        self.error_id = error_id
        super().__init__(f"{service} unavailable: {reason}")


class GraphSyncException(Exception):
    """Raised when Neo4j and Firestore synchronization fails."""

    def __init__(
        self, message: str, operation: str, node_type: str, node_id: str | None = None
    ):
        self.operation = operation
        self.node_type = node_type
        self.node_id = node_id
        super().__init__(
            f"Graph sync failed during {operation} of {node_type}: {message}"
        )
