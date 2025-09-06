"""Pydantic models for analytics data structures.

This module provides type-safe data models for the analytics system,
ensuring data validation and consistency across the analytics pipeline.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ExecutionMetrics(BaseModel):
    """Model for tracking agent execution metrics."""
    
    execution_id: str
    agent_name: str
    account_id: str
    timestamp: datetime
    model: str
    prompt_tokens: int
    response_tokens: int
    total_tokens: int
    prompt_cost: float
    response_cost: float
    total_cost: float
    execution_time_seconds: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DailyCostAggregation(BaseModel):
    """Model for daily cost aggregation data."""
    
    date: str
    account_id: str
    total_cost: float
    total_tokens: int
    total_executions: int
    cost_by_agent: Dict[str, float]
    cost_by_model: Dict[str, float]
    tokens_by_model: Dict[str, int]


class PerformanceProfile(BaseModel):
    """Model for performance profiling data."""
    
    execution_id: str
    account_id: str
    timestamp: datetime
    agent_name: str
    operation: str
    duration_seconds: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_bottleneck: bool
    severity: str


class AlertData(BaseModel):
    """Model for alert notification data."""
    
    alert_id: str
    account_id: str
    timestamp: str
    severity: str
    percentage: float
    current_tokens: int
    max_tokens: int
    message: str
    context: Optional[str] = None
    agent_name: Optional[str] = None
    circuit_breaker_open: bool = False


class OptimizationRecommendationModel(BaseModel):
    """Model for optimization recommendations."""
    
    recommendation_type: str
    description: str
    estimated_savings_percentage: float
    implementation_difficulty: str  # easy, medium, hard
    priority: int  # 1-5, higher is more important
    details: Dict[str, Any]
    created_at: datetime


class UsagePattern(BaseModel):
    """Model for analyzed usage patterns."""
    
    period_days: int
    total_executions: int
    total_tokens: int
    total_cost: float
    agent_patterns: Dict[str, Dict[str, Any]]
    model_usage: Dict[str, Dict[str, Any]]
    error_patterns: Dict[str, int]
    peak_usage_times: List[Dict[str, Any]]
    context_utilization: List[float]


class TokenEstimation(BaseModel):
    """Model for token estimation tracking."""
    
    execution_id: str
    agent_name: str
    account_id: str
    timestamp: datetime
    estimated_tokens: int
    actual_tokens: int
    accuracy_error: float
    context: str
    metadata: Dict[str, Any] = Field(default_factory=dict)