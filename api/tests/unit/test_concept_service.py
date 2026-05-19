"""Unit tests for concept disambiguation service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.kene_api.models.monitoring_models import (
    ConceptType,
)
from src.kene_api.services.concept_service import ConceptDisambiguationService


class TestConceptDisambiguationService:
    """Test concept disambiguation service."""

    @pytest.fixture
    def mock_gemini_model(self):
        """Mock Gemini model."""
        with patch("src.kene_api.services.concept_service.GenerativeModel") as mock:
            yield mock

    @pytest.fixture
    def mock_vertexai_init(self):
        """Mock Vertex AI initialization."""
        with patch("src.kene_api.services.concept_service.vertexai.init") as mock:
            yield mock

    @pytest.fixture
    def service(self, mock_gemini_model, mock_vertexai_init):
        """Create service instance with mocked dependencies."""
        with patch.dict(
            "os.environ",
            {
                "VERTEX_AI_PROJECT_ID": "test-project",
                "VERTEX_AI_LOCATION": "us-central1",
                "GEMINI_MODEL": "gemini-2.5-pro",
            },
        ):
            # Mock the model initialization to succeed
            mock_model_instance = MagicMock()
            mock_gemini_model.return_value = mock_model_instance

            service = ConceptDisambiguationService()
            service.gemini_model = mock_model_instance
            return service

    @pytest.fixture
    def mock_http_client(self):
        """Mock HTTP client for API calls."""
        with patch.object(ConceptDisambiguationService, "get_http_client") as mock:
            client = AsyncMock(spec=httpx.AsyncClient)
            mock.return_value = client
            yield client

    @pytest.mark.asyncio
    async def test_search_concepts_success(self, service):
        """Test successful concept search with Gemini."""
        # Mock Gemini response
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "concepts": [
                    {
                        "label": "Apple Inc.",
                        "type": "company",
                        "description": "Technology company based in Cupertino",
                        "url": "https://apple.com",
                        "confidence": 0.95,
                    },
                    {
                        "label": "Apple (fruit)",
                        "type": "topic",
                        "description": "Edible fruit from apple trees",
                        "url": "https://en.wikipedia.org/wiki/Apple",
                        "confidence": 0.75,
                    },
                ]
            }
        )
        service.gemini_model.generate_content.return_value = mock_response

        # Test
        concepts = await service.search_concepts("Apple")

        # Assertions
        assert len(concepts) == 2
        assert concepts[0].label == "Apple Inc."
        assert concepts[0].type == ConceptType.COMPANY
        assert concepts[0].confidence_score == 0.95
        assert concepts[0].reference.url == "https://apple.com"

        assert concepts[1].label == "Apple (fruit)"
        assert concepts[1].type == ConceptType.TOPIC
        assert concepts[1].confidence_score == 0.75

    @pytest.mark.asyncio
    async def test_search_concepts_no_gemini(self):
        """Test behavior when Gemini is not available."""
        service = ConceptDisambiguationService()
        service.gemini_model = None

        concepts = await service.search_concepts("test")

        assert concepts == []

    @pytest.mark.asyncio
    async def test_search_concepts_gemini_error(self, service):
        """Test handling of Gemini errors."""
        service.gemini_model.generate_content.side_effect = Exception("API error")

        concepts = await service.search_concepts("test")

        assert concepts == []

    @pytest.mark.asyncio
    async def test_search_concepts_invalid_json(self, service):
        """Test handling of invalid JSON from Gemini."""
        mock_response = MagicMock()
        mock_response.text = "Invalid JSON response"
        service.gemini_model.generate_content.return_value = mock_response

        concepts = await service.search_concepts("test")

        assert concepts == []

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Async mock setup is incorrect for current httpx/concept_service API — needs rewrite — see DM-85"
    )
    async def test_search_wikipedia_success(self, service, mock_http_client):
        """Test successful Wikipedia search."""
        # Mock Wikipedia API responses
        search_response = AsyncMock()
        search_response.json.return_value = [
            "search query",
            ["Apple Inc.", "Apple"],
            ["", ""],
            [
                "https://en.wikipedia.org/wiki/Apple_Inc.",
                "https://en.wikipedia.org/wiki/Apple",
            ],
        ]
        search_response.raise_for_status = AsyncMock()

        extract_response = AsyncMock()
        extract_response.json.return_value = {
            "query": {
                "pages": {
                    "1": {
                        "title": "Apple Inc.",
                        "extract": "Apple Inc. is an American multinational technology company.",
                        "pageprops": {},
                    },
                    "2": {
                        "title": "Apple",
                        "extract": "An apple is an edible fruit produced by an apple tree.",
                        "pageprops": {},
                    },
                }
            }
        }
        extract_response.raise_for_status = AsyncMock()

        mock_http_client.get.side_effect = [search_response, extract_response]

        # Test
        concepts = await service._search_wikipedia("Apple")

        # Assertions
        assert len(concepts) == 2
        assert concepts[0].label == "Apple Inc."
        assert "technology company" in concepts[0].description.lower()
        assert concepts[0].reference.source_type == "wikipedia"

    @pytest.mark.asyncio
    async def test_search_wikipedia_timeout(self, service, mock_http_client):
        """Test handling of Wikipedia API timeout."""
        mock_http_client.get.side_effect = httpx.TimeoutException("Request timeout")

        concepts = await service._search_wikipedia("test")

        assert concepts == []

    @pytest.mark.asyncio
    async def test_search_wikipedia_http_error(self, service, mock_http_client):
        """Test handling of Wikipedia API HTTP errors."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_http_client.get.side_effect = httpx.HTTPStatusError(
            "Server error", request=None, response=mock_response
        )

        concepts = await service._search_wikipedia("test")

        assert concepts == []

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Async mock setup is incorrect for current httpx/concept_service API — needs rewrite — see DM-85"
    )
    async def test_search_wikidata_success(self, service, mock_http_client):
        """Test successful Wikidata search."""
        response = AsyncMock()
        response.json.return_value = {
            "search": [
                {
                    "id": "Q312",
                    "label": "Apple Inc.",
                    "description": "American technology company",
                },
                {"id": "Q89", "label": "apple", "description": "fruit"},
            ]
        }
        response.raise_for_status = AsyncMock()
        mock_http_client.get.return_value = response

        # Test
        concepts = await service._search_wikidata("Apple")

        # Assertions
        assert len(concepts) == 2
        assert concepts[0].label == "Apple Inc."
        assert concepts[0].type == ConceptType.COMPANY
        assert concepts[0].reference.source_type == "wikidata"
        assert "Q312" in concepts[0].reference.url

    @pytest.mark.asyncio
    async def test_map_wikidata_type(self, service):
        """Test Wikidata type mapping."""
        assert (
            service._map_wikidata_type("American technology company")
            == ConceptType.COMPANY
        )
        assert service._map_wikidata_type("city in California") == ConceptType.LOCATION
        assert (
            service._map_wikidata_type("American businessperson") == ConceptType.PERSON
        )
        assert service._map_wikidata_type("software product") == ConceptType.PRODUCT
        assert service._map_wikidata_type("annual conference") == ConceptType.EVENT
        assert service._map_wikidata_type("general concept") == ConceptType.TOPIC

    @pytest.mark.asyncio
    async def test_determine_source_type(self, service):
        """Test source type determination from URL."""
        assert (
            service._determine_source_type("https://en.wikipedia.org/wiki/Apple")
            == "wikipedia"
        )
        assert (
            service._determine_source_type("https://www.wikidata.org/wiki/Q312")
            == "wikidata"
        )
        assert (
            service._determine_source_type("https://www.reuters.com/article/123")
            == "news_source"
        )
        assert (
            service._determine_source_type("https://www.britannica.com/topic/apple")
            == "encyclopedia"
        )
        assert (
            service._determine_source_type("https://www.irs.gov/forms") == "government"
        )
        assert service._determine_source_type("https://apple.com") == "official_website"

    @pytest.mark.asyncio
    async def test_http_client_pooling(self):
        """Test HTTP client connection pooling."""
        # Reset class-level client
        ConceptDisambiguationService._http_client = None

        # Get client twice
        client1 = await ConceptDisambiguationService.get_http_client()
        client2 = await ConceptDisambiguationService.get_http_client()

        # Should be the same instance
        assert client1 is client2

        # Clean up
        await ConceptDisambiguationService.close_http_client()
        assert ConceptDisambiguationService._http_client is None

    @pytest.mark.asyncio
    @pytest.mark.skip(
        reason="Async mock setup is incorrect for current httpx/concept_service API — needs rewrite — see DM-85"
    )
    async def test_model_caching(self, mock_gemini_model, mock_vertexai_init):
        """Test Gemini model name caching."""
        # Reset class-level cache
        ConceptDisambiguationService._gemini_model_name = None

        with patch.dict(
            "os.environ",
            {
                "VERTEX_AI_PROJECT_ID": "test-project",
                "GEMINI_MODEL": "gemini-2.5-pro",
            },
        ):
            # First initialization
            mock_model_instance = MagicMock()
            mock_gemini_model.return_value = mock_model_instance

            service1 = ConceptDisambiguationService()
            assert ConceptDisambiguationService._gemini_model_name == "gemini-2.5-pro"

            # Second initialization should use cached name
            mock_gemini_model.reset_mock()
            service2 = ConceptDisambiguationService()

            # Should have tried to use cached model name
            mock_gemini_model.assert_called_once_with("gemini-2.5-pro")

    @pytest.mark.asyncio
    async def test_search_concepts_sorting(self, service):
        """Test that concepts are sorted by confidence score."""
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "concepts": [
                    {
                        "label": "Low confidence",
                        "type": "other",
                        "description": "Low confidence result",
                        "url": "https://example.com/low",
                        "confidence": 0.3,
                    },
                    {
                        "label": "High confidence",
                        "type": "company",
                        "description": "High confidence result",
                        "url": "https://example.com/high",
                        "confidence": 0.9,
                    },
                    {
                        "label": "Medium confidence",
                        "type": "topic",
                        "description": "Medium confidence result",
                        "url": "https://example.com/medium",
                        "confidence": 0.6,
                    },
                ]
            }
        )
        service.gemini_model.generate_content.return_value = mock_response

        concepts = await service.search_concepts("test")

        # Should be sorted by confidence (highest first)
        assert len(concepts) == 3
        assert concepts[0].confidence_score == 0.9
        assert concepts[1].confidence_score == 0.6
        assert concepts[2].confidence_score == 0.3

    @pytest.mark.asyncio
    async def test_search_concepts_limit(self, service):
        """Test that results are limited to top 5."""
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "concepts": [
                    {
                        "label": f"Concept {i}",
                        "type": "topic",
                        "description": f"Description {i}",
                        "url": f"https://example.com/{i}",
                        "confidence": 0.9 - (i * 0.1),
                    }
                    for i in range(10)
                ]
            }
        )
        service.gemini_model.generate_content.return_value = mock_response

        concepts = await service.search_concepts("test")

        # Should be limited to 5 results
        assert len(concepts) == 5
        assert concepts[0].label == "Concept 0"
        assert concepts[4].label == "Concept 4"
