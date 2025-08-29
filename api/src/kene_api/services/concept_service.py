"""Service for concept disambiguation using free APIs and Gemini."""

import json
import logging
import os
import uuid
from typing import Any, Optional, ClassVar

import httpx
import vertexai
from vertexai.generative_models import GenerativeModel

from ..models.monitoring_models import (
    ConceptOption,
    ConceptReference,
    ConceptType,
)

logger = logging.getLogger(__name__)


class ConceptDisambiguationService:
    """Service to disambiguate concepts using Wikipedia, Wikidata, and Gemini."""
    
    _http_client: ClassVar[Optional[httpx.AsyncClient]] = None
    _gemini_model_name: ClassVar[Optional[str]] = None

    def __init__(self):
        """Initialize the service with Vertex AI/Gemini."""
        self.gemini_model = None
        
        # Get configuration from environment
        project_id = os.getenv("VERTEX_AI_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT_ID") or "ken-e-dev"
        location = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        
        # Check if we've already successfully initialized a model
        if self._gemini_model_name:
            try:
                vertexai.init(project=project_id, location=location)
                self.gemini_model = GenerativeModel(self._gemini_model_name)
                logger.debug(f"Reused cached Gemini model '{self._gemini_model_name}'")
                return
            except Exception as e:
                logger.warning(f"Could not reuse cached model {self._gemini_model_name}: {e}")
                self._gemini_model_name = None
        
        # Try to initialize Gemini
        try:
            vertexai.init(project=project_id, location=location)
            
            # Get model preference from environment or use defaults
            preferred_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
            model_fallbacks = [
                "gemini-2.0-flash-exp",
                "gemini-1.5-flash-002",
                "gemini-1.5-flash",
                "gemini-pro"
            ]
            
            # Try preferred model first
            models_to_try = [preferred_model] + [m for m in model_fallbacks if m != preferred_model]
            
            for model_name in models_to_try:
                try:
                    self.gemini_model = GenerativeModel(model_name)
                    self._gemini_model_name = model_name  # Cache successful model
                    logger.info(f"Successfully initialized Gemini model '{model_name}'")
                    break
                except Exception as model_error:
                    logger.debug(f"Could not initialize model {model_name}: {model_error}")
                    continue
            
            if not self.gemini_model:
                logger.error("Could not initialize any Gemini model variant")
                
        except Exception as ve:
            logger.error(f"Could not initialize Vertex AI: {ve}")
            self.gemini_model = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # HTTP client is now shared class-level, don't close it here
        pass
    
    @classmethod
    async def get_http_client(cls) -> httpx.AsyncClient:
        """Get or create shared HTTP client with connection pooling."""
        if cls._http_client is None or cls._http_client.is_closed:
            cls._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=5.0,
                    read=30.0,
                    write=10.0,
                    pool=5.0
                ),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    keepalive_expiry=30.0
                )
            )
        return cls._http_client
    
    @classmethod
    async def close_http_client(cls):
        """Close the shared HTTP client."""
        if cls._http_client:
            await cls._http_client.aclose()
            cls._http_client = None

    async def search_concepts(self, term: str) -> list[ConceptOption]:
        """
        Search for possible concept interpretations of a term using Gemini.

        Args:
            term: The ambiguous term to search for

        Returns:
            List of possible concept interpretations with confidence scores
        """
        logger.info(f"Searching concepts for term: {term}")
        
        # If Gemini is not available, return empty list
        if not self.gemini_model:
            logger.warning("Gemini model not available for concept search")
            return []

        try:
            # Use Gemini to search and analyze concepts
            concepts = await self._search_with_gemini(term)
            
            # Sort by confidence score
            concepts.sort(key=lambda x: x.confidence_score, reverse=True)
            
            # Limit to top 5 results
            result = concepts[:5]
            logger.info(f"Returning {len(result)} concepts for '{term}'")
            return result

        except Exception as e:
            logger.error(f"Error searching concepts for '{term}': {e}", exc_info=True)
            return []

    async def _search_wikipedia(self, term: str) -> list[ConceptOption]:
        """
        Search Wikipedia for matching articles with extracts.

        Uses the free Wikipedia API.
        """
        try:
            client = await self.get_http_client()
            # First, search for matching titles
            search_url = "https://en.wikipedia.org/w/api.php"
            search_params = {
                "action": "opensearch",
                "search": term,
                "limit": 3,
                "format": "json",
            }
            
            search_response = await client.get(search_url, params=search_params)
            search_response.raise_for_status()
            
            search_data = search_response.json()
            if len(search_data) < 4:
                return []

            titles = search_data[1]
            urls = search_data[3]
            
            if not titles:
                return []

            # Now fetch extracts for the found titles
            extract_params = {
                "action": "query",
                "titles": "|".join(titles),
                "prop": "extracts|pageprops",
                "exintro": True,  # Only get intro
                "explaintext": True,  # Plain text, no HTML
                "exsentences": 2,  # Get first 2 sentences
                "format": "json",
            }
            
            extract_response = await client.get(search_url, params=extract_params)
            extract_response.raise_for_status()
            extract_data = extract_response.json()
            
            pages = extract_data.get("query", {}).get("pages", {})
            
            # Build concepts with real descriptions
            concepts = []
            for i, title in enumerate(titles):
                if i < len(urls):
                    # Find the page data for this title
                    description = None
                    is_disambiguation = False
                    
                    for page_id, page_data in pages.items():
                        if page_data.get("title") == title:
                            extract = page_data.get("extract", "").strip()
                            pageprops = page_data.get("pageprops", {})
                            
                            # Check if it's a disambiguation page
                            if "disambiguation" in pageprops:
                                is_disambiguation = True
                                description = f"Disambiguation page - term with multiple meanings"
                            elif extract:
                                # Clean up the extract
                                description = extract.split("\n")[0]  # Get first paragraph
                                # Check for "may refer to" which indicates disambiguation
                                if "may refer to" in description.lower() or "can refer to" in description.lower():
                                    is_disambiguation = True
                                    description = "Term with multiple meanings - see Wikipedia for options"
                                # Limit to reasonable length
                                elif len(description) > 200:
                                    description = description[:197] + "..."
                            break
                    
                    # If no description found, try to provide something meaningful
                    if not description:
                        if "utilities" in title.lower():
                            description = "Public services such as electricity, gas, water, or telecommunications"
                        else:
                            description = f"See Wikipedia article for details about {title}"
                    
                    # Lower confidence for disambiguation pages
                    confidence = 0.4 if is_disambiguation else 0.7
                    
                    concept = ConceptOption(
                        id=str(uuid.uuid4()),
                        label=title,
                        type=ConceptType.OTHER,  # Will be refined by Gemini
                        description=description,
                        reference=ConceptReference(
                            url=urls[i],
                            title=title,
                            description=description[:100] if description else "",
                            source_type="wikipedia",
                        ),
                        confidence_score=confidence,
                    )
                    concepts.append(concept)

            return concepts

        except httpx.TimeoutException as e:
            logger.error(f"Wikipedia API timeout for term '{term}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Wikipedia API HTTP error for term '{term}': {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Wikipedia API request error for term '{term}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected Wikipedia search error for term '{term}': {e}")
            return []

    async def _search_wikidata(self, term: str) -> list[ConceptOption]:
        """
        Search Wikidata for matching entities.

        Uses the free Wikidata API.
        """
        try:
            client = await self.get_http_client()
            response = await client.get(
                "https://www.wikidata.org/w/api.php",
                params={
                    "action": "wbsearchentities",
                    "search": term,
                    "language": "en",
                    "limit": 3,
                    "format": "json",
                },
            )
            response.raise_for_status()

            data = response.json()
            search_results = data.get("search", [])

            concepts = []
            for item in search_results:
                # Map Wikidata concept types
                concept_type = self._map_wikidata_type(item.get("description", ""))

                concept = ConceptOption(
                    id=str(uuid.uuid4()),
                    label=item.get("label", term),
                    type=concept_type,
                    description=item.get("description", "")[:200],
                    reference=ConceptReference(
                        url=f"https://www.wikidata.org/wiki/{item.get('id', '')}",
                        title=item.get("label", term),
                        description=item.get("description", "")[:100],
                        source_type="wikidata",
                    ),
                    confidence_score=0.6,  # Default score
                )
                concepts.append(concept)

            return concepts

        except httpx.TimeoutException as e:
            logger.error(f"Wikidata API timeout for term '{term}': {e}")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Wikidata API HTTP error for term '{term}': {e.response.status_code}")
            return []
        except httpx.RequestError as e:
            logger.error(f"Wikidata API request error for term '{term}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected Wikidata search error for term '{term}': {e}")
            return []

    def _map_wikidata_type(self, description: str) -> ConceptType:
        """Map Wikidata description to our concept types."""
        description_lower = description.lower()

        if any(word in description_lower for word in ["company", "corporation", "firm"]):
            return ConceptType.COMPANY
        elif any(word in description_lower for word in ["city", "country", "state", "region"]):
            return ConceptType.LOCATION
        elif any(word in description_lower for word in ["person", "human", "individual"]):
            return ConceptType.PERSON
        elif any(word in description_lower for word in ["product", "software", "application"]):
            return ConceptType.PRODUCT
        elif any(word in description_lower for word in ["event", "conference", "festival"]):
            return ConceptType.EVENT
        else:
            return ConceptType.TOPIC

    async def _search_with_gemini(self, term: str) -> list[ConceptOption]:
        """
        Use Gemini to search for and identify concept interpretations.
        
        Gemini will search the web and find authoritative sources for each interpretation.
        """
        try:
            prompt = f"""You are a concept disambiguation expert. Search the web and identify different meanings of the term "{term}".

For each distinct meaning, provide:
1. The specific interpretation (e.g., "Apple Inc." vs "apple fruit")
2. The type of concept (company, location, person, product, event, topic, other)
3. A clear, concise description (50-150 characters)
4. A URL to an authoritative source (prefer in this order: official website for companies/products, Wikipedia for general topics, Reuters/Bloomberg for business entities, Britannica for academic topics, official government sites for locations)
5. A confidence score (0-1) based on how likely this interpretation is what users typically mean

Focus on:
- Current, relevant interpretations (not obsolete or highly obscure meanings)
- Well-established entities and concepts
- Clear disambiguation between similar terms

Return ONLY valid JSON in this exact format:
{{
    "concepts": [
        {{
            "label": "Exact name of the concept",
            "type": "company|location|person|product|event|topic|other",
            "description": "Brief, informative description",
            "url": "https://...",
            "confidence": 0.95
        }}
    ]
}}

Important:
- Return ONLY the JSON, no other text
- Include up to 5 most relevant interpretations
- Ensure all URLs are valid and accessible
- Order by relevance/confidence (highest first)"""

            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Extract JSON from response
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]
            
            gemini_data = json.loads(response_text)
            
            concepts = []
            for concept_data in gemini_data.get("concepts", []):
                concept = ConceptOption(
                    id=str(uuid.uuid4()),
                    label=concept_data.get("label", term),
                    type=ConceptType(concept_data.get("type", "other")),
                    description=concept_data.get("description", "")[:200],
                    reference=ConceptReference(
                        url=concept_data.get("url", f"https://www.google.com/search?q={term}"),
                        title=concept_data.get("label", term),
                        description=concept_data.get("description", "")[:100],
                        source_type=self._determine_source_type(concept_data.get("url", "")),
                    ),
                    confidence_score=concept_data.get("confidence", 0.5),
                )
                concepts.append(concept)
            
            return concepts
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini response as JSON for term '{term}': {e}")
            return []
        except AttributeError as e:
            logger.error(f"Gemini model not properly initialized for term '{term}': {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected Gemini search error for term '{term}': {e}")
            return []
    
    def _determine_source_type(self, url: str) -> str:
        """Determine the source type from URL."""
        url_lower = url.lower()
        if "wikipedia.org" in url_lower:
            return "wikipedia"
        elif "wikidata.org" in url_lower:
            return "wikidata"
        elif "reuters.com" in url_lower or "bloomberg.com" in url_lower:
            return "news_source"
        elif "britannica.com" in url_lower:
            return "encyclopedia"
        elif ".gov" in url_lower:
            return "government"
        else:
            return "official_website"

    async def _analyze_with_gemini(
        self, term: str, initial_results: list[ConceptOption]
    ) -> list[ConceptOption]:
        """
        Use Gemini to analyze the term and refine/add concept interpretations.

        Args:
            term: The search term
            initial_results: Results from Wikipedia/Wikidata

        Returns:
            Enhanced list of concept options
        """
        # If Gemini is not available, return initial results
        if not self.gemini_model:
            logger.warning("Gemini model not available, returning initial results only")
            return initial_results
            
        try:
            # Prepare context from initial results
            existing_concepts = []
            for r in initial_results[:3]:
                existing_concepts.append(
                    {
                        "label": r.label,
                        "type": r.type.value,
                        "description": r.description,
                        "url": r.reference.url,
                    }
                )

            prompt = f"""Analyze the term "{term}" and provide possible interpretations.

Existing results from Wikipedia/Wikidata:
{json.dumps(existing_concepts, indent=2) if existing_concepts else "No existing results found"}

Task:
1. Identify what type of concept this might be (company, location, person, product, event, topic, other)
2. List up to 5 most likely interpretations with confidence scores
3. For each, provide a Wikipedia URL if it exists, or suggest where to find more info
4. Consider common ambiguities (e.g., "Apple" as company vs fruit, "Asana" as software vs yoga position)
5. If it's a company, include the company website if known

Return ONLY valid JSON in this exact format:
{{
    "concepts": [
        {{
            "label": "Exact name of the concept",
            "type": "company|location|person|product|event|topic|other",
            "description": "Brief description (50-100 chars)",
            "url": "https://en.wikipedia.org/wiki/... or company website",
            "confidence": 0.95
        }}
    ]
}}

Important:
- Return ONLY the JSON, no other text
- Ensure all URLs are valid and start with https://
- Confidence scores should be between 0 and 1
- Order by confidence (highest first)"""

            response = self.gemini_model.generate_content(prompt)
            response_text = response.text.strip()

            # Extract JSON from response (in case there's extra text)
            json_start = response_text.find("{")
            json_end = response_text.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                response_text = response_text[json_start:json_end]

            gemini_data = json.loads(response_text)

            # Merge Gemini results with existing ones
            concept_map = {c.label.lower(): c for c in initial_results}

            for gemini_concept in gemini_data.get("concepts", []):
                label = gemini_concept.get("label", "")
                label_lower = label.lower()

                # Check if we already have this concept
                if label_lower in concept_map:
                    # Update existing concept with Gemini's analysis
                    existing = concept_map[label_lower]
                    existing.confidence_score = gemini_concept.get("confidence", 0.5)
                    existing.type = ConceptType(
                        gemini_concept.get("type", ConceptType.OTHER)
                    )
                else:
                    # Add new concept from Gemini
                    new_concept = ConceptOption(
                        id=str(uuid.uuid4()),
                        label=label,
                        type=ConceptType(gemini_concept.get("type", ConceptType.OTHER)),
                        description=gemini_concept.get("description", "")[:200],
                        reference=ConceptReference(
                            url=gemini_concept.get("url", f"https://www.google.com/search?q={term}"),
                            title=label,
                            description=gemini_concept.get("description", "")[:100],
                            source_type="gemini_search",
                        ),
                        confidence_score=gemini_concept.get("confidence", 0.5),
                    )
                    concept_map[label_lower] = new_concept

            return list(concept_map.values())

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Gemini analysis response as JSON for term '{term}': {e}")
            return initial_results
        except AttributeError as e:
            logger.error(f"Gemini model not properly initialized for analysis of term '{term}': {e}")
            return initial_results
        except Exception as e:
            logger.error(f"Unexpected Gemini analysis error for term '{term}': {e}")
            return initial_results


async def get_concept_service() -> ConceptDisambiguationService:
    """Dependency injection for concept service."""
    return ConceptDisambiguationService()