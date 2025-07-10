"""Kene API data models based on Excel specifications."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field

# Constants for repeated string literals
ACCOUNT_ID_DESCRIPTION = "The unique identifier for the account"
MISSING_REQUIRED_IDS_ERROR = "Both activity_id and metric_id are required"
CREATION_TIMESTAMP_DESCRIPTION = "Creation timestamp"
ACTIVITY_ID_DESCRIPTION = "Activity ID"
METRIC_ID_DESCRIPTION = "Metric ID"
CONFIDENCE_SCORE_DESCRIPTION = "Confidence score"
PRIORITY_LEVEL_DESCRIPTION = "Priority level"
ACTIVITY_ID_EDIT_DELETE_DESCRIPTION = "Activity ID (required for edit/delete)"
ACTIVITY_ID_CREATE_DESCRIPTION = "Activity ID (required for create)"
ACTIVITY_ID_FILTER_DESCRIPTION = "Activity ID to filter by"
METRIC_ID_EDIT_DELETE_DESCRIPTION = "Metric ID (required for edit/delete)"
METRIC_ID_FILTER_DESCRIPTION = "Metric ID to filter by"
ACTIVITY_LOG_ID_DESCRIPTION = (
    "A unique identifier for the ActivityLog node created by the application"
)
ACTIVITY_DESCRIPTION_DESCRIPTION = "A description of the activity"
DIRECTION_DESCRIPTION = "Direction of influence (positive or negative)"
RELATED_DATASET_PRODUCTS_DESCRIPTION = (
    "The name of the martech products that were used to calculate the metric. "
    "In neo4j this value is stored on the Dataset node that has a CALCULATED_FROM relationship to the Metric node"
)
METRIC_VERBOSE_NAME_DESCRIPTION = "The friendly name of the metric. Should be identical to the value stored in Superset"
EVIDENCE_DESCRIPTION = (
    "The results from the Analysis Workflow that indicate that the Activity did or did not influence the Metric. "
    "Stored as a property of the INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED relationship"
)


class RelationshipType(str, Enum):
    """Enum for relationship types."""

    BELONGS_TO = "BELONGS_TO"
    INFLUENCE_LIKELY = "INFLUENCE_LIKELY"
    INFLUENCE_CONFIRMED = "INFLUENCE_CONFIRMED"
    NO_INFLUENCE_CONFIRMED = "NO_INFLUENCE_CONFIRMED"
    LOGGED = "LOGGED"


class DirectionType(str, Enum):
    """Enum for direction types indicating influence direction."""

    POSITIVE = "positive"
    NEGATIVE = "negative"


class ActiveConfidenceLevel(str, Enum):
    """Enum for active confidence levels."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# Base Models
class BaseEntity(BaseModel):
    """Base entity with common fields."""

    id: Optional[str] = Field(None, description="Unique identifier")
    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)


class BaseRequest(BaseModel):
    """Base request model."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)


class BaseCRUDRequest(BaseRequest):
    """Base CRUD request with common fields."""

    name: Optional[str] = Field(None, description="Name of the entity")
    description: Optional[str] = Field(None, description="Description of the entity")


# Metric Models
class Metric(BaseEntity):
    """Metric entity model."""

    d3_format: str = Field(
        ...,
        description="The d3 formatting guidelines that define how the metric should be presented",
    )
    verbose_name: str = Field(
        ...,
        description="The unique identifier for the metric in this account, created by the application",
    )
    expression: str = Field(
        ...,
        description="The SQL expression used to calculate this metric. Should be identical to the value stored in Superset",
    )
    metric_name: str = Field(
        ...,
        description="The snake_case representation of the metric name. Should be identical to the value stored in Superset",
    )
    currency: str = Field(
        ...,
        description="The currency code for the metric (e.g., USD, EUR, GBP). Used for formatting monetary values",
    )
    account_components: List[str] = Field(
        ...,
        description="A list of components that the metric can be used to assist with in an analysis. An account must include at least one component from the list for the metric to be relevant",
    )
    related_dataset_id: int = Field(
        ...,
        description="A unique identifier for the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node. This is created by Superset, where it is known as the 'dataset_id'",
    )
    related_dataset_name: str = Field(
        ...,
        description="The name of the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node",
    )
    related_dataset_products: List[str] = Field(
        ...,
        description="The name of the martech products that were used to calculate the metric. In neo4j this value is stored on the Dataset node that has a CALCULATED_FROM relationship to the Metric node",
    )
    description: str = Field(
        ...,
        description="A friendly description of the metric and how it is used. Should be identical to the value stored in Superset",
    )
    below_zero: bool = Field(
        ...,
        description="Indicates whether the metric can return a result below 0",
    )
    is_kpi: bool = Field(
        ...,
        description="Indicates whether the metric has been flagged as a Key Performance Indicator",
    )


class MetricRequest(BaseRequest):
    """Request model for metric operations."""

    id: Optional[str] = Field(None, description=METRIC_ID_EDIT_DELETE_DESCRIPTION)
    d3_format: Optional[str] = Field(
        None,
        description="The d3 formatting guidelines that define how the metric should be presented",
    )
    verbose_name: Optional[str] = Field(
        None,
        description="The unique identifier for the metric in this account, created by the application",
    )
    expression: Optional[str] = Field(
        None,
        description="The SQL expression used to calculate this metric. Should be identical to the value stored in Superset",
    )
    metric_name: Optional[str] = Field(
        None,
        description="The snake_case representation of the metric name. Should be identical to the value stored in Superset",
    )
    currency: Optional[str] = Field(
        None,
        description="The currency code for the metric (e.g., USD, EUR, GBP). Used for formatting monetary values",
    )
    account_components: Optional[List[str]] = Field(
        None,
        description="A list of components that the metric can be used to assist with in an analysis. An account must include at least one component from the list for the metric to be relevant",
    )
    related_dataset_id: Optional[int] = Field(
        None,
        description="A unique identifier for the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node. This is created by Superset, where it is known as the 'dataset_id'",
    )
    related_dataset_name: Optional[str] = Field(
        None,
        description="The name of the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node",
    )
    related_dataset_products: Optional[List[str]] = Field(
        None,
        description="The name of the martech products that were used to calculate the metric. In neo4j this value is stored on the Dataset node that has a CALCULATED_FROM relationship to the Metric node",
    )
    description: Optional[str] = Field(
        None,
        description="A friendly description of the metric and how it is used. Should be identical to the value stored in Superset",
    )
    below_zero: Optional[bool] = Field(
        None,
        description="Indicates whether the metric can return a result below 0",
    )
    is_kpi: Optional[bool] = Field(
        None,
        description="Indicates whether the metric has been flagged as a Key Performance Indicator",
    )


class MetricListResponse(BaseModel):
    """Response model for metric list."""

    metrics: List[Metric] = Field(..., description="List of metrics")
    total: int = Field(..., description="Total number of metrics")


# Evidence Models
class SupersetMetricValue(BaseModel):
    """Superset metric value object with comparison and evaluation data."""

    comparison_metric_value: float = Field(
        ..., description="Value of the metric during the comparison date range"
    )
    evaluation_metric_value: float = Field(
        ..., description="Value of the metric during the evaluation date range"
    )
    metric_details: "Metric" = Field(..., description="Metric details")


class ActiveEvidence(BaseModel):
    """Active evidence object with confidence level and data."""

    active_confidence: ActiveConfidenceLevel = Field(
        ..., description="Confidence level for the active evidence"
    )
    evidence: Union[List[str], Literal["data"]] = Field(
        ..., description="Either a list of strings or fixed value 'data'"
    )
    data: Optional[SupersetMetricValue] = Field(
        None,
        description="Provides the metric value on the comparison date and evaluation date, along with the metric information",
    )


class InfluenceEvidence(BaseModel):
    """Influence evidence object with direction alignment and insight analysis."""

    influence_direction_aligned: bool = Field(
        ..., description="Whether the metric moved in the expected direction"
    )
    influence_likely: bool = Field(
        ..., description="Whether there is an influence_likely connection already"
    )
    other_conflicting_insights: List["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances that conflict with this insight",
    )
    other_supporting_insights: List["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances that support this insight",
    )
    overlapping_conflicting_insights: List["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances with overlapping time periods that conflict",
    )
    overlapping_supporting_insights: List["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances with overlapping time periods that support",
    )


class Evidence(BaseModel):
    """Evidence object for activity logs - flexible structure to accommodate any evidence format."""

    model_config = {"extra": "allow"}

    def __init__(self, **data):
        """Initialize Evidence with any structure."""
        super().__init__(**data)


# Activity Models
class ActivityLog(BaseEntity):
    """Activity log entity model."""

    start_date: str = Field(
        ...,
        description="The date when the activity was first known to be active in format 'YYYY-MM-DD'",
    )
    end_date: str = Field(
        ...,
        description="The date when the activity was last known to be active in format 'YYYY-MM-DD'",
    )
    description: Optional[str] = Field(
        None, description="A description of the specific instance of the activity"
    )
    evidence: Optional[Evidence] = Field(
        None,
        description="The results from the Activity Scan that indicate that the Activity was active during the time period",
    )


class Activity(BaseEntity):
    """Activity entity model."""

    activity_description: str = Field(..., description=ACTIVITY_DESCRIPTION_DESCRIPTION)
    expected_impact: str = Field(
        ...,
        description="A description of the impact that this activity is likely to have on the business",
    )
    internal: bool = Field(
        ...,
        description="Set to TRUE when the company can choose to activate this activity to influence metrics",
    )
    known_activity: bool = Field(
        ...,
        description="Set to TRUE when every occurrence of this activity will exist as an ActivityLog node",
    )
    logs: Optional[List[ActivityLog]] = Field(
        default_factory=list,
        description="A list of ActivityLog nodes with a LOGGED relationship to the Activity node",
    )


class ActivityRequest(BaseRequest):
    """Request model for activity operations."""

    activity_id: Optional[str] = Field(None, description=ACTIVITY_ID_EDIT_DELETE_DESCRIPTION)
    activity_description: Optional[str] = Field(
        None, description=ACTIVITY_DESCRIPTION_DESCRIPTION
    )
    expected_impact: Optional[str] = Field(
        None,
        description="A description of the impact that this activity is likely to have on the business",
    )
    internal: Optional[bool] = Field(
        None,
        description="Set to TRUE when the company can choose to activate this activity to influence metrics",
    )
    known_activity: Optional[bool] = Field(
        None,
        description="Set to TRUE when every occurrence of this activity will exist as an ActivityLog node",
    )


class ActivityLogRequest(BaseRequest):
    """Request model for activity log operations."""

    activity_id: Optional[str] = Field(
        None, description="Activity ID (required for associating logs)"
    )
    activity_log_id: Optional[str] = Field(
        None, description="Activity log ID (required for edit/delete)"
    )
    start_date: Optional[str] = Field(
        None,
        description="The date when the activity was first known to be active in format 'YYYY-MM-DD'",
    )
    end_date: Optional[str] = Field(
        None,
        description="The date when the activity was last known to be active in format 'YYYY-MM-DD'",
    )
    description: Optional[str] = Field(
        None, description="A description of the specific instance of the activity"
    )


class ActivityListResponse(BaseModel):
    """Response model for activity list."""

    activities: List[Activity] = Field(..., description="List of activities")
    total: int = Field(..., description="Total number of activities")


# Insight Models
class Insight(BaseModel):
    """Insight relationship model."""

    activity_id: str = Field(..., description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_DESCRIPTION)
    activity_log_id: str = Field(..., description=ACTIVITY_LOG_ID_DESCRIPTION)
    relationship_type: RelationshipType = Field(
        ..., description="Type of relationship (INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED)"
    )
    direction: Optional[DirectionType] = Field(
        None, description="Direction of influence (positive or negative)"
    )
    metric_verbose_name: str = Field(
        ...,
        description=METRIC_VERBOSE_NAME_DESCRIPTION,
    )
    related_dataset_products: List[str] = Field(
        ...,
        description=RELATED_DATASET_PRODUCTS_DESCRIPTION,
    )
    evidence: Optional[Evidence] = Field(
        None,
        description=EVIDENCE_DESCRIPTION,
    )
    activity_description: str = Field(..., description=ACTIVITY_DESCRIPTION_DESCRIPTION)


class Intuition(BaseModel):
    """Intuition model for insights."""

    activity_id: str = Field(..., description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_DESCRIPTION)
    direction: DirectionType = Field(
        ..., description=DIRECTION_DESCRIPTION
    )


class InsightRequest(BaseRequest):
    """Request model for insight operations."""

    activity_id: Optional[str] = Field(None, description=ACTIVITY_ID_DESCRIPTION)
    metric_id: Optional[str] = Field(None, description=METRIC_ID_DESCRIPTION)
    activity_log_id: Optional[str] = Field(
        None, description=ACTIVITY_LOG_ID_DESCRIPTION
    )
    relationship_type: Optional[RelationshipType] = Field(
        RelationshipType.INFLUENCE_CONFIRMED,
        description="The type of relationship between activity log and metric"
    )
    direction: Optional[DirectionType] = Field(
        None, description=DIRECTION_DESCRIPTION
    )
    metric_verbose_name: Optional[str] = Field(
        None,
        description=METRIC_VERBOSE_NAME_DESCRIPTION,
    )
    related_dataset_products: Optional[List[str]] = Field(
        None,
        description=RELATED_DATASET_PRODUCTS_DESCRIPTION,
    )
    evidence: Optional[Evidence] = Field(
        None,
        description=EVIDENCE_DESCRIPTION,
    )
    activity_description: Optional[str] = Field(
        None, description=ACTIVITY_DESCRIPTION_DESCRIPTION
    )


class IntuitionRequest(BaseRequest):
    """Request model for intuition operations."""

    activity_id: Optional[str] = Field(None, description=ACTIVITY_ID_DESCRIPTION)
    metric_id: Optional[str] = Field(None, description=METRIC_ID_DESCRIPTION)
    direction: Optional[DirectionType] = Field(
        None, description=DIRECTION_DESCRIPTION
    )


class InsightSearchRequest(BaseModel):
    """Request model for searching insights."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_FILTER_DESCRIPTION)
    activity_id: str = Field(..., description=ACTIVITY_ID_FILTER_DESCRIPTION)
    evaluation_date_start: str = Field(..., description="Start date for evaluation period (YYYY-MM-DD)")
    evaluation_date_end: str = Field(..., description="End date for evaluation period (YYYY-MM-DD)")
    comparison_date_start: str = Field(..., description="Start date for comparison period (YYYY-MM-DD)")
    comparison_date_end: str = Field(..., description="End date for comparison period (YYYY-MM-DD)")
    direction: DirectionType = Field(..., description=DIRECTION_DESCRIPTION)


class InsightSearchResponse(BaseModel):
    """Response model for insight search."""

    insights: List[Insight] = Field(..., description="List of insights")
    total: int = Field(..., description="Total number of insights")


class InsightListResponse(BaseModel):
    """Response model for insight list."""

    insights: List[Insight] = Field(..., description="List of insights")
    intuitions: List[Intuition] = Field(..., description="List of intuitions")
    total: int = Field(..., description="Total number of items")


class IntuitionListResponse(BaseModel):
    """Response model for intuition list."""

    intuitions: List[Intuition] = Field(..., description="List of intuitions")
    total: int = Field(..., description="Total number of intuitions")


# Home/Notification Models
class Notification(BaseEntity):
    """Notification entity model."""

    title: str = Field(..., description="Notification title")
    message: str = Field(..., description="Notification message")
    notification_type: str = Field(..., description="Type of notification")
    priority: Optional[str] = Field(None, description=PRIORITY_LEVEL_DESCRIPTION)
    read_status: bool = Field(False, description="Read status")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class NotificationRequest(BaseRequest):
    """Request model for notification operations."""

    title: Optional[str] = Field(None, description="Notification title")
    message: Optional[str] = Field(None, description="Notification message")
    notification_type: Optional[str] = Field(None, description="Type of notification")
    priority: Optional[str] = Field(None, description=PRIORITY_LEVEL_DESCRIPTION)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ActivityScanRequest(BaseModel):
    """Request model for activity scanning."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    scan_depth: Optional[int] = Field(
        10, description="Number of recent activities to scan"
    )
    include_logs: bool = Field(True, description="Include activity logs in scan")


class ActivityScanResponse(BaseModel):
    """Response model for activity scanning."""

    scanned_activities: int = Field(..., description="Number of activities scanned")
    notifications_created: int = Field(
        ..., description="Number of notifications created"
    )
    insights_found: int = Field(..., description="Number of insights discovered")
    scan_duration: float = Field(..., description="Scan duration in seconds")


# Funnel Reports Models
class AnalysisWorkflowRequest(BaseModel):
    """Request model for analysis workflow."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    workflow_type: str = Field(..., description="Type of analysis workflow")
    parameters: Dict[str, Any] = Field(..., description="Analysis parameters")
    save_results: bool = Field(True, description="Whether to save results")


class AnalysisResult(BaseModel):
    """Analysis result model."""

    result_id: str = Field(..., description="Unique result identifier")
    workflow_type: str = Field(..., description="Type of analysis workflow")
    results: Dict[str, Any] = Field(..., description="Analysis results")
    metadata: Dict[str, Any] = Field(..., description="Result metadata")


class Recommendation(BaseModel):
    """Recommendation model."""

    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Recommendation description")
    priority: str = Field(..., description=PRIORITY_LEVEL_DESCRIPTION)
    category: str = Field(..., description="Recommendation category")
    confidence_score: float = Field(..., description=CONFIDENCE_SCORE_DESCRIPTION)
    impact_score: Optional[float] = Field(None, description="Expected impact score")
    related_metrics: List[str] = Field(
        default_factory=list, description="Related metric IDs"
    )
    related_activities: List[str] = Field(
        default_factory=list, description="Related activity IDs"
    )


class AnalysisWorkflowResponse(BaseModel):
    """Response model for analysis workflow."""

    workflow_id: str = Field(..., description="Workflow execution ID")
    status: str = Field(..., description="Execution status")
    results: List[AnalysisResult] = Field(..., description="Analysis results")
    recommendations: List[Recommendation] = Field(
        ..., description="Generated recommendations"
    )
    execution_time: float = Field(..., description="Execution time in seconds")


class AnalysisSearchRequest(BaseModel):
    """Request model for analysis search without activity_id."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_FILTER_DESCRIPTION)
    evaluation_date_start: str = Field(..., description="Start date for evaluation period (YYYY-MM-DD)")
    evaluation_date_end: str = Field(..., description="End date for evaluation period (YYYY-MM-DD)")
    comparison_date_start: str = Field(..., description="Start date for comparison period (YYYY-MM-DD)")
    comparison_date_end: str = Field(..., description="End date for comparison period (YYYY-MM-DD)")
    direction: DirectionType = Field(..., description=DIRECTION_DESCRIPTION)


# Response Models
class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    details: Optional[Dict[str, Any]] = None


# Superset Saved Queries Models
class SavedQueryRequest(BaseRequest):
    """Request model for creating/updating saved queries."""
    
    label: str = Field(..., description="Label/name of the saved query")
    description: Optional[str] = Field(None, description="Description of the saved query")
    database_id: int = Field(..., description="Database ID for the saved query")
    schema_name: str = Field(..., description="Schema name for the saved query")
    sql: str = Field(..., description="SQL query text")


class SavedQueryResponse(BaseModel):
    """Response model for saved query operations."""
    
    id: int = Field(..., description="Saved query ID")
    label: str = Field(..., description="Label/name of the saved query")
    description: Optional[str] = Field(None, description="Description of the saved query")
    database_id: int = Field(..., description="Database ID")
    schema_name: str = Field(..., description="Schema name")
    sql: str = Field(..., description="SQL query text")
    created_on: Optional[str] = Field(None, description="Creation timestamp")
    changed_on: Optional[str] = Field(None, description="Last modification timestamp")


class SavedQueryListResponse(BaseModel):
    """Response model for saved query list."""
    
    saved_queries: List[SavedQueryResponse] = Field(..., description="List of saved queries")
    total: int = Field(..., description="Total number of saved queries")


class QueryExecutionResponse(BaseModel):
    """Response model for query execution results."""
    
    query_id: Optional[int] = Field(None, description="Query execution ID")
    status: str = Field(..., description="Execution status")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Query result data")
    columns: Optional[List[Dict[str, Any]]] = Field(None, description="Column metadata")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    query: Optional[Dict[str, Any]] = Field(None, description="Query metadata object containing execution details")
