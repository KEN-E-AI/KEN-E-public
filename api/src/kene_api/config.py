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


settings = Settings()
