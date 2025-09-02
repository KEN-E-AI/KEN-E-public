"""
Document processing utilities for strategy agents.
Following BP-C4: Simple, composable, testable functions.
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import datetime
import io

logger = logging.getLogger(__name__)

# Constants (consistent with existing patterns like CACHE_MAX_SIZE)
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB per document
MAX_TOTAL_SIZE = 50 * 1024 * 1024      # 50MB total for all documents
MAX_TEXT_LENGTH = 500_000              # ~500K chars max per document
MAX_PDF_PAGES = 100                    # Limit PDF pages to prevent timeout
SUPPORTED_FORMATS = {'.pdf', '.txt', '.md', '.docx'}


class DocumentProcessingError(Exception):
    """Base exception for document processing errors."""
    pass


class DocumentSizeError(DocumentProcessingError):
    """Raised when document exceeds size limits."""
    pass


class DocumentFormatError(DocumentProcessingError):
    """Raised when document format is not supported."""
    pass


def create_error_context(error: Exception, operation: str) -> Dict[str, any]:
    """Create structured error context for logging."""
    return {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "operation": operation,
        "timestamp": datetime.utcnow().isoformat()
    }


def validate_document_size(content_bytes: bytes, filename: str) -> None:
    """
    Validate document size against limits.
    Raises DocumentSizeError if too large.
    
    Args:
        content_bytes: Document content as bytes
        filename: Name of the document for error messages
        
    Raises:
        DocumentSizeError: If document exceeds MAX_DOCUMENT_SIZE
    """
    size = len(content_bytes)
    if size > MAX_DOCUMENT_SIZE:
        raise DocumentSizeError(
            f"Document '{filename}' exceeds size limit: "
            f"{size:,} bytes > {MAX_DOCUMENT_SIZE:,} bytes"
        )


def extract_text_from_pdf(pdf_bytes: bytes, filename: str) -> str:
    """
    Extract text from PDF bytes with error handling.
    Following existing pattern from artifact_utils.parse_gcs_url().
    
    Args:
        pdf_bytes: PDF content as bytes
        filename: Name of the PDF file for logging
        
    Returns:
        Extracted text from the PDF
        
    Raises:
        DocumentProcessingError: If PDF extraction fails
    """
    try:
        import PyPDF2
        
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        extracted_text = []
        page_count = min(len(pdf_reader.pages), MAX_PDF_PAGES)
        
        for page_num in range(page_count):
            page = pdf_reader.pages[page_num]
            text = page.extract_text()
            if text:
                extracted_text.append(text)
                
        full_text = "\n".join(extracted_text)
        
        # Truncate if too long
        if len(full_text) > MAX_TEXT_LENGTH:
            logger.warning(
                f"Truncating {filename}: {len(full_text)} chars to {MAX_TEXT_LENGTH}"
            )
            full_text = full_text[:MAX_TEXT_LENGTH] + "\n[TRUNCATED]"
            
        logger.info(f"Extracted {len(full_text)} chars from {filename} ({page_count} pages)")
        return full_text
        
    except ImportError:
        error_msg = f"PyPDF2 not available for {filename}"
        logger.error(error_msg)
        raise DocumentProcessingError(error_msg)
    except Exception as e:
        error_ctx = create_error_context(e, f"extract_pdf:{filename}")
        logger.error(f"PDF extraction failed: {error_ctx}")
        raise DocumentProcessingError(f"Failed to extract text from {filename}: {e}")


def load_document_from_gcs(
    gcs_url: str, 
    storage_client: any  # Using any to avoid import dependency
) -> Tuple[str, str]:
    """
    Load a single document from GCS with validation.
    
    Args:
        gcs_url: GCS URL in format gs://bucket/path/to/file
        storage_client: Google Cloud Storage client
        
    Returns:
        Tuple of (filename, content)
        
    Raises:
        ValueError: If GCS URL is invalid
        DocumentSizeError: If document exceeds size limits
        DocumentProcessingError: If loading fails
    """
    from .artifact_utils import parse_gcs_url  # Reuse existing function
    
    bucket_name, blob_path = parse_gcs_url(gcs_url)
    if not bucket_name or not blob_path:
        raise ValueError(f"Invalid GCS URL: {gcs_url}")
    
    try:
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        # Check size before downloading
        blob.reload()  # Get metadata
        if blob.size and blob.size > MAX_DOCUMENT_SIZE:
            raise DocumentSizeError(
                f"Document at {gcs_url} too large: {blob.size:,} bytes > {MAX_DOCUMENT_SIZE:,} bytes"
            )
        
        # Download content
        content_bytes = blob.download_as_bytes()
        validate_document_size(content_bytes, blob_path)
        
        # Extract text based on format
        filename = blob_path.split('/')[-1]
        
        if filename.lower().endswith('.pdf'):
            logger.info(f"Processing PDF: {filename}")
            content = extract_text_from_pdf(content_bytes, filename)
        elif filename.lower().endswith(('.txt', '.md')):
            logger.info(f"Processing text file: {filename}")
            content = content_bytes.decode('utf-8', errors='ignore')
            # Apply text length limit
            if len(content) > MAX_TEXT_LENGTH:
                logger.warning(f"Truncating {filename}: {len(content)} chars")
                content = content[:MAX_TEXT_LENGTH] + "\n[TRUNCATED]"
        else:
            # For unsupported formats, return placeholder
            logger.warning(f"Unsupported document format: {filename}")
            content = f"[Unsupported format: {filename} - only PDF, TXT, and MD files are supported]"
        
        return filename, content
        
    except (DocumentSizeError, DocumentProcessingError):
        raise  # Re-raise our custom exceptions
    except Exception as e:
        # Handle GCS-specific exceptions
        if hasattr(e, '__class__'):
            if e.__class__.__name__ == 'NotFound':
                error_msg = f"Document not found: {gcs_url}"
                logger.error(error_msg)
                raise DocumentProcessingError(error_msg)
            elif e.__class__.__name__ == 'Forbidden':
                error_msg = f"Access denied to: {gcs_url}"
                logger.error(error_msg)
                raise DocumentProcessingError(error_msg)
        
        error_ctx = create_error_context(e, f"load_gcs:{gcs_url}")
        logger.error(f"Failed to load document: {error_ctx}")
        raise DocumentProcessingError(f"Failed to load {gcs_url}: {e}")


def load_documents_from_gcs_urls(
    urls: list[str],
    project_id: str
) -> Dict[str, str]:
    """
    Load multiple documents from GCS URLs with cumulative size limits.
    
    Args:
        urls: List of GCS URLs to load
        project_id: GCP project ID for storage client
        
    Returns:
        Dictionary of {document_key: content}
    """
    from .artifact_utils import UPLOADED_STRATEGY_PREFIX
    from google.cloud import storage
    
    storage_client = storage.Client(project=project_id)
    loaded_docs = {}
    total_size = 0
    failed_count = 0
    
    for url in urls:
        try:
            filename, content = load_document_from_gcs(url, storage_client)
            
            # Check cumulative size
            doc_size = len(content.encode('utf-8'))
            if total_size + doc_size > MAX_TOTAL_SIZE:
                logger.warning(
                    f"Skipping {filename}: would exceed total size limit "
                    f"({total_size + doc_size:,} > {MAX_TOTAL_SIZE:,})"
                )
                continue
                
            doc_key = f"{UPLOADED_STRATEGY_PREFIX}{filename}"
            loaded_docs[doc_key] = content
            total_size += doc_size
            
            logger.info(
                f"Loaded {filename}: {len(content)} chars, "
                f"cumulative size: {total_size:,} bytes"
            )
            
        except DocumentSizeError as e:
            logger.warning(f"Skipping oversized document: {e}")
            failed_count += 1
            continue
        except DocumentProcessingError as e:
            logger.error(f"Failed to process document: {e}")
            failed_count += 1
            continue
        except Exception as e:
            logger.error(f"Unexpected error loading {url}: {e}")
            failed_count += 1
            continue
    
    logger.info(
        f"Document loading complete: {len(loaded_docs)} loaded, "
        f"{failed_count} failed, total size: {total_size:,} bytes"
    )
    
    return loaded_docs


def create_document_loading_summary(
    loaded_docs: Dict[str, str],
    requested_urls: list[str]
) -> str:
    """
    Create a summary message about document loading results.
    
    Args:
        loaded_docs: Dictionary of successfully loaded documents
        requested_urls: Original list of requested URLs
        
    Returns:
        Human-readable summary message
    """
    if not requested_urls:
        return ""
    
    loaded_count = len(loaded_docs)
    requested_count = len(requested_urls)
    
    if loaded_count == requested_count:
        return f"Successfully loaded all {loaded_count} document(s)"
    elif loaded_count > 0:
        return (
            f"Loaded {loaded_count} of {requested_count} document(s). "
            f"Some documents could not be processed."
        )
    else:
        return (
            f"Unable to load any of the {requested_count} requested document(s). "
            f"Proceeding with web research only."
        )