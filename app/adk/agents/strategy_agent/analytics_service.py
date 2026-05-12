"""Analytics Service for tracking agent execution metrics, costs, and performance.

This module provides comprehensive analytics capabilities using a dedicated
'analytics' Firestore database for high-volume time-series data.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, ClassVar
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from shared.account_id_utils import validate_account_id
from .retry_utils import with_batch_retry, with_read_retry, with_write_retry

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Service for tracking and analyzing agent execution metrics."""

    # Model pricing (per 1M tokens) - updated from weave_observability.py
    MODEL_PRICING: ClassVar[dict[str, dict[str, float]]] = {
        "gemini-2.0-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-2.5-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-flash-latest": {"prompt": 0.075, "response": 0.30},
        "gemini-1.5-pro": {"prompt": 3.50, "response": 10.50},
        "gemini-1.5-pro-002": {"prompt": 3.50, "response": 10.50},
        "gemini-2.5-pro": {"prompt": 3.50, "response": 10.50},
    }

    def __init__(self, account_id: str, project_id: str | None = None):
        """Initialize Analytics Service with database connections.

        Args:
            account_id: Account identifier for scoped collections
            project_id: Optional GCP project ID
        """
        self.account_id = validate_account_id(account_id)
        self.project_id = project_id
        self.execution_id = str(uuid4())

        # Initialize Firestore clients
        self._init_firestore_clients()

        # Track cumulative metrics for this execution
        self.execution_metrics = {
            "total_tokens": 0,
            "total_cost": 0.0,
            "agent_metrics": {},
            "start_time": datetime.now(timezone.utc),
        }

    def _init_firestore_clients(self):
        """Initialize Firestore clients for both databases."""
        try:
            # TEMPORARY: Commenting out analytics database to avoid permission issues
            # TODO: Revert this after fixing IAM permissions for Agent Engine service account
            # # Analytics database for high-volume metrics
            # self.analytics_db = firestore.Client(
            #     project=self.project_id, database="analytics"
            # )

            # For now, set analytics_db to None to skip analytics tracking
            self.analytics_db = None

            # Default database for configuration
            self.default_db = firestore.Client(project=self.project_id)

            logger.info(
                f"Initialized analytics service for account {self.account_id} (analytics temporarily disabled)"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Firestore clients: {e}")
            # Fallback to in-memory tracking if Firestore unavailable
            self.analytics_db = None
            self.default_db = None

    @with_write_retry(operation_name="track_agent_execution")
    def track_agent_execution(
        self,
        agent_name: str,
        prompt_tokens: int,
        response_tokens: int,
        model: str,
        execution_time: float,
        success: bool = True,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Track execution metrics for a single agent.

        Args:
            agent_name: Name of the agent
            prompt_tokens: Number of input tokens
            response_tokens: Number of output tokens
            model: Model used for execution
            execution_time: Time taken in seconds
            success: Whether execution succeeded
            error_message: Error message if failed
            metadata: Additional metadata to track

        Returns:
            Execution metrics dictionary
        """
        # Calculate cost
        model_pricing = self.MODEL_PRICING.get(
            model, self.MODEL_PRICING["gemini-2.5-flash"]
        )
        prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
        response_cost = (response_tokens / 1_000_000) * model_pricing["response"]
        total_cost = prompt_cost + response_cost

        # Prepare metrics document
        metrics = {
            "execution_id": self.execution_id,
            "agent_name": agent_name,
            "account_id": self.account_id,
            "timestamp": datetime.now(timezone.utc),
            "model": model,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "total_tokens": prompt_tokens + response_tokens,
            "prompt_cost": prompt_cost,
            "response_cost": response_cost,
            "total_cost": total_cost,
            "execution_time_seconds": execution_time,
            "success": success,
            "error_message": error_message,
            "metadata": metadata or {},
        }

        # Update cumulative metrics
        self._update_cumulative_metrics(agent_name, metrics)

        # Store in analytics database
        if self.analytics_db:
            try:
                collection = self.analytics_db.collection(
                    f"accounts/{self.account_id}/agent_analytics"
                )
                collection.add(metrics)
                logger.info(
                    f"Tracked execution for {agent_name}: "
                    f"{prompt_tokens + response_tokens} tokens, ${total_cost:.4f}"
                )
            except Exception as e:
                logger.error(f"Failed to store analytics: {e}")

        return metrics

    def _update_cumulative_metrics(self, agent_name: str, metrics: dict[str, Any]):
        """Update cumulative execution metrics."""
        self.execution_metrics["total_tokens"] += metrics["total_tokens"]
        self.execution_metrics["total_cost"] += metrics["total_cost"]

        if agent_name not in self.execution_metrics["agent_metrics"]:
            self.execution_metrics["agent_metrics"][agent_name] = {
                "executions": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_time": 0.0,
                "errors": 0,
            }

        agent_metrics = self.execution_metrics["agent_metrics"][agent_name]
        agent_metrics["executions"] += 1
        agent_metrics["total_tokens"] += metrics["total_tokens"]
        agent_metrics["total_cost"] += metrics["total_cost"]
        agent_metrics["total_time"] += metrics["execution_time_seconds"]
        if not metrics["success"]:
            agent_metrics["errors"] += 1

    @with_write_retry(operation_name="track_token_estimation")
    def track_token_estimation(
        self,
        agent_name: str,
        estimated_tokens: int,
        actual_tokens: int | None = None,
        context: str = "input",
    ):
        """Track token estimation accuracy.

        Args:
            agent_name: Name of the agent
            estimated_tokens: Estimated token count
            actual_tokens: Actual token count if available
            context: Context of estimation (input/output)
        """
        accuracy = None
        if actual_tokens:
            accuracy = abs(estimated_tokens - actual_tokens) / actual_tokens

        metrics = {
            "execution_id": self.execution_id,
            "agent_name": agent_name,
            "account_id": self.account_id,
            "timestamp": datetime.now(timezone.utc),
            "context": context,
            "estimated_tokens": estimated_tokens,
            "actual_tokens": actual_tokens,
            "accuracy_error": accuracy,
        }

        if self.analytics_db:
            try:
                collection = self.analytics_db.collection(
                    f"accounts/{self.account_id}/agent_analytics"
                )
                collection.add({**metrics, "metric_type": "token_estimation"})
            except Exception as e:
                logger.error(f"Failed to track token estimation: {e}")

    @with_read_retry(operation_name="aggregate_daily_costs")
    def aggregate_daily_costs(self, date: datetime | None = None) -> dict[str, Any]:
        """Aggregate costs for a specific day.

        Args:
            date: Date to aggregate (defaults to today)

        Returns:
            Aggregated cost metrics
        """
        if not self.analytics_db:
            return {}

        if date is None:
            date = datetime.now(timezone.utc)

        start_time = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(days=1)

        try:
            # Query analytics for the day
            collection = self.analytics_db.collection(
                f"accounts/{self.account_id}/agent_analytics"
            )
            docs = (
                collection.where(filter=FieldFilter("timestamp", ">=", start_time))
                .where(filter=FieldFilter("timestamp", "<", end_time))
                .stream()
            )

            # Aggregate metrics
            aggregation = {
                "date": start_time.date().isoformat(),
                "account_id": self.account_id,
                "total_cost": 0.0,
                "total_tokens": 0,
                "total_executions": 0,
                "cost_by_agent": {},
                "cost_by_model": {},
                "tokens_by_model": {},
            }

            for doc in docs:
                data = doc.to_dict()
                aggregation["total_cost"] += data.get("total_cost", 0)
                aggregation["total_tokens"] += data.get("total_tokens", 0)
                aggregation["total_executions"] += 1

                # By agent
                agent = data.get("agent_name", "unknown")
                if agent not in aggregation["cost_by_agent"]:
                    aggregation["cost_by_agent"][agent] = 0.0
                aggregation["cost_by_agent"][agent] += data.get("total_cost", 0)

                # By model
                model = data.get("model", "unknown")
                if model not in aggregation["cost_by_model"]:
                    aggregation["cost_by_model"][model] = 0.0
                    aggregation["tokens_by_model"][model] = 0
                aggregation["cost_by_model"][model] += data.get("total_cost", 0)
                aggregation["tokens_by_model"][model] += data.get("total_tokens", 0)

            # Store aggregation
            agg_collection = (
                self.analytics_db.collection("accounts")
                .document(self.account_id)
                .collection("cost_aggregations")
            )
            agg_collection.document(start_time.date().isoformat()).set(aggregation)

            logger.info(
                f"Daily cost aggregation for {start_time.date()}: ${aggregation['total_cost']:.2f}"
            )
            return aggregation

        except Exception as e:
            logger.error(f"Failed to aggregate daily costs: {e}")
            return {}

    def get_execution_summary(self) -> dict[str, Any]:
        """Get summary of current execution.

        Returns:
            Execution summary metrics
        """
        elapsed_time = (
            datetime.now(timezone.utc) - self.execution_metrics["start_time"]
        ).total_seconds()

        summary = {
            "execution_id": self.execution_id,
            "account_id": self.account_id,
            "elapsed_time_seconds": elapsed_time,
            "total_tokens": self.execution_metrics["total_tokens"],
            "total_cost": self.execution_metrics["total_cost"],
            "agent_metrics": self.execution_metrics["agent_metrics"],
            "cost_per_second": (
                self.execution_metrics["total_cost"] / elapsed_time
                if elapsed_time > 0
                else 0
            ),
            "tokens_per_second": (
                self.execution_metrics["total_tokens"] / elapsed_time
                if elapsed_time > 0
                else 0
            ),
        }

        return summary

    def get_cost_trends(self, days: int = 30) -> list[dict[str, Any]]:
        """Get cost trends over specified days.

        Args:
            days: Number of days to look back

        Returns:
            List of daily cost aggregations
        """
        if not self.analytics_db:
            return []

        trends = []
        end_date = datetime.now(timezone.utc)

        try:
            collection = (
                self.analytics_db.collection("accounts")
                .document(self.account_id)
                .collection("cost_aggregations")
            )

            for i in range(days):
                date = end_date - timedelta(days=i)
                doc_id = date.date().isoformat()
                doc = collection.document(doc_id).get()

                if doc.exists:
                    trends.append(doc.to_dict())
                else:
                    # No data for this day
                    trends.append(
                        {
                            "date": doc_id,
                            "total_cost": 0.0,
                            "total_tokens": 0,
                            "total_executions": 0,
                        }
                    )

            return sorted(trends, key=lambda x: x["date"])

        except Exception as e:
            logger.error(f"Failed to get cost trends: {e}")
            return []

    @with_batch_retry(operation_name="cleanup_old_metrics")
    def cleanup_old_metrics(self, retention_days: int = 90):
        """Clean up old metrics based on retention policy.

        Args:
            retention_days: Number of days to retain raw metrics
        """
        if not self.analytics_db:
            return

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        try:
            collection = self.analytics_db.collection(
                f"accounts/{self.account_id}/agent_analytics"
            )

            # Query for old documents
            old_docs = collection.where(
                filter=FieldFilter("timestamp", "<", cutoff_date)
            ).stream()

            # Batch delete
            batch = self.analytics_db.batch()
            count = 0

            for doc in old_docs:
                batch.delete(doc.reference)
                count += 1

                # Commit every 500 deletes
                if count % 500 == 0:
                    batch.commit()
                    batch = self.analytics_db.batch()

            # Commit remaining
            if count % 500 != 0:
                batch.commit()

            logger.info(f"Cleaned up {count} old metrics for account {self.account_id}")

        except Exception as e:
            logger.error(f"Failed to cleanup old metrics: {e}")
