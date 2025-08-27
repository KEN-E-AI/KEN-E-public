"""
Usage and cost tracking API endpoints with admin-only access.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query
from google.cloud import firestore
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from ..auth.models import UserContext

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])

# Initialize Firestore client
db = firestore.Client()


class UsageRecord(BaseModel):
    """Individual usage record."""
    timestamp: datetime = Field(..., description="When the usage occurred")
    agent: str = Field(..., description="Agent that generated the usage")
    operation: str = Field(..., description="Operation performed")
    model: str = Field(..., description="Model used")
    prompt_tokens: int = Field(..., description="Number of prompt tokens")
    response_tokens: int = Field(..., description="Number of response tokens")
    total_tokens: int = Field(..., description="Total tokens used")
    prompt_cost: float = Field(..., description="Cost for prompt tokens")
    response_cost: float = Field(..., description="Cost for response tokens")
    total_cost: float = Field(..., description="Total cost")
    user_id: str = Field(..., description="User who triggered the usage")
    account_id: str = Field(..., description="Account associated with usage")


class UsageSummary(BaseModel):
    """Usage summary for a period."""
    period_start: datetime = Field(..., description="Start of period")
    period_end: datetime = Field(..., description="End of period")
    total_tokens: int = Field(..., description="Total tokens in period")
    total_cost: float = Field(..., description="Total cost in period")
    by_agent: Dict[str, Dict[str, Any]] = Field(..., description="Breakdown by agent")
    by_model: Dict[str, Dict[str, Any]] = Field(..., description="Breakdown by model")
    by_operation: Dict[str, Dict[str, Any]] = Field(..., description="Breakdown by operation")
    record_count: int = Field(..., description="Number of records in period")


class UserCostResponse(BaseModel):
    """Response for user cost query."""
    user_id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    summary: UsageSummary = Field(..., description="Usage summary")
    recent_records: List[UsageRecord] = Field(..., description="Recent usage records")


class AccountCostResponse(BaseModel):
    """Response for account cost query."""
    account_id: str = Field(..., description="Account ID")
    summary: UsageSummary = Field(..., description="Usage summary")
    by_user: Dict[str, Dict[str, Any]] = Field(..., description="Breakdown by user")
    recent_records: List[UsageRecord] = Field(..., description="Recent usage records")


async def check_cost_access(
    user: UserContext,
    account_id: Optional[str] = None,
    target_user_id: Optional[str] = None
) -> bool:
    """
    Check if user has access to view cost data.
    
    Rules:
    - Super admins can view all costs
    - Account admins can view costs for their accounts
    - Users can view their own costs
    """
    # Super admins have full access
    if user.is_super_admin:
        return True
    
    # Users can view their own costs
    if target_user_id and target_user_id == user.user_id:
        return True
    
    # Account admins can view account costs
    if account_id and user.has_account_access(account_id, ["edit"]):
        return True
    
    return False


@router.get("/user/{user_id}/costs", response_model=UserCostResponse)
async def get_user_costs(
    user_id: str,
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(10, description="Number of recent records to return"),
    user: UserContext = Depends(get_current_user)
) -> UserCostResponse:
    """
    Get usage costs for a specific user.
    Users can view their own costs, admins can view any user's costs.
    """
    # Check access
    if not await check_cost_access(user, target_user_id=user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view user costs"
        )
    
    try:
        # Set date range
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Query usage records
        usage_ref = db.collection("usage_records")
        query = usage_ref.where("user_id", "==", user_id)
        query = query.where("timestamp", ">=", date_from)
        query = query.where("timestamp", "<=", date_to)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        # Get all records for summary
        all_records = []
        for doc in query.stream():
            record_data = doc.to_dict()
            all_records.append(UsageRecord(**record_data))
        
        # Calculate summary
        summary = calculate_usage_summary(all_records, date_from, date_to)
        
        # Get recent records
        recent_records = all_records[:limit]
        
        # Get user email
        user_email = user.email if user.user_id == user_id else f"user_{user_id}"
        
        return UserCostResponse(
            user_id=user_id,
            email=user_email,
            summary=summary,
            recent_records=recent_records
        )
        
    except Exception as e:
        logger.error(f"Error retrieving user costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user costs"
        )


@router.get("/account/{account_id}/costs", response_model=AccountCostResponse)
async def get_account_costs(
    account_id: str,
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    limit: int = Query(10, description="Number of recent records to return"),
    user: UserContext = Depends(get_current_user)
) -> AccountCostResponse:
    """
    Get usage costs for an account.
    Requires admin access to the account.
    """
    # Check access
    if not await check_cost_access(user, account_id=account_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to view account costs"
        )
    
    try:
        # Set date range
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Query usage records
        usage_ref = db.collection("usage_records")
        query = usage_ref.where("account_id", "==", account_id)
        query = query.where("timestamp", ">=", date_from)
        query = query.where("timestamp", "<=", date_to)
        query = query.order_by("timestamp", direction=firestore.Query.DESCENDING)
        
        # Get all records
        all_records = []
        for doc in query.stream():
            record_data = doc.to_dict()
            all_records.append(UsageRecord(**record_data))
        
        # Calculate summary
        summary = calculate_usage_summary(all_records, date_from, date_to)
        
        # Calculate by-user breakdown
        by_user = {}
        for record in all_records:
            user_id = record.user_id
            if user_id not in by_user:
                by_user[user_id] = {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "record_count": 0
                }
            by_user[user_id]["total_tokens"] += record.total_tokens
            by_user[user_id]["total_cost"] += record.total_cost
            by_user[user_id]["record_count"] += 1
        
        # Get recent records
        recent_records = all_records[:limit]
        
        return AccountCostResponse(
            account_id=account_id,
            summary=summary,
            by_user=by_user,
            recent_records=recent_records
        )
        
    except Exception as e:
        logger.error(f"Error retrieving account costs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve account costs"
        )


@router.post("/record")
async def record_usage(
    usage_record: UsageRecord,
    user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Record usage data (internal endpoint).
    Only accessible by service accounts.
    """
    # This endpoint should only be called by internal services
    # In production, verify this is a service account
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only service accounts can record usage"
        )
    
    try:
        # Save to Firestore
        doc_id = f"{usage_record.user_id}_{usage_record.timestamp.isoformat()}_{uuid4().hex[:8]}"
        doc_ref = db.document(f"usage_records/{doc_id}")
        doc_ref.set(usage_record.dict())
        
        logger.info(
            f"Usage recorded: {usage_record.agent} by {usage_record.user_id} "
            f"for {usage_record.total_tokens} tokens (${usage_record.total_cost:.4f})"
        )
        
        return {"success": True, "record_id": doc_id}
        
    except Exception as e:
        logger.error(f"Error recording usage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record usage"
        )


@router.get("/summary")
async def get_usage_summary(
    date_from: Optional[datetime] = Query(None, description="Start date"),
    date_to: Optional[datetime] = Query(None, description="End date"),
    user: UserContext = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get overall usage summary.
    Only accessible by super admins.
    """
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view overall usage"
        )
    
    try:
        # Set date range
        if not date_from:
            date_from = datetime.utcnow() - timedelta(days=30)
        if not date_to:
            date_to = datetime.utcnow()
        
        # Query all usage records
        usage_ref = db.collection("usage_records")
        query = usage_ref.where("timestamp", ">=", date_from)
        query = query.where("timestamp", "<=", date_to)
        
        # Calculate totals
        total_tokens = 0
        total_cost = 0.0
        record_count = 0
        by_account = {}
        
        for doc in query.stream():
            record = doc.to_dict()
            total_tokens += record.get("total_tokens", 0)
            total_cost += record.get("total_cost", 0.0)
            record_count += 1
            
            # Aggregate by account
            account_id = record.get("account_id", "unknown")
            if account_id not in by_account:
                by_account[account_id] = {
                    "total_tokens": 0,
                    "total_cost": 0.0,
                    "record_count": 0
                }
            by_account[account_id]["total_tokens"] += record.get("total_tokens", 0)
            by_account[account_id]["total_cost"] += record.get("total_cost", 0.0)
            by_account[account_id]["record_count"] += 1
        
        return {
            "period_start": date_from.isoformat(),
            "period_end": date_to.isoformat(),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "record_count": record_count,
            "by_account": by_account,
            "average_cost_per_record": total_cost / record_count if record_count > 0 else 0
        }
        
    except Exception as e:
        logger.error(f"Error retrieving usage summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve usage summary"
        )


def calculate_usage_summary(
    records: List[UsageRecord],
    date_from: datetime,
    date_to: datetime
) -> UsageSummary:
    """Calculate usage summary from records."""
    total_tokens = 0
    total_cost = 0.0
    by_agent = {}
    by_model = {}
    by_operation = {}
    
    for record in records:
        total_tokens += record.total_tokens
        total_cost += record.total_cost
        
        # By agent
        if record.agent not in by_agent:
            by_agent[record.agent] = {"tokens": 0, "cost": 0.0, "count": 0}
        by_agent[record.agent]["tokens"] += record.total_tokens
        by_agent[record.agent]["cost"] += record.total_cost
        by_agent[record.agent]["count"] += 1
        
        # By model
        if record.model not in by_model:
            by_model[record.model] = {"tokens": 0, "cost": 0.0, "count": 0}
        by_model[record.model]["tokens"] += record.total_tokens
        by_model[record.model]["cost"] += record.total_cost
        by_model[record.model]["count"] += 1
        
        # By operation
        if record.operation not in by_operation:
            by_operation[record.operation] = {"tokens": 0, "cost": 0.0, "count": 0}
        by_operation[record.operation]["tokens"] += record.total_tokens
        by_operation[record.operation]["cost"] += record.total_cost
        by_operation[record.operation]["count"] += 1
    
    return UsageSummary(
        period_start=date_from,
        period_end=date_to,
        total_tokens=total_tokens,
        total_cost=total_cost,
        by_agent=by_agent,
        by_model=by_model,
        by_operation=by_operation,
        record_count=len(records)
    )


from uuid import uuid4  # Add this import at the top