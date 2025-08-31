"""
Utilities for managing strategy document artifacts.
Following BP-C4: Simple, composable, testable functions.
"""

import logging
import os
from typing import List, Optional, Tuple

from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import storage
from google.genai.types import Part

logger = logging.getLogger(__name__)

# Artifact naming convention: uploaded strategy documents are prefixed with this
UPLOADED_STRATEGY_PREFIX = "input_strategy_"


def parse_gcs_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse a GCS URL into bucket name and blob path.
    
    Args:
        url: GCS URL in format gs://bucket/path/to/file
        
    Returns:
        Tuple of (bucket_name, blob_path) or (None, None) if invalid
        
    Examples:
        >>> parse_gcs_url("gs://my-bucket/path/to/file.pdf")
        ('my-bucket', 'path/to/file.pdf')
        >>> parse_gcs_url("invalid-url")
        (None, None)
    """
    if not url or not url.startswith("gs://"):
        logger.warning(f"Invalid GCS URL format: {url}")
        return None, None
    
    # Remove gs:// prefix and split
    path = url[5:]
    parts = path.split("/", 1)
    
    bucket_name = parts[0] if parts else None
    blob_path = parts[1] if len(parts) > 1 else ""
    
    return bucket_name, blob_path


def determine_artifact_bucket(
    uploaded_documents: List[str], 
    environment: Optional[str] = None
) -> str:
    """
    Determine the appropriate GCS bucket for artifacts.
    
    Args:
        uploaded_documents: List of GCS URLs
        environment: Environment name (development/staging/production)
        
    Returns:
        Bucket name to use for artifacts
        
    Examples:
        >>> determine_artifact_bucket(["gs://ken-e-dev-files-us/file.pdf"])
        'ken-e-dev-files-us'
        >>> determine_artifact_bucket([], "staging")
        'ken-e-staging-files-us'
    """
    # If we have uploaded documents, extract bucket from first URL
    if uploaded_documents and uploaded_documents[0].startswith("gs://"):
        bucket_name, _ = parse_gcs_url(uploaded_documents[0])
        if bucket_name:
            return bucket_name
    
    # Fall back to environment-based naming
    if environment is None:
        environment = os.getenv("ENVIRONMENT", "development").lower()
    
    return f"ken-e-{environment}-files-us"


def create_artifact_from_gcs(
    storage_client: storage.Client,
    bucket_name: str,
    blob_path: str
) -> Tuple[Optional[Part], str]:
    """
    Download a GCS blob and create an artifact Part.
    
    Args:
        storage_client: Initialized GCS client
        bucket_name: Name of the GCS bucket
        blob_path: Path to the blob in the bucket
        
    Returns:
        Tuple of (artifact Part, filename) or (None, filename) if error
        
    Note:
        This function performs I/O and should be mocked in unit tests.
    """
    filename = blob_path.split('/')[-1] if blob_path else "unknown"
    
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        logger.info(f"Downloading document: {blob_path} from {bucket_name}")
        doc_content = blob.download_as_bytes()
        
        artifact = Part.from_bytes(
            data=doc_content,
            mime_type=blob.content_type or "application/octet-stream"
        )
        
        return artifact, filename
        
    except Exception as e:
        logger.error(f"Failed to download {blob_path} from {bucket_name}: {e}")
        return None, filename


def save_artifact_to_service(
    artifact_service,
    artifact: Part,
    filename: str,
    session_user_id: str,
    session_id: str
) -> bool:
    """
    Save an artifact to the artifact service.
    
    Args:
        artifact_service: GcsArtifactService or InMemoryArtifactService
        artifact: The Part object to save
        filename: Name for the artifact
        session_user_id: User ID for the session
        session_id: Session ID
        
    Returns:
        True if saved successfully, False otherwise
    """
    try:
        artifact_filename = f"{UPLOADED_STRATEGY_PREFIX}{filename}"
        artifact_service.save_artifact_sync(
            filename=artifact_filename,
            artifact=artifact,
            user_id=session_user_id,
            session_id=session_id
        )
        logger.info(f"Saved artifact: {artifact_filename}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to save artifact {filename}: {e}")
        return False


def load_uploaded_documents_as_artifacts(
    uploaded_documents: Optional[List[str]],
    account_id: str,
    session_user_id: str,
    session_id: str,
    project_id: Optional[str] = None,
    storage_client: Optional[storage.Client] = None,
    artifact_service = None
):
    """
    Load uploaded documents from GCS and save as artifacts.
    
    This is the main function that orchestrates artifact loading.
    It's composed of smaller, testable functions.
    
    Args:
        uploaded_documents: List of GCS URLs for uploaded documents
        account_id: Account ID for namespacing
        session_user_id: User ID for the session
        session_id: Session ID
        project_id: Optional GCP project ID
        storage_client: Optional injected storage client (for testing)
        artifact_service: Optional injected artifact service (for testing)
        
    Returns:
        Configured artifact service (GcsArtifactService or InMemoryArtifactService)
        
    Examples:
        >>> service = load_uploaded_documents_as_artifacts(
        ...     ["gs://bucket/doc.pdf"],
        ...     "acc_123",
        ...     "user_456",
        ...     "session_789"
        ... )
    """
    # If no documents, return in-memory service
    if not uploaded_documents:
        logger.info("No uploaded documents, using InMemoryArtifactService")
        return artifact_service or InMemoryArtifactService()
    
    # Determine bucket and set up artifact service if not provided
    if artifact_service is None:
        try:
            bucket_name = determine_artifact_bucket(uploaded_documents)
            logger.info(f"Setting up GcsArtifactService with bucket: {bucket_name}")
            artifact_service = GcsArtifactService(
                bucket_name=bucket_name,
                namespace=f"accounts/{account_id}/artifacts"
            )
        except Exception as e:
            logger.error(f"Failed to set up GcsArtifactService: {e}")
            artifact_service = InMemoryArtifactService()
    
    # Initialize storage client if not provided
    if storage_client is None:
        storage_client = storage.Client(project=project_id)
    
    # Load each document as an artifact
    success_count = 0
    for doc_url in uploaded_documents:
        bucket_name, blob_path = parse_gcs_url(doc_url)
        
        if not bucket_name or not blob_path:
            continue
        
        artifact, filename = create_artifact_from_gcs(
            storage_client, bucket_name, blob_path
        )
        
        if artifact:
            if save_artifact_to_service(
                artifact_service, artifact, filename, 
                session_user_id, session_id
            ):
                success_count += 1
    
    logger.info(f"Successfully loaded {success_count}/{len(uploaded_documents)} documents as artifacts")
    
    return artifact_service