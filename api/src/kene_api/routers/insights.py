"""Insights router for CRUD operations on insight relationships and intuitions."""

import ast
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..database import Neo4jService, get_neo4j_service
from ..models.kene_models import (
    ACCOUNT_ID_DESCRIPTION,
    MISSING_REQUIRED_IDS_ERROR,
    ActiveConfidenceLevel,
    ActiveEvidence,
    DirectionType,
    Evidence,
    InfluenceEvidence,
    Insight,
    InsightListResponse,
    InsightRequest,
    Intuition,
    RelationshipType,
    SuccessResponse,
)

router = APIRouter(tags=["insights"])

# Constants
DATABASE_UNAVAILABLE_MESSAGE = "Database service unavailable. Please try again later."


def _parse_list_field(field_value: Any) -> List[Any]:
    """Parse a field that might be a string representation of a list."""
    if isinstance(field_value, list):
        return field_value
    elif isinstance(field_value, str):
        try:
            return ast.literal_eval(field_value)
        except (ValueError, SyntaxError):
            return []
    else:
        return []


def _parse_comma_separated_field(field_value: Any) -> List[str]:
    """Parse a field that is a comma-separated string into a list of strings."""
    if isinstance(field_value, list):
        return [str(item).strip() for item in field_value]
    elif isinstance(field_value, str):
        if not field_value.strip():
            return []
        # Split by comma and strip whitespace from each item
        return [item.strip() for item in field_value.split(",") if item.strip()]
    else:
        return []


def _parse_relationship_type(relationship_data: Dict[str, Any]) -> RelationshipType:
    """Parse relationship type from relationship data."""
    relationship_type_str = relationship_data.get("type", "INFLUENCE_CONFIRMED")
    if relationship_type_str == "NO_INFLUENCE_CONFIRMED":
        return RelationshipType.NO_INFLUENCE_CONFIRMED
    elif relationship_type_str == "INFLUENCE_CONFIRMED":
        return RelationshipType.INFLUENCE_CONFIRMED
    else:
        return RelationshipType.INFLUENCE_CONFIRMED  # Default


def _parse_direction(relationship_data: Dict[str, Any]) -> Optional[DirectionType]:
    """Parse direction from relationship data."""
    if not relationship_data.get("direction"):
        return None
    direction_str = relationship_data.get("direction", "positive")
    return (
        DirectionType.POSITIVE
        if direction_str == "positive"
        else DirectionType.NEGATIVE
    )


async def _create_insight_from_record(record: Dict[str, Any]) -> Insight:
    """Create an Insight object from a Neo4j record."""
    activity_data = record.get("activity") or {}
    metric_data = record.get("metric") or {}
    activity_log_data = record.get("activity_log") or {}
    dataset_data = record.get("dataset") or {}
    relationship_data = record.get("relationship") or {}

    # Parse dataset products from the dataset's product field
    related_dataset_products = _parse_comma_separated_field(
        dataset_data.get("product", "")
    )

    # Get relationship type directly from the query result
    relationship_type_str = record.get("relationship_type", "INFLUENCE_CONFIRMED")
    if relationship_type_str == "NO_INFLUENCE_CONFIRMED":
        relationship_type = RelationshipType.NO_INFLUENCE_CONFIRMED
    else:
        relationship_type = RelationshipType.INFLUENCE_CONFIRMED

    # Parse direction from relationship properties
    direction = _parse_direction(relationship_data)

    # Parse evidence from relationship properties if it exists
    evidence = None
    if relationship_data.get("evidence"):
        try:
            evidence_data = relationship_data["evidence"]
            if isinstance(evidence_data, str):
                evidence_data = ast.literal_eval(evidence_data)

            # Create Evidence object from stored data
            active_evidence = ActiveEvidence(
                active_confidence=evidence_data.get("active_evidence", {}).get(
                    "active_confidence", ActiveConfidenceLevel.MEDIUM
                ),
                evidence=evidence_data.get("active_evidence", {}).get("evidence", []),
                data=evidence_data.get("active_evidence", {}).get("data"),
            )

            influence_evidence = InfluenceEvidence(
                influence_direction_aligned=evidence_data.get(
                    "influence_evidence", {}
                ).get("influence_direction_aligned", False),
                influence_likely=evidence_data.get("influence_evidence", {}).get(
                    "influence_likely", False
                ),
                other_conflicting_insights=evidence_data.get(
                    "influence_evidence", {}
                ).get("other_conflicting_insights", []),
                other_supporting_insights=evidence_data.get(
                    "influence_evidence", {}
                ).get("other_supporting_insights", []),
                overlapping_conflicting_insights=evidence_data.get(
                    "influence_evidence", {}
                ).get("overlapping_conflicting_insights", []),
                overlapping_supporting_insights=evidence_data.get(
                    "influence_evidence", {}
                ).get("overlapping_supporting_insights", []),
            )

            evidence = Evidence(
                active_evidence=active_evidence, influence_evidence=influence_evidence
            )
        except (ValueError, SyntaxError, TypeError):
            # If evidence parsing fails, leave it as None
            evidence = None

    return Insight(
        activity_id=activity_data.get("activity_id", ""),
        metric_id=metric_data.get("metric_id", ""),
        activity_log_id=activity_log_data.get("activity_log_id", ""),
        relationship_type=relationship_type,
        direction=direction,
        metric_verbose_name=metric_data.get("metric_name", "") or "",
        related_dataset_products=related_dataset_products,
        evidence=evidence,
        activity_description=activity_data.get("activity_description", "") or "",
    )


async def _create_intuition_from_record(record: Dict[str, Any]) -> Intuition:
    """Create an Intuition object from a Neo4j record."""
    activity_data = record.get("activity") or {}
    metric_data = record.get("metric") or {}
    relationship_data = record.get("relationship") or {}

    # Parse direction from relationship properties
    direction_str = relationship_data.get("direction", "positive")
    direction = (
        DirectionType.POSITIVE
        if direction_str == "positive"
        else DirectionType.NEGATIVE
    )

    return Intuition(
        activity_id=activity_data.get("activity_id", ""),
        metric_id=metric_data.get("metric_id", ""),
        direction=direction,
    )


def _determine_relationship_type(evidence: Optional[Evidence] = None) -> str:
    """Determine the relationship type based on evidence."""
    if evidence and evidence.influence_evidence:
        if not evidence.influence_evidence.influence_likely:
            return "NO_INFLUENCE_CONFIRMED"
    return "INFLUENCE_CONFIRMED"


def _prepare_evidence_data(
    evidence: Optional[Evidence] = None,
) -> Optional[Dict[str, Any]]:
    """Prepare evidence data for storage in Neo4j."""
    if not evidence:
        return None

    return {
        "active_evidence": {
            "active_confidence": (
                evidence.active_evidence.active_confidence.value
                if evidence.active_evidence
                else "MEDIUM"
            ),
            "evidence": (
                evidence.active_evidence.evidence if evidence.active_evidence else []
            ),
            "data": evidence.active_evidence.data if evidence.active_evidence else None,
        },
        "influence_evidence": {
            "influence_direction_aligned": (
                evidence.influence_evidence.influence_direction_aligned
                if evidence.influence_evidence
                else False
            ),
            "influence_likely": (
                evidence.influence_evidence.influence_likely
                if evidence.influence_evidence
                else False
            ),
            "other_conflicting_insights": (
                evidence.influence_evidence.other_conflicting_insights
                if evidence.influence_evidence
                else []
            ),
            "other_supporting_insights": (
                evidence.influence_evidence.other_supporting_insights
                if evidence.influence_evidence
                else []
            ),
            "overlapping_conflicting_insights": (
                evidence.influence_evidence.overlapping_conflicting_insights
                if evidence.influence_evidence
                else []
            ),
            "overlapping_supporting_insights": (
                evidence.influence_evidence.overlapping_supporting_insights
                if evidence.influence_evidence
                else []
            ),
        },
    }


@router.get("/", response_model=InsightListResponse)
async def get_insights(
    account_id: str = Query(..., description=ACCOUNT_ID_DESCRIPTION),
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> InsightListResponse:
    """
    Get all insights for an account.

    Returns insight relationships and intuitions for the account.
    Fetches Activities for an account, then ActivityLog nodes linked to those Activities,
    then finds relationships from ActivityLog to Metric nodes.
    """
    try:
        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Query to fetch insights: Account → Activity → ActivityLog → Metric relationships
        insights_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)
        MATCH (activity)-[:LOGGED]->(activity_log:ActivityLog)
        MATCH (activity_log)-[insight_rel:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(metric:Metric)
        OPTIONAL MATCH (metric)-[:CALCULATED_FROM]->(dataset:Dataset)
        RETURN activity, activity_log, properties(insight_rel) as relationship, type(insight_rel) as relationship_type, metric, dataset
        ORDER BY activity.activity_description, metric.metric_name
        """

        # Query to fetch intuitions: Account → Activity → Metric relationships with INFLUENCE_LIKELY
        intuitions_query = """
        MATCH (account:Account {account_id: $account_id})<-[:BELONGS_TO]-(activity:Activity)
        MATCH (activity)-[intuition_rel:INFLUENCE_LIKELY]->(metric:Metric)
        RETURN activity, properties(intuition_rel) as relationship, metric
        ORDER BY activity.activity_description, metric.metric_name
        """

        # Execute both queries
        insights_result = await neo4j.execute_query(
            insights_query, {"account_id": account_id}
        )
        intuitions_result = await neo4j.execute_query(
            intuitions_query, {"account_id": account_id}
        )

        # Process insights
        insights = []
        for record in insights_result:
            try:
                insight = await _create_insight_from_record(record)
                insights.append(insight)
            except Exception as e:
                # Log error but continue processing other records
                print(f"Error processing insight record: {e}")
                continue

        # Process intuitions
        intuitions = []
        for record in intuitions_result:
            try:
                intuition = await _create_intuition_from_record(record)
                intuitions.append(intuition)
            except Exception as e:
                # Log error but continue processing other records
                print(f"Error processing intuition record: {e}")
                continue

        return InsightListResponse(
            insights=insights,
            intuitions=intuitions,
            total=len(insights) + len(intuitions),
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(
            status_code=500, detail=f"Error fetching insights: {str(e)}"
        )


@router.post("/", response_model=SuccessResponse)
async def create_insight(
    request: InsightRequest,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Create a new insight relationship.

    Creates an INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED relationship
    between an ActivityLog node and a Metric node in neo4j.
    """
    try:
        if not request.activity_log_id or not request.metric_id:
            raise HTTPException(
                status_code=400,
                detail="Both activity_log_id and metric_id are required for creating insights",
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Use the explicit relationship type from the request
        relationship_type = request.relationship_type.value if request.relationship_type else "INFLUENCE_CONFIRMED"
        evidence_data = _prepare_evidence_data(request.evidence)

        # Neo4j query to create insight relationship
        query = f"""
        MATCH (al:ActivityLog {{activity_log_id: $activity_log_id}})
        MATCH (m:Metric {{metric_id: $metric_id}})
        CREATE (al)-[r:{relationship_type} {{
            evidence: $evidence,
            direction: $direction
        }}]->(m)
        RETURN r
        """

        parameters = {
            "activity_log_id": request.activity_log_id,
            "metric_id": request.metric_id,
            "evidence": str(evidence_data) if evidence_data else None,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)
        if result["relationships_created"] == 0:
            raise HTTPException(
                status_code=404, detail="ActivityLog or Metric not found"
            )

        return SuccessResponse(
            success=True,
            data=None,
            message=f"Insight relationship ({relationship_type}) created successfully",
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error creating insight: {str(e)}")


@router.put("/", response_model=SuccessResponse)
async def update_insight(
    request: InsightRequest,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Update an existing insight relationship.

    Updates properties of an INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED relationship in neo4j.
    """
    try:
        if not request.activity_log_id or not request.metric_id:
            raise HTTPException(
                status_code=400,
                detail="Both activity_log_id and metric_id are required for updating insights",
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Prepare evidence data for storage
        evidence_data = _prepare_evidence_data(request.evidence)

        # Neo4j query to update insight relationship
        query = """
        MATCH (al:ActivityLog {activity_log_id: $activity_log_id})-[r:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(m:Metric {metric_id: $metric_id})
        SET r.evidence = $evidence, r.direction = $direction
        RETURN r
        """

        parameters = {
            "activity_log_id": request.activity_log_id,
            "metric_id": request.metric_id,
            "evidence": str(evidence_data) if evidence_data else None,
            "direction": request.direction.value if request.direction else None,
        }

        result = await neo4j.execute_write_query(query, parameters)
        if result["properties_set"] == 0:
            raise HTTPException(
                status_code=404, detail="Insight relationship not found"
            )

        return SuccessResponse(
            success=True, data=None, message="Insight updated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error updating insight: {str(e)}")


@router.delete("/", response_model=SuccessResponse)
async def delete_insight(
    request: InsightRequest,
    neo4j: Neo4jService = Depends(get_neo4j_service),
) -> SuccessResponse:
    """
    Delete an insight relationship.

    Removes an INFLUENCE_CONFIRMED or NO_INFLUENCE_CONFIRMED relationship
    between ActivityLog and Metric nodes in neo4j.
    """
    try:
        if not request.activity_log_id or not request.metric_id:
            raise HTTPException(
                status_code=400,
                detail="Both activity_log_id and metric_id are required for deleting insights",
            )

        # Check Neo4j connectivity
        is_healthy = await neo4j.health_check()
        if not is_healthy:
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)

        # Neo4j query to delete insight relationship
        query = """
        MATCH (al:ActivityLog {activity_log_id: $activity_log_id})-[r:INFLUENCE_CONFIRMED|NO_INFLUENCE_CONFIRMED]->(m:Metric {metric_id: $metric_id})
        DELETE r
        RETURN count(r) as deleted_count
        """

        parameters = {
            "activity_log_id": request.activity_log_id,
            "metric_id": request.metric_id,
        }

        result = await neo4j.execute_write_query(query, parameters)
        if result["relationships_deleted"] == 0:
            raise HTTPException(
                status_code=404, detail="Insight relationship not found"
            )

        return SuccessResponse(
            success=True, data=None, message="Insight deleted successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle Neo4j connectivity issues specifically
        if "Neo4j" in str(e) or "connect" in str(e).lower():
            raise HTTPException(status_code=503, detail=DATABASE_UNAVAILABLE_MESSAGE)
        raise HTTPException(status_code=500, detail=f"Error deleting insight: {str(e)}")
