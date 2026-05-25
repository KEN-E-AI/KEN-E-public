import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add root directory to path to import shared package
root_dir = Path(__file__).parent.parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from shared.secrets import get_env_or_secret

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings."""

    app_name: str = "Kene API"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    reload: bool = os.getenv("RELOAD", "false").lower() == "true"

    # Neo4j database settings
    neo4j_uri: str = get_env_or_secret("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = get_env_or_secret("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = get_env_or_secret("NEO4J_PASSWORD", "password")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")
    # Seconds the driver retries a failed managed transaction before giving up.
    # Default 30.0 = Neo4j driver default (unchanged for prod/staging/dev). Set
    # low in CI/e2e (which has no Neo4j) so a transaction against an unreachable
    # Neo4j fails fast instead of stalling the request with ~30s of backoffs.
    neo4j_max_transaction_retry_time: float = float(
        os.getenv("NEO4J_MAX_TRANSACTION_RETRY_TIME", "30.0")
    )

    # Apache Superset settings
    superset_base_url: str = os.getenv("SUPERSET_BASE_URL", "http://localhost:8088")
    superset_username: str = os.getenv("SUPERSET_USERNAME", "admin")
    superset_password: str = get_env_or_secret("SUPERSET_PASSWORD", "admin")
    superset_database_id: int = int(os.getenv("SUPERSET_DATABASE_ID", "2"))

    # CORS settings
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")
    cors_methods: str = os.getenv("CORS_METHODS", "*")
    cors_headers: str = os.getenv("CORS_HEADERS", "*")

    # reCAPTCHA settings
    RECAPTCHA_SITE_KEY: str = get_env_or_secret("RECAPTCHA_SITE_KEY", "")
    RECAPTCHA_SECRET_KEY: str = get_env_or_secret("RECAPTCHA_SECRET_KEY", "")

    # Organization creation settings
    # Options: "all" (any authenticated user), "super_admin" (only super admins), "none" (disabled)
    organization_creation_permission: str = os.getenv(
        "ORGANIZATION_CREATION_PERMISSION", "all"
    )

    # Rate-limit bypass for the chat-sidebar load-test user.
    # When set, requests carrying a Firebase ID token for this UID skip the
    # per-IP authenticated-request rate limiter so the 1000-VU sidebar load
    # test (which originates from a single Cloud Build egress IP) is not
    # throttled by the production 60-req/min ceiling.  Must be empty in
    # production; set only on staging where the load test runs.
    load_test_bypass_uid: str = os.getenv("LOAD_TEST_BYPASS_UID", "")

    # E2E test bypass token — skips Firebase token verification entirely and
    # synthesises a UserContext from the bearer token value:
    #   bearer == API_TEST_BYPASS_TOKEN           → non-member (empty account_permissions)
    #   bearer == API_TEST_BYPASS_TOKEN:{acct_id} → member of {acct_id} with "edit" role
    # Must be empty in production; set only in the E2E test environment.
    api_test_bypass_token: str = os.getenv("API_TEST_BYPASS_TOKEN", "")


settings = Settings()
