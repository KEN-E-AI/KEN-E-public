import pytest
from httpx import ASGITransport, AsyncClient
from src.kene_api.main import app


@pytest.mark.asyncio
async def test_read_root():
    """Test the root endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Welcome to Kene API"
    assert data["version"] == "1.0.0"
    assert data["docs"] == "/docs"
    assert data["redoc"] == "/redoc"


@pytest.mark.asyncio
async def test_health_check():
    """Test the health check endpoint returns appropriate status code."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/health")
    data = response.json()
    # In test environment, Neo4j/Firestore not available, so status is degraded (503)
    # In production with healthy deps, status is healthy (200)
    assert response.status_code in [200, 503]
    assert data["status"] in ["healthy", "degraded"]
    # Status code should match the status field
    if data["status"] == "healthy":
        assert response.status_code == 200
    else:
        assert response.status_code == 503
    assert data["message"] == "API is running"
    assert "services" in data
    assert "neo4j" in data["services"]
    assert "firestore" in data["services"]
    assert "redis" in data["services"]


@pytest.mark.asyncio
async def test_readiness_check():
    """Test the readiness probe endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/ready")
    # In test environment, critical services not available, so returns 503
    assert response.status_code in [200, 503]
    if response.status_code == 200:
        assert response.text == "Ready"
    else:
        assert response.text == "Not Ready"


@pytest.mark.asyncio
async def test_get_metrics():
    """Test retrieving metrics - expects 503 when Neo4j unavailable."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/metrics/?account_id=test123")
    # Since Neo4j is not available in test environment, expect 503
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "Database service unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_create_metric():
    """Test creating a new metric - expects 503 when Neo4j unavailable."""
    metric_data = {
        "account_id": "test123",
        "d3_format": ".2f",
        "verbose_name": "Test Metric",
        "expression": "COUNT(*)",
        "metric_name": "test_metric",
        "account_components": ["test", "example"],
        "related_dataset_id": 1,
        "related_dataset_name": "test_dataset",
        "related_dataset_products": ["test_product"],
        "description": "A test metric for validation",
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.post("/api/v1/metrics/", json=metric_data)
    # Since Neo4j is not available in test environment, expect 503
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "Database service unavailable" in data["detail"]


@pytest.mark.asyncio
async def test_get_activities():
    """Test retrieving activities - expects 503 when Neo4j unavailable."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/activities/?account_id=test123")
    # Since Neo4j is not available in test environment, expect 503
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert "Database service unavailable" in data["detail"]
