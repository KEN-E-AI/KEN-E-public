"""Performance Profiler for identifying bottlenecks in agent execution.

This module provides comprehensive performance profiling capabilities to track
execution times, identify bottlenecks, and optimize agent performance.

THREAD SAFETY WARNING:
----------------------
This module uses thread-local storage (threading.local()) to track operations
within each thread. While this provides thread safety for concurrent operations,
there are important limitations to be aware of:

1. **Thread-Local Data Isolation**: Operations started in one thread cannot be
   accessed or completed from another thread. Each thread maintains its own
   operation stack.

2. **Async/Await Compatibility**: Thread-local storage may not work correctly
   with async/await patterns if the async runtime moves coroutines between
   threads. For async code, consider using contextvars instead.

3. **Thread Pool Executors**: When using thread pools, be aware that threads
   may be reused, and thread-local data persists across tasks unless explicitly
   cleared.

4. **Multiprocessing**: Thread-local storage is not shared across processes.
   Each process will have its own independent profiler state.

Example of correct usage:
```python
# Each thread tracks its own operations
def worker_thread():
    profiler = PerformanceProfiler("account", "project")
    op = profiler.start_operation("agent", "task")
    # ... do work ...
    profiler.end_operation(op)  # Must be called in same thread
```

Example of incorrect usage:
```python
# DON'T DO THIS - operations cannot cross thread boundaries
op = profiler.start_operation("agent", "task")  # Main thread
thread = Thread(target=lambda: profiler.end_operation(op))  # Different thread
thread.start()  # This will fail or produce incorrect results
```

For production deployments with complex threading or async requirements,
consider implementing a centralized profiling service or using distributed
tracing solutions like OpenTelemetry.
"""

import functools
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from .retry_utils import with_write_retry, with_read_retry, with_batch_retry

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""

    agent_name: str
    operation: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    child_operations: List["PerformanceMetrics"] = field(default_factory=list)

    def complete(self, success: bool = True, error: Optional[str] = None):
        """Mark operation as complete."""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        self.success = success
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "agent_name": self.agent_name,
            "operation": self.operation,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
            "child_operations": [child.to_dict() for child in self.child_operations],
        }


class PerformanceProfiler:
    """Service for profiling agent performance and identifying bottlenecks."""

    def __init__(self, account_id: str, project_id: Optional[str] = None):
        """Initialize Performance Profiler.

        Args:
            account_id: Account identifier for scoped collections
            project_id: Optional GCP project ID
        """
        self.account_id = account_id
        self.project_id = project_id
        self.execution_id = str(uuid4())

        # Thread-local storage for nested operation tracking
        self._thread_local = threading.local()

        # Global metrics storage
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.operation_stack: List[PerformanceMetrics] = []

        # Initialize Firestore client for analytics database
        self._init_firestore_client()

        # Performance thresholds (in seconds)
        self.thresholds = {
            "slow_operation": 5.0,
            "very_slow_operation": 10.0,
            "timeout_warning": 30.0,
        }

    def _init_firestore_client(self):
        """Initialize Firestore client for analytics database."""
        try:
            self.analytics_db = firestore.Client(
                project=self.project_id, database="analytics"
            )
            logger.info(
                f"Initialized performance profiler for account {self.account_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            self.analytics_db = None

    @property
    def current_stack(self) -> List[PerformanceMetrics]:
        """Get thread-local operation stack."""
        if not hasattr(self._thread_local, "stack"):
            self._thread_local.stack = []
        return self._thread_local.stack

    def start_operation(
        self, agent_name: str, operation: str, metadata: Optional[Dict[str, Any]] = None
    ) -> PerformanceMetrics:
        """Start tracking a new operation.

        Args:
            agent_name: Name of the agent
            operation: Operation being performed
            metadata: Additional metadata

        Returns:
            Performance metrics object
        """
        metrics = PerformanceMetrics(
            agent_name=agent_name,
            operation=operation,
            start_time=time.time(),
            metadata=metadata or {},
        )

        # Add to current operation stack
        stack = self.current_stack
        if stack:
            # This is a child operation
            parent = stack[-1]
            parent.child_operations.append(metrics)

        stack.append(metrics)

        # Store in global metrics
        operation_id = f"{agent_name}:{operation}:{uuid4()}"
        self.metrics[operation_id] = metrics

        logger.debug(f"Started operation: {agent_name}:{operation}")
        return metrics

    @with_write_retry(operation_name="end_performance_operation")
    def end_operation(
        self,
        metrics: PerformanceMetrics,
        success: bool = True,
        error: Optional[str] = None,
    ):
        """End tracking for an operation.

        Args:
            metrics: Performance metrics object
            success: Whether operation succeeded
            error: Error message if failed
        """
        metrics.complete(success=success, error=error)

        # Remove from stack
        stack = self.current_stack
        if stack and stack[-1] == metrics:
            stack.pop()

        # Log slow operations
        if metrics.duration:
            if metrics.duration > self.thresholds["timeout_warning"]:
                logger.warning(
                    f"Operation timeout warning: {metrics.agent_name}:{metrics.operation} "
                    f"took {metrics.duration:.2f}s"
                )
            elif metrics.duration > self.thresholds["very_slow_operation"]:
                logger.warning(
                    f"Very slow operation: {metrics.agent_name}:{metrics.operation} "
                    f"took {metrics.duration:.2f}s"
                )
            elif metrics.duration > self.thresholds["slow_operation"]:
                logger.info(
                    f"Slow operation: {metrics.agent_name}:{metrics.operation} "
                    f"took {metrics.duration:.2f}s"
                )

        # Store in Firestore
        self._store_metrics(metrics)

    def _store_metrics(self, metrics: PerformanceMetrics):
        """Store performance metrics in Firestore."""
        if not self.analytics_db or not metrics.duration:
            return

        try:
            collection = self.analytics_db.collection(
                f"performance_profiles_{self.account_id}"
            )

            doc = {
                "execution_id": self.execution_id,
                "account_id": self.account_id,
                "timestamp": datetime.now(timezone.utc),
                "agent_name": metrics.agent_name,
                "operation": metrics.operation,
                "duration_seconds": metrics.duration,
                "success": metrics.success,
                "error": metrics.error,
                "metadata": metrics.metadata,
                "is_bottleneck": metrics.duration > self.thresholds["slow_operation"],
                "severity": self._get_severity(metrics.duration),
            }

            collection.add(doc)

        except Exception as e:
            logger.error(f"Failed to store performance metrics: {e}")

    def _get_severity(self, duration: float) -> str:
        """Get severity level based on duration."""
        if duration > self.thresholds["timeout_warning"]:
            return "critical"
        elif duration > self.thresholds["very_slow_operation"]:
            return "high"
        elif duration > self.thresholds["slow_operation"]:
            return "medium"
        else:
            return "low"

    def profile_operation(self, agent_name: str, operation: str):
        """Decorator for profiling function execution.

        Args:
            agent_name: Name of the agent
            operation: Operation being performed
        """

        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                metrics = self.start_operation(agent_name, operation)

                try:
                    result = func(*args, **kwargs)
                    self.end_operation(metrics, success=True)
                    return result

                except Exception as e:
                    self.end_operation(metrics, success=False, error=str(e))
                    raise

            return wrapper

        return decorator

    @with_read_retry(operation_name="get_bottlenecks")
    def get_bottlenecks(
        self, time_window_hours: int = 24, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Identify bottlenecks in recent executions.

        Args:
            time_window_hours: Hours to look back
            limit: Maximum number of bottlenecks to return

        Returns:
            List of bottleneck operations
        """
        if not self.analytics_db:
            return []

        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(
                hours=time_window_hours
            )
            collection = self.analytics_db.collection(
                f"performance_profiles_{self.account_id}"
            )

            # Query for slow operations
            query = (
                collection.where(filter=FieldFilter("timestamp", ">=", cutoff_time))
                .where(filter=FieldFilter("is_bottleneck", "==", True))
                .order_by("duration_seconds", direction=firestore.Query.DESCENDING)
                .limit(limit)
            )

            bottlenecks = []
            for doc in query.stream():
                data = doc.to_dict()
                bottlenecks.append(
                    {
                        "agent_name": data.get("agent_name"),
                        "operation": data.get("operation"),
                        "duration": data.get("duration_seconds"),
                        "severity": data.get("severity"),
                        "timestamp": data.get("timestamp"),
                        "error": data.get("error"),
                    }
                )

            return bottlenecks

        except Exception as e:
            logger.error(f"Failed to get bottlenecks: {e}")
            return []

    @with_read_retry(operation_name="get_performance_summary")
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary for current execution.

        Returns:
            Performance summary statistics
        """
        summary = {
            "execution_id": self.execution_id,
            "total_operations": len(self.metrics),
            "completed_operations": sum(1 for m in self.metrics.values() if m.end_time),
            "failed_operations": sum(1 for m in self.metrics.values() if not m.success),
            "total_duration": sum(
                m.duration for m in self.metrics.values() if m.duration
            ),
            "agent_performance": defaultdict(
                lambda: {
                    "operations": 0,
                    "total_duration": 0.0,
                    "avg_duration": 0.0,
                    "failures": 0,
                }
            ),
        }

        # Aggregate by agent
        for metrics in self.metrics.values():
            if metrics.duration:
                agent_stats = summary["agent_performance"][metrics.agent_name]
                agent_stats["operations"] += 1
                agent_stats["total_duration"] += metrics.duration
                agent_stats["avg_duration"] = (
                    agent_stats["total_duration"] / agent_stats["operations"]
                )
                if not metrics.success:
                    agent_stats["failures"] += 1

        # Convert defaultdict to regular dict
        summary["agent_performance"] = dict(summary["agent_performance"])

        # Identify slowest agent
        if summary["agent_performance"]:
            slowest_agent = max(
                summary["agent_performance"].items(), key=lambda x: x[1]["avg_duration"]
            )
            summary["slowest_agent"] = {
                "name": slowest_agent[0],
                "avg_duration": slowest_agent[1]["avg_duration"],
            }

        return summary

    def analyze_execution_path(self) -> Dict[str, Any]:
        """Analyze the execution path to identify optimization opportunities.

        Returns:
            Analysis of execution path with recommendations
        """
        analysis = {
            "execution_id": self.execution_id,
            "critical_path": [],
            "parallel_opportunities": [],
            "redundant_operations": [],
            "recommendations": [],
        }

        # Find critical path (longest sequence of operations)
        critical_path_duration = 0.0
        critical_path_ops = []

        for metrics in self.metrics.values():
            if metrics.duration and metrics.duration > critical_path_duration:
                critical_path_duration = metrics.duration
                critical_path_ops = [metrics]

                # Include child operations
                def add_children(parent: PerformanceMetrics):
                    for child in parent.child_operations:
                        critical_path_ops.append(child)
                        if child.child_operations:
                            add_children(child)

                add_children(metrics)

        analysis["critical_path"] = [
            {"agent": op.agent_name, "operation": op.operation, "duration": op.duration}
            for op in critical_path_ops
            if op.duration
        ]

        # Identify parallel opportunities
        sequential_ops = defaultdict(list)
        for metrics in self.metrics.values():
            if metrics.duration:
                sequential_ops[metrics.agent_name].append(metrics)

        for agent, ops in sequential_ops.items():
            if len(ops) > 1:
                # Check if operations could run in parallel
                ops_sorted = sorted(ops, key=lambda x: x.start_time)
                for i in range(len(ops_sorted) - 1):
                    if ops_sorted[i].end_time and ops_sorted[i + 1].start_time:
                        if ops_sorted[i].end_time < ops_sorted[i + 1].start_time:
                            analysis["parallel_opportunities"].append(
                                {
                                    "agent": agent,
                                    "operations": [
                                        ops_sorted[i].operation,
                                        ops_sorted[i + 1].operation,
                                    ],
                                    "potential_time_saved": min(
                                        ops_sorted[i].duration or 0,
                                        ops_sorted[i + 1].duration or 0,
                                    ),
                                }
                            )

        # Generate recommendations
        if critical_path_duration > 30:
            analysis["recommendations"].append(
                "Critical path exceeds 30 seconds. Consider optimizing longest operations."
            )

        if analysis["parallel_opportunities"]:
            total_savings = sum(
                opp["potential_time_saved"]
                for opp in analysis["parallel_opportunities"]
            )
            analysis["recommendations"].append(
                f"Found {len(analysis['parallel_opportunities'])} parallel opportunities "
                f"that could save {total_savings:.2f} seconds."
            )

        return analysis
