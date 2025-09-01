"""
Unit tests for account_creation_service.py
Following T-1 through T-8: Testing extracted service functions
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from fastapi import UploadFile

from account_creation_service import (
    upload_strategy_documents,
    prepare_strategy_generation_params
)


class TestUploadStrategyDocuments:
    """Test the async upload_strategy_documents function"""
    
    @pytest.mark.asyncio
    async def test_successful_upload_all_files(self):
        # Mock files
        file1 = Mock(spec=UploadFile)
        file1.filename = "strategy1.pdf"
        file2 = Mock(spec=UploadFile)
        file2.filename = "strategy2.docx"
        
        # Mock storage service
        mock_storage = Mock()
        mock_storage.upload_business_documents = AsyncMock(return_value=[
            {"filename": "strategy1.pdf", "gcs_url": "gs://bucket/acc_123/strategy1.pdf"},
            {"filename": "strategy2.docx", "gcs_url": "gs://bucket/acc_123/strategy2.docx"}
        ])
        
        # Call function
        urls = await upload_strategy_documents(
            files=[file1, file2],
            account_id="acc_123",
            data_region="US",
            storage_service=mock_storage
        )
        
        # Assertions
        assert len(urls) == 2
        assert "gs://bucket/acc_123/strategy1.pdf" in urls
        assert "gs://bucket/acc_123/strategy2.docx" in urls
        mock_storage.upload_business_documents.assert_called_once_with(
            "acc_123", "US", [file1, file2]
        )
    
    @pytest.mark.asyncio
    async def test_partial_upload_failure(self):
        # Mock files
        file1 = Mock(spec=UploadFile)
        file2 = Mock(spec=UploadFile)
        
        # Mock storage service with one success and one failure
        mock_storage = Mock()
        mock_storage.upload_business_documents = AsyncMock(return_value=[
            {"filename": "strategy1.pdf", "gcs_url": "gs://bucket/acc_123/strategy1.pdf"},
            {"filename": "strategy2.docx", "error": "Upload failed", "status": "failed"}
        ])
        
        # Call function
        urls = await upload_strategy_documents(
            files=[file1, file2],
            account_id="acc_123",
            data_region="EU",
            storage_service=mock_storage
        )
        
        # Should only return successful uploads
        assert len(urls) == 1
        assert urls[0] == "gs://bucket/acc_123/strategy1.pdf"
    
    @pytest.mark.asyncio
    async def test_no_files_provided(self):
        mock_storage = Mock()
        
        urls = await upload_strategy_documents(
            files=None,
            account_id="acc_123",
            data_region="US",
            storage_service=mock_storage
        )
        
        assert urls == []
        mock_storage.upload_business_documents.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_empty_files_list(self):
        mock_storage = Mock()
        
        urls = await upload_strategy_documents(
            files=[],
            account_id="acc_123",
            data_region="US",
            storage_service=mock_storage
        )
        
        assert urls == []
        mock_storage.upload_business_documents.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_storage_service_exception(self):
        file1 = Mock(spec=UploadFile)
        
        # Mock storage service that raises exception
        mock_storage = Mock()
        mock_storage.upload_business_documents = AsyncMock(
            side_effect=Exception("Storage service error")
        )
        
        # Should handle exception and return empty list
        urls = await upload_strategy_documents(
            files=[file1],
            account_id="acc_123",
            data_region="US",
            storage_service=mock_storage
        )
        
        assert urls == []


class TestPrepareStrategyGenerationParams:
    """Test the pure function prepare_strategy_generation_params"""
    
    def test_all_parameters_provided(self):
        params = prepare_strategy_generation_params(
            account_id="acc_123",
            account_name="Test Corp",
            websites=["https://test.com", "https://example.com"],
            industry="Technology",
            region=["US", "EU", "APAC"],
            user_id="user_456",
            estimated_annual_ad_budget=100000,
            uploaded_document_urls=["gs://bucket/doc1.pdf", "gs://bucket/doc2.pdf"]
        )
        
        # Test the entire structure in one assertion (T-8)
        assert params == {
            "account_id": "acc_123",
            "company_name": "Test Corp",
            "websites": ["https://test.com", "https://example.com"],
            "industry": "Technology",
            "customer_regions": ["US", "EU", "APAC"],
            "user_id": "user_456",
            "annual_ad_budget": 100000,
            "uploaded_document_urls": ["gs://bucket/doc1.pdf", "gs://bucket/doc2.pdf"],
            "user_context": None
        }
    
    def test_optional_parameters_none(self):
        params = prepare_strategy_generation_params(
            account_id="acc_123",
            account_name="Test Corp",
            websites=["https://test.com"],
            industry="Technology",
            region=None,
            user_id="user_456",
            estimated_annual_ad_budget=None,
            uploaded_document_urls=None
        )
        
        assert params["customer_regions"] == []
        assert params["annual_ad_budget"] is None
        assert params["uploaded_document_urls"] == []
        assert params["user_context"] is None
    
    def test_empty_lists_handled_correctly(self):
        params = prepare_strategy_generation_params(
            account_id="acc_123",
            account_name="Test Corp",
            websites=[],
            industry="Technology",
            region=[],
            user_id="user_456",
            estimated_annual_ad_budget=0,
            uploaded_document_urls=[]
        )
        
        assert params["websites"] == []
        assert params["customer_regions"] == []
        assert params["annual_ad_budget"] == 0
        assert params["uploaded_document_urls"] == []