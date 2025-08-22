"""Kene API data models based on Excel specifications."""

from enum import Enum
from typing import Any, Literal

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

# Region to Holiday Activity ID mapping
REGION_TO_HOLIDAY_ACTIVITY_ID = {
    "AU": "act_00_au",
    "CA": "act_00_ca",
    "CH": "act_00_ch",
    "CL": "act_00_cl",
    "CZ": "act_00_cz",
    "DE": "act_00_de",
    "DK": "act_00_dk",
    "EMEA": "act_00_emea",
    "ES": "act_00_es",
    "FR": "act_00_fr",
    "GB": "act_00_gb",
    "GLOBAL": "act_00_global",
    "ID": "act_00_id",
    "IN": "act_00_in",
    "IT": "act_00_it",
    "JAPAC": "act_00_japac",
    "JP": "act_00_jp",
    "KR": "act_00_kr",
    "LAC": "act_00_lac",
    "MX": "act_00_mx",
    "MY": "act_00_my",
    "NA": "act_00_na",
    "NL": "act_00_nl",
    "NZ": "act_00_nz",
    "PT": "act_00_pt",
    "SK": "act_00_sk",
    "US": "act_00_us",
    "ZA": "act_00_za",
    "VN": "act_00_vn",
    "VE": "act_00_ve",
    "UA": "act_00_ua",
    "TW": "act_00_tw",
    "TR": "act_00_tr",
    "TH": "act_00_th",
    "SL": "act_00_sl",
    "SG": "act_00_sg",
    "SE": "act_00_se",
    "SA": "act_00_sa",
    "RU": "act_00_ru",
    "RS": "act_00_rs",
    "RO": "act_00_ro",
    "PL": "act_00_pl",
    "PK": "act_00_pk",
    "PH": "act_00_ph",
    "PE": "act_00_pe",
    "NO": "act_00_no",
    "NG": "act_00_ng",
    "MA": "act_00_ma",
    "LV": "act_00_lv",
    "IR": "act_00_ir",
    "IL": "act_00_il",
    "IE": "act_00_ie",
    "HU": "act_00_hu",
    "HK": "act_00_hk",
    "GR": "act_00_gr",
    "FI": "act_00_fi",
    "EG": "act_00_eg",
    "EE": "act_00_ee",
    "EC": "act_00_ec",
    "DZ": "act_00_dz",
    "CO": "act_00_co",
    "CN": "act_00_cn",
    "BR": "act_00_br",
    "BE": "act_00_be",
    "AT": "act_00_at",
    "AR": "act_00_ar",
    "AE": "act_00_ae",
}


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

    id: str | None = Field(None, description="Unique identifier")
    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)


class BaseRequest(BaseModel):
    """Base request model."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)


class BaseCRUDRequest(BaseRequest):
    """Base CRUD request with common fields."""

    name: str | None = Field(None, description="Name of the entity")
    description: str | None = Field(None, description="Description of the entity")


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
    account_components: list[str] = Field(
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
    related_dataset_products: list[str] = Field(
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

    metric_id: str | None = Field(None, description=METRIC_ID_EDIT_DELETE_DESCRIPTION)
    d3_format: str | None = Field(
        None,
        description="The d3 formatting guidelines that define how the metric should be presented",
    )
    verbose_name: str | None = Field(
        None,
        description="The unique identifier for the metric in this account, created by the application",
    )
    expression: str | None = Field(
        None,
        description="The SQL expression used to calculate this metric. Should be identical to the value stored in Superset",
    )
    metric_name: str | None = Field(
        None,
        description="The snake_case representation of the metric name. Should be identical to the value stored in Superset",
    )
    currency: str | None = Field(
        None,
        description="The currency code for the metric (e.g., USD, EUR, GBP). Used for formatting monetary values",
    )
    account_components: list[str] | None = Field(
        None,
        description="A list of components that the metric can be used to assist with in an analysis. An account must include at least one component from the list for the metric to be relevant",
    )
    related_dataset_id: int | None = Field(
        None,
        description="A unique identifier for the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node. This is created by Superset, where it is known as the 'dataset_id'",
    )
    related_dataset_name: str | None = Field(
        None,
        description="The name of the dataset that is used to calculate the metric. In neo4j the Dataset node will have a CALCULATED_FROM relationship to the Metric node",
    )
    related_dataset_products: list[str] | None = Field(
        None,
        description="The name of the martech products that were used to calculate the metric. In neo4j this value is stored on the Dataset node that has a CALCULATED_FROM relationship to the Metric node",
    )
    description: str | None = Field(
        None,
        description="A friendly description of the metric and how it is used. Should be identical to the value stored in Superset",
    )
    below_zero: bool | None = Field(
        None,
        description="Indicates whether the metric can return a result below 0",
    )
    is_kpi: bool | None = Field(
        None,
        description="Indicates whether the metric has been flagged as a Key Performance Indicator",
    )


class MetricListResponse(BaseModel):
    """Response model for metric list."""

    metrics: list[Metric] = Field(..., description="List of metrics")
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
    evidence: list[str] | Literal["data"] = Field(
        ..., description="Either a list of strings or fixed value 'data'"
    )
    data: SupersetMetricValue | None = Field(
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
    other_conflicting_insights: list["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances that conflict with this insight",
    )
    other_supporting_insights: list["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances that support this insight",
    )
    overlapping_conflicting_insights: list["ActivityLog"] = Field(
        default_factory=list,
        description="List of ActivityLog instances with overlapping time periods that conflict",
    )
    overlapping_supporting_insights: list["ActivityLog"] = Field(
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
    description: str | None = Field(
        None, description="A description of the specific instance of the activity"
    )
    evidence: Evidence | None = Field(
        None,
        description="The results from the Activity Scan that indicate that the Activity was active during the time period",
    )


class Activity(BaseEntity):
    """Activity entity model."""

    activity_name: str = Field(
        ...,
        description="The name of the activity",
    )
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
    logs: list[ActivityLog] | None = Field(
        default_factory=list,
        description="A list of ActivityLog nodes with a LOGGED relationship to the Activity node",
    )


class ActivityRequest(BaseRequest):
    """Request model for activity operations."""

    activity_id: str | None = Field(
        None, description=ACTIVITY_ID_EDIT_DELETE_DESCRIPTION
    )
    activity_name: str | None = Field(None, description="The name of the activity")
    activity_description: str | None = Field(
        None, description=ACTIVITY_DESCRIPTION_DESCRIPTION
    )
    expected_impact: str | None = Field(
        None,
        description="A description of the impact that this activity is likely to have on the business",
    )
    internal: bool | None = Field(
        None,
        description="Set to TRUE when the company can choose to activate this activity to influence metrics",
    )
    known_activity: bool | None = Field(
        None,
        description="Set to TRUE when every occurrence of this activity will exist as an ActivityLog node",
    )


class ActivityLogRequest(BaseRequest):
    """Request model for activity log operations."""

    activity_id: str | None = Field(
        None, description="Activity ID (required for associating logs)"
    )
    activity_log_id: str | None = Field(
        None, description="Activity log ID (required for edit/delete)"
    )
    start_date: str | None = Field(
        None,
        description="The date when the activity was first known to be active in format 'YYYY-MM-DD'",
    )
    end_date: str | None = Field(
        None,
        description="The date when the activity was last known to be active in format 'YYYY-MM-DD'",
    )
    description: str | None = Field(
        None, description="A description of the specific instance of the activity"
    )


class ActivityListResponse(BaseModel):
    """Response model for activity list."""

    activities: list[Activity] = Field(..., description="List of activities")
    total: int = Field(..., description="Total number of activities")


# Insight Models
class Insight(BaseModel):
    """Insight relationship model."""

    activity_id: str = Field(..., description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_DESCRIPTION)
    activity_log_id: str = Field(..., description=ACTIVITY_LOG_ID_DESCRIPTION)
    relationship_type: RelationshipType = Field(
        ...,
        description="Type of relationship (INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED)",
    )
    direction: DirectionType | None = Field(
        None, description="Direction of influence (positive or negative)"
    )
    metric_verbose_name: str = Field(
        ...,
        description=METRIC_VERBOSE_NAME_DESCRIPTION,
    )
    related_dataset_products: list[str] = Field(
        ...,
        description=RELATED_DATASET_PRODUCTS_DESCRIPTION,
    )
    evidence: Evidence | None = Field(
        None,
        description=EVIDENCE_DESCRIPTION,
    )
    activity_description: str = Field(..., description=ACTIVITY_DESCRIPTION_DESCRIPTION)


class Intuition(BaseModel):
    """Intuition model for insights."""

    activity_id: str = Field(..., description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_DESCRIPTION)
    direction: DirectionType = Field(..., description=DIRECTION_DESCRIPTION)


class InsightRequest(BaseRequest):
    """Request model for insight operations."""

    activity_id: str | None = Field(None, description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str | None = Field(None, description=METRIC_ID_DESCRIPTION)
    activity_log_id: str | None = Field(None, description=ACTIVITY_LOG_ID_DESCRIPTION)
    relationship_type: RelationshipType | None = Field(
        RelationshipType.INFLUENCE_CONFIRMED,
        description="The type of relationship between activity log and metric",
    )
    direction: DirectionType | None = Field(None, description=DIRECTION_DESCRIPTION)
    metric_verbose_name: str | None = Field(
        None,
        description=METRIC_VERBOSE_NAME_DESCRIPTION,
    )
    related_dataset_products: list[str] | None = Field(
        None,
        description=RELATED_DATASET_PRODUCTS_DESCRIPTION,
    )
    evidence: Evidence | None = Field(
        None,
        description=EVIDENCE_DESCRIPTION,
    )
    activity_description: str | None = Field(
        None, description=ACTIVITY_DESCRIPTION_DESCRIPTION
    )


class IntuitionRequest(BaseRequest):
    """Request model for intuition operations."""

    activity_id: str | None = Field(None, description=ACTIVITY_ID_DESCRIPTION)
    metric_id: str | None = Field(None, description=METRIC_ID_DESCRIPTION)
    direction: DirectionType | None = Field(None, description=DIRECTION_DESCRIPTION)


class InsightSearchRequest(BaseModel):
    """Request model for searching insights."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_FILTER_DESCRIPTION)
    activity_id: str = Field(..., description=ACTIVITY_ID_FILTER_DESCRIPTION)
    evaluation_date_start: str = Field(
        ..., description="Start date for evaluation period (YYYY-MM-DD)"
    )
    evaluation_date_end: str = Field(
        ..., description="End date for evaluation period (YYYY-MM-DD)"
    )
    comparison_date_start: str = Field(
        ..., description="Start date for comparison period (YYYY-MM-DD)"
    )
    comparison_date_end: str = Field(
        ..., description="End date for comparison period (YYYY-MM-DD)"
    )
    direction: DirectionType = Field(..., description=DIRECTION_DESCRIPTION)


class InsightSearchResponse(BaseModel):
    """Response model for insight search."""

    insights: list[Insight] = Field(..., description="List of insights")
    total: int = Field(..., description="Total number of insights")


class InsightListResponse(BaseModel):
    """Response model for insight list."""

    insights: list[Insight] = Field(..., description="List of insights")
    intuitions: list[Intuition] = Field(..., description="List of intuitions")
    total: int = Field(..., description="Total number of items")


class IntuitionListResponse(BaseModel):
    """Response model for intuition list."""

    intuitions: list[Intuition] = Field(..., description="List of intuitions")
    total: int = Field(..., description="Total number of intuitions")


# Home/Notification Models
class NotificationCategory(str, Enum):
    """Notification category enum."""

    DATA_QUALITY_ALERT = "Data Quality Alert"
    NEWS_PRESS = "News & Press"
    INDUSTRY_NEWS = "Industry News"
    COMPETITOR_ACTIVITIES = "Competitor Activities"
    SCHEDULED_REPORT_STATUS = "Scheduled Report Status"
    KPI_PERFORMANCE = "KPI Performance"
    NEW_FEATURES = "New Features"


class NotificationStatus(str, Enum):
    """Notification status enum."""

    EXCLUDED = "excluded"
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class NotificationChannel(str, Enum):
    """Notification channel enum."""

    UI = "ui"
    SLACK = "slack"
    EMAIL = "email"


class Notification(BaseEntity):
    """Notification entity model."""

    category: NotificationCategory = Field(..., description="Notification category")
    description: str = Field(..., description="Short description of the notification")
    data: dict[str, Any] | None = Field(None, description="Optional JSON data")
    created_at: str = Field(
        ..., description="ISO timestamp when notification was created"
    )
    archived_at: str | None = Field(
        None,
        description="ISO timestamp when notification will be auto-archived (30 days after creation)",
    )


class NotificationWithStatus(Notification):
    """Notification with user-specific status."""

    status: NotificationStatus = Field(
        ..., description="User-specific notification status"
    )
    read_at: str | None = Field(None, description="ISO timestamp when marked as read")
    user_archived_at: str | None = Field(
        None, description="ISO timestamp when archived by user"
    )


class CreateNotificationRequest(BaseRequest):
    """Request model for creating notifications."""

    category: NotificationCategory = Field(..., description="Notification category")
    description: str = Field(..., description="Short description of the notification")
    data: dict[str, Any] | None = Field(None, description="Optional JSON data")


class UpdateNotificationStatusRequest(BaseModel):
    """Request model for updating notification status."""

    status: NotificationStatus = Field(..., description="New notification status")


class UserNotificationPreferences(BaseModel):
    """User notification preferences model."""

    categories: list[NotificationCategory] = Field(
        ..., description="Selected notification categories"
    )
    channels: list[NotificationChannel] = Field(
        ..., description="Selected notification channels"
    )
    updated_at: str | None = Field(None, description="ISO timestamp of last update")


class ActivityScanRequest(BaseModel):
    """Request model for activity scanning."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    scan_depth: int | None = Field(
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
    parameters: dict[str, Any] = Field(..., description="Analysis parameters")
    save_results: bool = Field(True, description="Whether to save results")


class AnalysisResult(BaseModel):
    """Analysis result model."""

    result_id: str = Field(..., description="Unique result identifier")
    workflow_type: str = Field(..., description="Type of analysis workflow")
    results: dict[str, Any] = Field(..., description="Analysis results")
    metadata: dict[str, Any] = Field(..., description="Result metadata")


class Recommendation(BaseModel):
    """Recommendation model."""

    recommendation_id: str = Field(..., description="Unique recommendation identifier")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Recommendation description")
    priority: str = Field(..., description=PRIORITY_LEVEL_DESCRIPTION)
    category: str = Field(..., description="Recommendation category")
    confidence_score: float = Field(..., description=CONFIDENCE_SCORE_DESCRIPTION)
    impact_score: float | None = Field(None, description="Expected impact score")
    related_metrics: list[str] = Field(
        default_factory=list, description="Related metric IDs"
    )
    related_activities: list[str] = Field(
        default_factory=list, description="Related activity IDs"
    )


class AnalysisWorkflowResponse(BaseModel):
    """Response model for analysis workflow."""

    workflow_id: str = Field(..., description="Workflow execution ID")
    status: str = Field(..., description="Execution status")
    results: list[AnalysisResult] = Field(..., description="Analysis results")
    recommendations: list[Recommendation] = Field(
        ..., description="Generated recommendations"
    )
    execution_time: float = Field(..., description="Execution time in seconds")


class AnalysisSearchRequest(BaseModel):
    """Request model for analysis search without activity_id."""

    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    metric_id: str = Field(..., description=METRIC_ID_FILTER_DESCRIPTION)
    evaluation_date_start: str = Field(
        ..., description="Start date for evaluation period (YYYY-MM-DD)"
    )
    evaluation_date_end: str = Field(
        ..., description="End date for evaluation period (YYYY-MM-DD)"
    )
    comparison_date_start: str = Field(
        ..., description="Start date for comparison period (YYYY-MM-DD)"
    )
    comparison_date_end: str = Field(
        ..., description="End date for comparison period (YYYY-MM-DD)"
    )
    direction: DirectionType = Field(..., description=DIRECTION_DESCRIPTION)


# Response Models
class SuccessResponse(BaseModel):
    """Standard success response."""

    success: bool = True
    message: str
    data: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error: str
    details: dict[str, Any] | None = None


class CreateNotificationResponse(SuccessResponse):
    """Response model for notification creation."""

    notification_id: str = Field(..., description="Created notification ID")


# Superset Saved Queries Models
class SavedQueryRequest(BaseRequest):
    """Request model for creating/updating saved queries."""

    label: str = Field(..., description="Label/name of the saved query")
    description: str | None = Field(None, description="Description of the saved query")
    database_id: int = Field(..., description="Database ID for the saved query")
    schema_name: str = Field(..., description="Schema name for the saved query")
    sql: str = Field(..., description="SQL query text")


class SavedQueryResponse(BaseModel):
    """Response model for saved query operations."""

    id: int = Field(..., description="Saved query ID")
    label: str = Field(..., description="Label/name of the saved query")
    description: str | None = Field(None, description="Description of the saved query")
    database_id: int = Field(..., description="Database ID")
    schema_name: str = Field(..., description="Schema name")
    sql: str = Field(..., description="SQL query text")
    created_on: str | None = Field(None, description="Creation timestamp")
    changed_on: str | None = Field(None, description="Last modification timestamp")


class SavedQueryListResponse(BaseModel):
    """Response model for saved query list."""

    saved_queries: list[SavedQueryResponse] = Field(
        ..., description="List of saved queries"
    )
    total: int = Field(..., description="Total number of saved queries")


class QueryExecutionResponse(BaseModel):
    """Response model for query execution results."""

    query_id: int | None = Field(None, description="Query execution ID")
    status: str = Field(..., description="Execution status")
    data: list[dict[str, Any]] | None = Field(None, description="Query result data")
    columns: list[dict[str, Any]] | None = Field(None, description="Column metadata")
    error: str | None = Field(None, description="Error message if execution failed")
    query: dict[str, Any] | None = Field(
        None, description="Query metadata object containing execution details"
    )


# Dataset Models


class Dataset(BaseModel):
    """Response model for dataset data."""

    id: int = Field(..., description="The unique identifier for the dataset")
    account_id: str = Field(..., description=ACCOUNT_ID_DESCRIPTION)
    dataset_id: int = Field(..., description="Unique identifier for the dataset")
    dataset_name: str = Field(..., description="Unique name for the dataset")
    products: list[str] = Field(
        ..., description="List of products that collect the data used in this dataset"
    )
    default_datetime: str = Field(
        ..., description="Name of the datetime column used to aggregate data by date"
    )
    description: str = Field(
        ..., description="Description of the dataset and its usefulness"
    )


class DatasetRequest(BaseRequest):
    """Request model for dataset operations."""

    dataset_id: int | None = Field(
        None, description="Unique identifier for the dataset (required for create)"
    )
    dataset_name: str | None = Field(
        None,
        description="Unique name for the dataset (required for create/update/delete)",
    )
    products: list[str] | None = Field(
        None, description="List of products that collect the data used in this dataset"
    )
    default_datetime: str | None = Field(
        None, description="Name of the datetime column used to aggregate data by date"
    )
    description: str | None = Field(
        None, description="Description of the dataset and its usefulness"
    )


class DatasetListResponse(BaseModel):
    """Response model for dataset list."""

    datasets: list[Dataset] = Field(..., description="List of datasets")
    total: int = Field(..., description="Total number of datasets")


# Product Models


class ProductRequest(BaseRequest):
    """Request model for product operations."""

    product: str = Field(
        ...,
        description="Name of the product (corresponds to document ID in Firestore product-metrics collection)",
    )


class ProductAddResponse(BaseModel):
    """Response model for add_product operation."""

    success: bool = True
    message: str = Field(..., description="Success message")
    data: dict[str, Any] = Field(..., description="Product processing results")


class ProductDeleteResponse(BaseModel):
    """Response model for delete_product operation."""

    success: bool = True
    message: str = Field(..., description="Success message")
    data: dict[str, Any] = Field(..., description="Deletion results")


# Organization and Account Models


class PaymentMethod(BaseModel):
    """Payment method details."""

    last_four: str = Field(..., description="Last four digits of payment method")
    brand: str = Field(..., description="Payment method brand (e.g., Visa, Mastercard)")
    expires: str = Field(..., description="Expiration date (MM/YY)")


class Billing(BaseModel):
    """Billing information for an organization."""

    payment_method: PaymentMethod = Field(..., description="Payment method details")
    address: str = Field(..., description="Billing address")
    tax_id: str = Field(..., description="Tax identification number")


class Subscription(BaseModel):
    """Subscription details for an organization."""

    plan_name: str = Field(..., description="Name of the subscription plan")
    plan_description: str = Field(
        ..., description="Description of the subscription plan"
    )
    price: float = Field(..., description="Price of the subscription")
    currency: str = Field(..., description="Currency code (e.g., USD)")
    billing_cycle: str = Field(..., description="Billing cycle (e.g., monthly, yearly)")
    next_billing_date: str = Field(..., description="Next billing date")
    features: list[str] = Field(
        ..., description="List of features included in the plan"
    )
    usage: dict[str, int] = Field(
        ..., description="Usage statistics (e.g., reports_generated, reports_limit)"
    )


class Team(BaseModel):
    """Team information for an organization."""

    members_used: int = Field(..., description="Number of team members currently used")
    members_limit: int = Field(
        ..., description="Maximum number of team members allowed"
    )
    pending_invitations: int = Field(
        ..., description="Number of pending team invitations"
    )


class Organization(BaseModel):
    """Organization entity model."""

    organization_id: str = Field(
        ..., description="Unique identifier for the organization"
    )
    organization_name: str = Field(..., description="Name of the organization")
    plan: str = Field(..., description="Subscription plan tier")
    website: str = Field(..., description="Organization website URL")
    company_size: str | None = Field(None, description="Size category of the company")
    agency: bool = Field(..., description="Whether the organization is an agency")
    child_organizations: list[str] = Field(
        default_factory=list, description="List of child organization IDs"
    )
    subscription: Subscription = Field(..., description="Subscription details")
    billing: Billing = Field(..., description="Billing information")
    team: Team = Field(..., description="Team information")


class Account(BaseModel):
    """Account entity model."""

    account_id: str = Field(..., description="Unique identifier for the account")
    account_name: str = Field(..., description="Name of the account")
    organization_id: str = Field(
        ..., description="ID of the organization this account belongs to"
    )
    industry: str = Field(..., description="Industry category")
    status: str = Field(..., description="Account status (e.g., Active, Inactive)")
    websites: list[str] = Field(
        ..., description="List of websites associated with the account"
    )
    timezone: str = Field(..., description="Timezone for the account")
    data_region: str = Field(default="", description="Data region for the account")
    region: list[str] = Field(
        default_factory=list, description="List of regions for the account"
    )
    estimated_annual_ad_budget: int | None = Field(
        None, description="Estimated annual advertising budget in USD"
    )


class OrganizationRequest(BaseModel):
    """Request model for organization operations."""

    organization_id: str | None = Field(
        None, description="Organization ID (required for update/delete)"
    )
    organization_name: str | None = Field(None, description="Name of the organization")
    plan: str | None = Field(None, description="Subscription plan tier")
    website: str | None = Field(None, description="Organization website URL")
    company_size: str | None = Field(None, description="Size category of the company")
    agency: bool | None = Field(
        None, description="Whether the organization is an agency"
    )
    child_organizations: list[str] | None = Field(
        None, description="List of child organization IDs"
    )
    subscription: Subscription | None = Field(None, description="Subscription details")
    billing: Billing | None = Field(None, description="Billing information")
    team: Team | None = Field(None, description="Team information")


class AccountRequest(BaseModel):
    """Request model for account operations."""

    account_id: str | None = Field(
        None, description="Account ID (required for update/delete)"
    )
    account_name: str | None = Field(None, description="Name of the account")
    organization_id: str | None = Field(
        None, description="ID of the organization (required for create)"
    )
    industry: str | None = Field(None, description="Industry category")
    status: str | None = Field(None, description="Account status")
    websites: list[str] | None = Field(None, description="List of websites")
    timezone: str | None = Field(None, description="Timezone for the account")
    data_region: str | None = Field(None, description="Data region for the account")
    region: list[str] | None = Field(
        None, description="List of regions for the account"
    )
    estimated_annual_ad_budget: int | None = Field(
        None, description="Estimated annual advertising budget in USD"
    )


class OrganizationListResponse(BaseModel):
    """Response model for organization list."""

    organizations: list[Organization] = Field(..., description="List of organizations")
    total: int = Field(..., description="Total number of organizations")


class AccountListResponse(BaseModel):
    """Response model for account list."""

    accounts: list[Account] = Field(..., description="List of accounts")
    total: int = Field(..., description="Total number of accounts")


# Subscription Plan Models
class SubscriptionPlanFeatures(BaseModel):
    """Features included in a subscription plan."""

    max_users: int = Field(..., description="Maximum number of team members allowed")
    max_reports: int = Field(..., description="Maximum number of reports per month")
    features: list[str] = Field(
        ..., description="List of features included in the plan"
    )


class SubscriptionPlanDefinition(BaseModel):
    """Subscription plan definition model."""

    plan_id: str = Field(..., description="Unique identifier for the plan")
    plan_name: str = Field(..., description="Name of the subscription plan")
    plan_description: str = Field(
        ..., description="Description of the subscription plan"
    )
    price: float = Field(..., description="Price of the subscription")
    currency: str = Field(..., description="Currency code (e.g., USD)")
    billing_cycle: str = Field(..., description="Billing cycle (e.g., monthly, yearly)")
    features: SubscriptionPlanFeatures = Field(
        ..., description="Plan features and limits"
    )
    is_default: bool = Field(
        False, description="Whether this is the default plan for new organizations"
    )
    is_active: bool = Field(
        True, description="Whether this plan is currently available"
    )
    created_at: str = Field(..., description="Plan creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class SubscriptionPlanListResponse(BaseModel):
    """Response model for subscription plan list."""

    plans: list[SubscriptionPlanDefinition] = Field(
        ..., description="List of subscription plans"
    )
    total: int = Field(..., description="Total number of plans")


class ChangeSubscriptionRequest(BaseModel):
    """Request model for changing organization subscription plan."""

    plan_id: str = Field(..., description="The ID of the new subscription plan")


# Industry Template Models
class IndustryTemplateSettings(BaseModel):
    """Settings recommended for an industry template."""

    timezone: str = Field(..., description="Recommended timezone")
    data_region: str = Field(..., description="Recommended data region")
    industry: str = Field(..., description="Industry name")


class IndustryTemplateDefaults(BaseModel):
    """Default settings for an industry template."""

    data_retention: int = Field(
        90, description="Data retention period in days"
    )


class IndustryTemplate(BaseModel):
    """Industry template model for account creation guidance."""

    id: str = Field(..., description="Unique identifier for the template")
    industry: str = Field(..., description="Industry name")
    name: str = Field(..., description="Template display name")
    description: str = Field(..., description="Template description")
    definition: str = Field(
        "", description="Industry definition for display in dropdown"
    )
    default_objectives: list[str] = Field(
        default_factory=list, description="Default marketing objectives"
    )
    default_channels: list[str] = Field(
        default_factory=list, description="Default marketing channels"
    )
    default_kpis: list[str] = Field(
        default_factory=list, description="Default KPIs to track"
    )
    marketing_channels: list[str] = Field(
        default_factory=list, description="Recommended marketing channels"
    )
    product_integrations: list[str] = Field(
        default_factory=list, description="Recommended product integrations"
    )
    recommended_settings: IndustryTemplateSettings = Field(
        ..., description="Recommended configuration settings"
    )
    default_settings: IndustryTemplateDefaults = Field(
        default_factory=IndustryTemplateDefaults,
        description="Default settings values"
    )
    is_active: bool = Field(
        True, description="Whether this template is currently available"
    )
    created_at: str = Field(..., description="Template creation timestamp")
    updated_at: str = Field(..., description="Template last update timestamp")


class IndustryTemplateListResponse(BaseModel):
    """Response model for industry template list."""

    templates: list[IndustryTemplate] = Field(
        ..., description="List of industry templates"
    )
    total: int = Field(..., description="Total number of templates")
