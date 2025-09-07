"""Optimization Analyzer for providing token usage recommendations.

This module analyzes token usage patterns and provides actionable recommendations
to optimize costs and performance while maintaining quality.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from .analytics_service import AnalyticsService
from .retry_utils import with_write_retry, with_read_retry, with_batch_retry

logger = logging.getLogger(__name__)


class OptimizationRecommendation:
    """Container for optimization recommendations."""

    def __init__(
        self,
        recommendation_type: str,
        description: str,
        estimated_savings_percentage: float,
        implementation_difficulty: str,  # easy, medium, hard
        priority: int,  # 1-5, higher is more important
        details: Dict[str, Any],
    ):
        """Initialize recommendation.

        Args:
            recommendation_type: Type of recommendation
            description: Human-readable description
            estimated_savings_percentage: Estimated token/cost savings
            implementation_difficulty: How hard to implement
            priority: Priority level (1-5)
            details: Additional details
        """
        self.recommendation_type = recommendation_type
        self.description = description
        self.estimated_savings_percentage = estimated_savings_percentage
        self.implementation_difficulty = implementation_difficulty
        self.priority = priority
        self.details = details
        self.created_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommendation_type": self.recommendation_type,
            "description": self.description,
            "estimated_savings_percentage": self.estimated_savings_percentage,
            "implementation_difficulty": self.implementation_difficulty,
            "priority": self.priority,
            "details": self.details,
            "created_at": self.created_at.isoformat(),
        }


class OptimizationAnalyzer:
    """Service for analyzing usage patterns and generating optimization recommendations."""

    # Model configurations for optimization decisions
    MODEL_CONFIGS = {
        "gemini-2.5-pro": {
            "best_for": ["strategy_creation", "complex_analysis"],
            "max_context": 2_097_152,
            "cost_multiplier": 46.7,  # Relative to Flash
        },
        "gemini-2.5-flash": {
            "best_for": ["review", "editing", "simple_queries"],
            "max_context": 1_048_576,
            "cost_multiplier": 1.0,  # Baseline
        },
    }

    # Thresholds for recommendations
    THRESHOLDS = {
        "context_utilization_low": 0.2,  # Under 20% context usage
        "context_utilization_high": 0.8,  # Over 80% context usage
        "error_rate_threshold": 0.1,  # 10% error rate
        "duplication_threshold": 0.3,  # 30% duplicate content
        "pro_model_simple_task_threshold": 100,  # Tokens for simple task
    }

    def __init__(self, account_id: str, project_id: Optional[str] = None):
        """Initialize Optimization Analyzer.

        Args:
            account_id: Account identifier
            project_id: Optional GCP project ID
        """
        self.account_id = account_id
        self.project_id = project_id

        # Initialize Firestore clients
        self._init_firestore_clients()

        # Initialize analytics service for data access
        self.analytics = AnalyticsService(account_id, project_id)

    def _init_firestore_clients(self):
        """Initialize Firestore clients for both databases."""
        try:
            # Analytics database for reading metrics
            self.analytics_db = firestore.Client(
                project=self.project_id, database="analytics"
            )

            # Default database for storing recommendations
            self.default_db = firestore.Client(project=self.project_id)

            logger.info(
                f"Initialized optimization analyzer for account {self.account_id}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Firestore clients: {e}")
            self.analytics_db = None
            self.default_db = None

    def analyze_usage_patterns(self, days_to_analyze: int = 7) -> Dict[str, Any]:
        """Analyze token usage patterns over specified period.

        Args:
            days_to_analyze: Number of days to analyze

        Returns:
            Analysis results with patterns identified
        """
        if not self.analytics_db:
            return {}

        patterns = self._initialize_patterns_dict(days_to_analyze)

        try:
            # Query analytics data
            docs = self._query_analytics_data(days_to_analyze)
            hourly_usage = defaultdict(lambda: {"tokens": 0, "executions": 0})

            for doc in docs:
                data = doc.to_dict()

                # Update various pattern categories
                self._update_overall_metrics(patterns, data)
                self._analyze_agent_patterns(patterns, data)
                self._analyze_model_usage(patterns, data)
                self._analyze_error_patterns(patterns, data)
                self._analyze_peak_usage(hourly_usage, data)
                self._analyze_context_utilization(patterns, data)

            # Post-processing
            self._calculate_agent_averages(patterns)
            patterns["model_usage"] = dict(patterns["model_usage"])
            patterns["error_patterns"] = dict(patterns["error_patterns"])
            patterns["peak_usage_times"] = self._identify_peak_times(hourly_usage)

            return patterns

        except Exception as e:
            logger.error(f"Failed to analyze usage patterns: {e}")
            return patterns

    def _initialize_patterns_dict(self, days_to_analyze: int) -> Dict[str, Any]:
        """Initialize the patterns dictionary structure.

        Args:
            days_to_analyze: Number of days for the analysis period

        Returns:
            Initialized patterns dictionary
        """
        return {
            "period_days": days_to_analyze,
            "total_executions": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "agent_patterns": {},
            "model_usage": defaultdict(lambda: {"count": 0, "tokens": 0, "cost": 0.0}),
            "error_patterns": defaultdict(int),
            "peak_usage_times": [],
            "context_utilization": [],
        }

    @with_read_retry(operation_name="query_analytics_data")
    def _query_analytics_data(self, days_to_analyze: int):
        """Query analytics data from Firestore.

        Args:
            days_to_analyze: Number of days to look back

        Returns:
            Firestore document stream
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days_to_analyze)
        collection = self.analytics_db.collection(f"agent_analytics_{self.account_id}")

        return collection.where(
            filter=FieldFilter("timestamp", ">=", cutoff_time)
        ).stream()

    def _update_overall_metrics(self, patterns: Dict[str, Any], data: Dict[str, Any]):
        """Update overall execution metrics.

        Args:
            patterns: Patterns dictionary to update
            data: Document data from Firestore
        """
        patterns["total_executions"] += 1
        patterns["total_tokens"] += data.get("total_tokens", 0)
        patterns["total_cost"] += data.get("total_cost", 0)

    def _analyze_agent_patterns(self, patterns: Dict[str, Any], data: Dict[str, Any]):
        """Analyze agent-specific patterns.

        Args:
            patterns: Patterns dictionary to update
            data: Document data from Firestore
        """
        agent_name = data.get("agent_name", "unknown")
        if agent_name not in patterns["agent_patterns"]:
            patterns["agent_patterns"][agent_name] = {
                "executions": 0,
                "total_tokens": 0,
                "avg_tokens": 0,
                "total_cost": 0.0,
                "errors": 0,
            }

        agent_pattern = patterns["agent_patterns"][agent_name]
        agent_pattern["executions"] += 1
        agent_pattern["total_tokens"] += data.get("total_tokens", 0)
        agent_pattern["total_cost"] += data.get("total_cost", 0)

        if not data.get("success", True):
            agent_pattern["errors"] += 1

    def _analyze_model_usage(self, patterns: Dict[str, Any], data: Dict[str, Any]):
        """Analyze model usage statistics.

        Args:
            patterns: Patterns dictionary to update
            data: Document data from Firestore
        """
        model = data.get("model", "unknown")
        patterns["model_usage"][model]["count"] += 1
        patterns["model_usage"][model]["tokens"] += data.get("total_tokens", 0)
        patterns["model_usage"][model]["cost"] += data.get("total_cost", 0)

    def _analyze_error_patterns(self, patterns: Dict[str, Any], data: Dict[str, Any]):
        """Analyze error patterns.

        Args:
            patterns: Patterns dictionary to update
            data: Document data from Firestore
        """
        if not data.get("success", True):
            patterns["error_patterns"][data.get("error_message", "unknown")] += 1

    def _analyze_peak_usage(
        self, hourly_usage: Dict[int, Dict[str, int]], data: Dict[str, Any]
    ):
        """Analyze hourly usage for peak times.

        Args:
            hourly_usage: Dictionary tracking hourly usage
            data: Document data from Firestore
        """
        timestamp = data.get("timestamp")
        if isinstance(timestamp, datetime):
            hour = timestamp.hour
            hourly_usage[hour]["tokens"] += data.get("total_tokens", 0)
            hourly_usage[hour]["executions"] += 1

    def _analyze_context_utilization(
        self, patterns: Dict[str, Any], data: Dict[str, Any]
    ):
        """Analyze context utilization statistics.

        Args:
            patterns: Patterns dictionary to update
            data: Document data from Firestore
        """
        prompt_tokens = data.get("prompt_tokens", 0)
        model = data.get("model", "unknown")

        if prompt_tokens > 0:
            model_config = self.MODEL_CONFIGS.get(
                model, self.MODEL_CONFIGS["gemini-2.5-flash"]
            )
            utilization = prompt_tokens / model_config["max_context"]
            patterns["context_utilization"].append(utilization)

    def _calculate_agent_averages(self, patterns: Dict[str, Any]):
        """Calculate average metrics for each agent.

        Args:
            patterns: Patterns dictionary to update
        """
        for agent_pattern in patterns["agent_patterns"].values():
            if agent_pattern["executions"] > 0:
                agent_pattern["avg_tokens"] = (
                    agent_pattern["total_tokens"] / agent_pattern["executions"]
                )

    def _identify_peak_times(
        self, hourly_usage: Dict[int, Dict[str, int]]
    ) -> List[Dict[str, Any]]:
        """Identify peak usage times from hourly data.

        Args:
            hourly_usage: Dictionary of hourly usage statistics

        Returns:
            List of top 3 peak usage hours
        """
        if not hourly_usage:
            return []

        sorted_hours = sorted(
            hourly_usage.items(), key=lambda x: x[1]["tokens"], reverse=True
        )[:3]

        return [
            {"hour": hour, "tokens": data["tokens"], "executions": data["executions"]}
            for hour, data in sorted_hours
        ]

    def generate_recommendations(
        self, usage_patterns: Optional[Dict[str, Any]] = None
    ) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on usage patterns.

        Args:
            usage_patterns: Pre-analyzed patterns or None to analyze

        Returns:
            List of optimization recommendations
        """
        if usage_patterns is None:
            usage_patterns = self.analyze_usage_patterns()

        recommendations = []

        # 1. Model downgrade opportunities
        recommendations.extend(self._check_model_optimization(usage_patterns))

        # 2. Context optimization
        recommendations.extend(self._check_context_optimization(usage_patterns))

        # 3. Error reduction
        recommendations.extend(self._check_error_patterns(usage_patterns))

        # 4. Agent-specific optimizations
        recommendations.extend(self._check_agent_optimization(usage_patterns))

        # 5. Timing optimizations
        recommendations.extend(self._check_timing_optimization(usage_patterns))

        # Sort by priority
        recommendations.sort(key=lambda x: x.priority, reverse=True)

        # Store recommendations
        self._store_recommendations(recommendations)

        return recommendations

    def _check_model_optimization(
        self, patterns: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Check for model optimization opportunities.

        Args:
            patterns: Usage patterns

        Returns:
            Model optimization recommendations
        """
        recommendations = []
        model_usage = patterns.get("model_usage", {})

        # Check if Pro model is being used for simple tasks
        for model, usage in model_usage.items():
            if "pro" in model.lower():
                avg_tokens = (
                    usage["tokens"] / usage["count"] if usage["count"] > 0 else 0
                )

                if avg_tokens < self.THRESHOLDS["pro_model_simple_task_threshold"]:
                    # Pro model used for simple tasks
                    flash_cost_per_token = 0.075 / 1_000_000  # Prompt cost
                    pro_cost_per_token = 3.50 / 1_000_000
                    potential_savings = (
                        pro_cost_per_token - flash_cost_per_token
                    ) * usage["tokens"]
                    savings_percentage = (
                        (potential_savings / usage["cost"]) * 100
                        if usage["cost"] > 0
                        else 0
                    )

                    recommendations.append(
                        OptimizationRecommendation(
                            recommendation_type="model_downgrade",
                            description=f"Consider using Gemini Flash instead of Pro for simple tasks (avg {avg_tokens:.0f} tokens)",
                            estimated_savings_percentage=savings_percentage,
                            implementation_difficulty="easy",
                            priority=4 if savings_percentage > 50 else 3,
                            details={
                                "current_model": model,
                                "recommended_model": "gemini-2.5-flash",
                                "avg_tokens_per_request": avg_tokens,
                                "potential_monthly_savings": potential_savings * 30,
                            },
                        )
                    )

        return recommendations

    def _check_context_optimization(
        self, patterns: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Check for context optimization opportunities.

        Args:
            patterns: Usage patterns

        Returns:
            Context optimization recommendations
        """
        recommendations = []
        context_utilization = patterns.get("context_utilization", [])

        if not context_utilization:
            return recommendations

        avg_utilization = sum(context_utilization) / len(context_utilization)

        if avg_utilization < self.THRESHOLDS["context_utilization_low"]:
            # Very low context utilization
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_type="context_reduction",
                    description=f"Context utilization is very low ({avg_utilization:.1%}). Consider reducing context size.",
                    estimated_savings_percentage=20,
                    implementation_difficulty="medium",
                    priority=3,
                    details={
                        "current_utilization": avg_utilization,
                        "recommendation": "Implement dynamic context sizing based on task requirements",
                    },
                )
            )

        elif avg_utilization > self.THRESHOLDS["context_utilization_high"]:
            # High context utilization - risk of hitting limits
            recommendations.append(
                OptimizationRecommendation(
                    recommendation_type="context_chunking",
                    description=f"Context utilization is high ({avg_utilization:.1%}). Implement chunking to avoid limits.",
                    estimated_savings_percentage=0,  # Not about savings but reliability
                    implementation_difficulty="hard",
                    priority=5,
                    details={
                        "current_utilization": avg_utilization,
                        "recommendation": "Implement document chunking and summarization",
                    },
                )
            )

        return recommendations

    def _check_error_patterns(
        self, patterns: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Check error patterns for optimization opportunities.

        Args:
            patterns: Usage patterns

        Returns:
            Error reduction recommendations
        """
        recommendations = []
        total_executions = patterns.get("total_executions", 0)

        if total_executions == 0:
            return recommendations

        # Check agent error rates
        for agent_name, agent_pattern in patterns.get("agent_patterns", {}).items():
            error_rate = (
                agent_pattern["errors"] / agent_pattern["executions"]
                if agent_pattern["executions"] > 0
                else 0
            )

            if error_rate > self.THRESHOLDS["error_rate_threshold"]:
                recommendations.append(
                    OptimizationRecommendation(
                        recommendation_type="error_reduction",
                        description=f"High error rate for {agent_name} ({error_rate:.1%}). Investigation needed.",
                        estimated_savings_percentage=error_rate * 100,  # Wasted tokens
                        implementation_difficulty="medium",
                        priority=5,
                        details={
                            "agent_name": agent_name,
                            "error_rate": error_rate,
                            "total_errors": agent_pattern["errors"],
                            "wasted_tokens": int(
                                agent_pattern["total_tokens"] * error_rate
                            ),
                        },
                    )
                )

        return recommendations

    def _check_agent_optimization(
        self, patterns: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Check for agent-specific optimization opportunities.

        Args:
            patterns: Usage patterns

        Returns:
            Agent optimization recommendations
        """
        recommendations = []
        agent_patterns = patterns.get("agent_patterns", {})

        # Find most expensive agents
        if agent_patterns:
            sorted_agents = sorted(
                agent_patterns.items(), key=lambda x: x[1]["total_cost"], reverse=True
            )

            # Focus on top 3 most expensive agents
            for agent_name, agent_data in sorted_agents[:3]:
                if agent_data["avg_tokens"] > 50000:  # Large token usage
                    recommendations.append(
                        OptimizationRecommendation(
                            recommendation_type="agent_optimization",
                            description=f"Optimize {agent_name} - high token usage ({agent_data['avg_tokens']:.0f} avg)",
                            estimated_savings_percentage=15,  # Conservative estimate
                            implementation_difficulty="hard",
                            priority=3,
                            details={
                                "agent_name": agent_name,
                                "avg_tokens": agent_data["avg_tokens"],
                                "total_cost": agent_data["total_cost"],
                                "suggestions": [
                                    "Review and optimize prompts",
                                    "Implement response caching",
                                    "Consider breaking into smaller sub-agents",
                                ],
                            },
                        )
                    )

        return recommendations

    def _check_timing_optimization(
        self, patterns: Dict[str, Any]
    ) -> List[OptimizationRecommendation]:
        """Check for timing optimization opportunities.

        Args:
            patterns: Usage patterns

        Returns:
            Timing optimization recommendations
        """
        recommendations = []
        peak_times = patterns.get("peak_usage_times", [])

        if peak_times and len(peak_times) > 0:
            # Check if peak usage is concentrated
            top_hour = peak_times[0]
            if top_hour["executions"] > patterns["total_executions"] * 0.3:
                recommendations.append(
                    OptimizationRecommendation(
                        recommendation_type="load_distribution",
                        description=f"High concentration of usage at hour {top_hour['hour']}:00. Consider load distribution.",
                        estimated_savings_percentage=5,  # Potential API rate savings
                        implementation_difficulty="medium",
                        priority=2,
                        details={
                            "peak_hour": top_hour["hour"],
                            "peak_executions": top_hour["executions"],
                            "recommendation": "Implement request queuing and load balancing",
                        },
                    )
                )

        return recommendations

    @with_batch_retry(operation_name="store_recommendations")
    def _store_recommendations(self, recommendations: List[OptimizationRecommendation]):
        """Store recommendations in Firestore.

        Args:
            recommendations: List of recommendations to store
        """
        if not self.default_db or not recommendations:
            return

        try:
            collection = self.default_db.collection("optimization_recommendations")

            # Create batch update
            batch = self.default_db.batch()

            # Store as single document per account with timestamp
            doc_id = f"{self.account_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            doc_ref = collection.document(doc_id)

            batch.set(
                doc_ref,
                {
                    "account_id": self.account_id,
                    "generated_at": datetime.now(timezone.utc),
                    "recommendations": [r.to_dict() for r in recommendations],
                    "total_estimated_savings": sum(
                        r.estimated_savings_percentage for r in recommendations
                    ),
                },
            )

            # Also update latest recommendations
            latest_ref = collection.document(f"{self.account_id}_latest")
            batch.set(
                latest_ref,
                {
                    "account_id": self.account_id,
                    "updated_at": datetime.now(timezone.utc),
                    "recommendations": [r.to_dict() for r in recommendations],
                    "total_estimated_savings": sum(
                        r.estimated_savings_percentage for r in recommendations
                    ),
                },
            )

            batch.commit()
            logger.info(
                f"Stored {len(recommendations)} recommendations for account {self.account_id}"
            )

        except Exception as e:
            logger.error(f"Failed to store recommendations: {e}")

    @with_read_retry(operation_name="get_latest_recommendations")
    def get_latest_recommendations(self) -> List[Dict[str, Any]]:
        """Get latest recommendations for the account.

        Returns:
            List of recommendation dictionaries
        """
        if not self.default_db:
            return []

        try:
            doc = (
                self.default_db.collection("optimization_recommendations")
                .document(f"{self.account_id}_latest")
                .get()
            )

            if doc.exists:
                data = doc.to_dict()
                return data.get("recommendations", [])

            return []

        except Exception as e:
            logger.error(f"Failed to get latest recommendations: {e}")
            return []

    def apply_automatic_optimizations(self) -> Dict[str, Any]:
        """Apply automatic optimizations that don't require code changes.

        Returns:
            Summary of applied optimizations
        """
        applied = {"timestamp": datetime.now(timezone.utc), "optimizations_applied": []}

        # Get latest recommendations
        recommendations = self.get_latest_recommendations()

        for rec in recommendations:
            if rec["implementation_difficulty"] == "easy" and rec["priority"] >= 4:
                # These are safe to apply automatically
                if rec["recommendation_type"] == "model_downgrade":
                    # This would need to be implemented in the agent configuration
                    logger.info(f"Would apply model downgrade: {rec['description']}")
                    applied["optimizations_applied"].append(
                        {
                            "type": "model_downgrade",
                            "description": rec["description"],
                            "status": "pending_configuration",
                        }
                    )

        return applied
