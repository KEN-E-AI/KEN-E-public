import os

from dotenv import load_dotenv

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
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username: str = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "password")
    neo4j_database: str = os.getenv("NEO4J_DATABASE", "neo4j")

    # Apache Superset settings
    superset_base_url: str = os.getenv("SUPERSET_BASE_URL", "http://localhost:8088")
    superset_username: str = os.getenv("SUPERSET_USERNAME", "admin")
    superset_password: str = os.getenv("SUPERSET_PASSWORD", "admin")
    superset_database_id: int = int(os.getenv("SUPERSET_DATABASE_ID", "2"))

    # CORS settings
    allowed_origins: list[str] = ["*"]  # Configure for production
    allowed_methods: list[str] = ["*"]
    allowed_headers: list[str] = ["*"]


settings = Settings()
