"""Queue-based Async Analytics for non-blocking operations.

This module provides a queue-based implementation for asynchronous analytics,
preventing blocking of agent execution while maintaining data integrity.
"""

import atexit
import json
import logging
import queue
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from google.cloud import firestore

from shared.account_id_utils import validate_account_id

logger = logging.getLogger(__name__)


class AsyncAnalyticsQueue:
    """Queue-based analytics service for non-blocking operations.

    This implementation uses an in-memory queue with a background worker thread
    to batch and process analytics events without blocking agent execution.
    """

    # Queue configuration defaults
    DEFAULT_QUEUE_SIZE = 10000
    DEFAULT_BATCH_SIZE = 100
    DEFAULT_FLUSH_INTERVAL = 5.0  # seconds
    DEFAULT_MAX_RETRY_ATTEMPTS = 3

    def __init__(
        self,
        account_id: str,
        project_id: Optional[str] = None,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        enable_background_worker: bool = True,
    ):
        """Initialize async analytics queue.

        Args:
            account_id: Account identifier
            project_id: Optional GCP project ID
            queue_size: Maximum queue size before blocking
            batch_size: Number of events to batch before writing
            flush_interval: Time interval for forced flush (seconds)
            enable_background_worker: Whether to start background worker
        """
        self.account_id = validate_account_id(account_id)
        self.project_id = project_id
        self.queue_size = queue_size
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        # Initialize queue and buffers
        self.event_queue = queue.Queue(maxsize=queue_size)
        self.failed_events = deque(maxlen=1000)  # Keep last 1000 failed events

        # Worker thread management
        self.worker_thread = None
        self.shutdown_event = threading.Event()
        self.flush_lock = threading.Lock()

        # Metrics tracking
        self.queue_metrics = {
            "events_queued": 0,
            "events_processed": 0,
            "events_failed": 0,
            "batches_written": 0,
            "queue_full_count": 0,
            "last_flush_time": None,
        }

        # Initialize Firestore client
        self._init_firestore()

        # Start background worker if enabled
        if enable_background_worker:
            self._start_worker()

        # Register shutdown handler
        atexit.register(self.shutdown)

    def _init_firestore(self):
        """Initialize Firestore client."""
        try:
            self.analytics_db = firestore.Client(
                project=self.project_id, database="analytics"
            )
            logger.info(
                f"Initialized async analytics queue for account {self.account_id}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            self.analytics_db = None

    def _start_worker(self):
        """Start background worker thread."""
        if self.worker_thread and self.worker_thread.is_alive():
            logger.warning("Worker thread already running")
            return

        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            name=f"analytics-worker-{self.account_id}",
            daemon=True,
        )
        self.worker_thread.start()
        logger.info(f"Started analytics worker thread for account {self.account_id}")

    def _worker_loop(self):
        """Background worker loop for processing events."""
        batch = []
        last_flush = time.time()

        while not self.shutdown_event.is_set():
            try:
                # Calculate timeout for queue.get()
                time_since_flush = time.time() - last_flush
                timeout = max(0.1, self.flush_interval - time_since_flush)

                # Try to get event from queue
                try:
                    event = self.event_queue.get(timeout=timeout)
                    batch.append(event)
                    self.event_queue.task_done()
                except queue.Empty:
                    pass

                # Check if we should flush
                should_flush = (
                    len(batch) >= self.batch_size
                    or time.time() - last_flush >= self.flush_interval
                    or (len(batch) > 0 and self.shutdown_event.is_set())
                )

                if should_flush and batch:
                    self._flush_batch(batch)
                    batch = []
                    last_flush = time.time()

            except Exception as e:
                logger.error(f"Error in analytics worker loop: {e}")
                time.sleep(1)  # Prevent tight loop on persistent errors

        # Final flush on shutdown
        if batch:
            self._flush_batch(batch)

    def _flush_batch(self, batch: List[Dict[str, Any]]):
        """Flush a batch of events to Firestore.

        Args:
            batch: List of analytics events to write
        """
        if not self.analytics_db or not batch:
            return

        with self.flush_lock:
            try:
                # Create Firestore batch
                fs_batch = self.analytics_db.batch()
                collection = self.analytics_db.collection(
                    f"accounts/{self.account_id}/agent_analytics"
                )

                # Add all events to batch
                for event in batch:
                    doc_ref = collection.document()
                    fs_batch.set(doc_ref, event)

                # Commit batch
                fs_batch.commit()

                # Update metrics
                self.queue_metrics["events_processed"] += len(batch)
                self.queue_metrics["batches_written"] += 1
                self.queue_metrics["last_flush_time"] = datetime.now(timezone.utc)

                logger.debug(f"Flushed {len(batch)} analytics events to Firestore")

            except Exception as e:
                logger.error(f"Failed to flush analytics batch: {e}")
                # Store failed events for potential retry
                self.failed_events.extend(batch)
                self.queue_metrics["events_failed"] += len(batch)

    def track_event(
        self, event_type: str, data: Dict[str, Any], priority: bool = False
    ) -> bool:
        """Queue an analytics event for processing.

        Args:
            event_type: Type of analytics event
            data: Event data to track
            priority: Whether this is a high-priority event

        Returns:
            True if event was queued, False if queue is full
        """
        event = {
            "event_id": str(uuid4()),
            "account_id": self.account_id,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        try:
            # Try to add to queue with minimal timeout
            timeout = 0.1 if not priority else 1.0
            self.event_queue.put(event, timeout=timeout)
            self.queue_metrics["events_queued"] += 1
            return True

        except queue.Full:
            self.queue_metrics["queue_full_count"] += 1
            logger.warning(f"Analytics queue full for account {self.account_id}")

            # For priority events, try harder
            if priority:
                try:
                    # Force flush and retry
                    self._force_flush()
                    self.event_queue.put(event, timeout=1.0)
                    return True
                except queue.Full:
                    pass

            return False

    def track_agent_execution(
        self,
        agent_name: str,
        prompt_tokens: int,
        response_tokens: int,
        model: str,
        execution_time: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Track agent execution metrics asynchronously.

        Args:
            agent_name: Name of the agent
            prompt_tokens: Number of input tokens
            response_tokens: Number of output tokens
            model: Model used
            execution_time: Execution time in seconds
            success: Whether execution succeeded
            error_message: Error message if failed
            metadata: Additional metadata

        Returns:
            True if event was queued successfully
        """
        data = {
            "agent_name": agent_name,
            "prompt_tokens": prompt_tokens,
            "response_tokens": response_tokens,
            "total_tokens": prompt_tokens + response_tokens,
            "model": model,
            "execution_time_seconds": execution_time,
            "success": success,
            "error_message": error_message,
            "metadata": metadata or {},
        }

        return self.track_event("agent_execution", data, priority=True)

    def _force_flush(self):
        """Force immediate flush of pending events."""
        # Signal worker to flush
        temp_batch = []

        # Drain queue into temporary batch
        while not self.event_queue.empty():
            try:
                event = self.event_queue.get_nowait()
                temp_batch.append(event)
                self.event_queue.task_done()
            except queue.Empty:
                break

        # Flush the batch
        if temp_batch:
            self._flush_batch(temp_batch)

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status and metrics.

        Returns:
            Queue status dictionary
        """
        return {
            "queue_size": self.event_queue.qsize(),
            "max_queue_size": self.queue_size,
            "utilization_percent": (self.event_queue.qsize() / self.queue_size) * 100,
            "worker_alive": self.worker_thread.is_alive()
            if self.worker_thread
            else False,
            "metrics": self.queue_metrics.copy(),
            "failed_events_count": len(self.failed_events),
        }

    def flush(self, timeout: float = 10.0) -> bool:
        """Manually flush all pending events.

        Args:
            timeout: Maximum time to wait for flush (seconds)

        Returns:
            True if flush completed, False if timeout
        """
        start_time = time.time()

        # Force flush
        self._force_flush()

        # Wait for queue to empty
        while not self.event_queue.empty():
            if time.time() - start_time > timeout:
                logger.warning("Flush timeout - some events may not be processed")
                return False
            time.sleep(0.1)

        return True

    def shutdown(self, timeout: float = 30.0):
        """Gracefully shutdown the analytics queue.

        Args:
            timeout: Maximum time to wait for shutdown (seconds)
        """
        logger.info(f"Shutting down analytics queue for account {self.account_id}")

        # Signal shutdown
        self.shutdown_event.set()

        # Wait for worker to finish
        if self.worker_thread and self.worker_thread.is_alive():
            self.worker_thread.join(timeout=timeout)

            if self.worker_thread.is_alive():
                logger.warning("Worker thread did not shut down cleanly")

        # Final flush attempt
        self.flush(timeout=5.0)

        # Log final metrics
        logger.info(
            f"Analytics queue shutdown - Processed: {self.queue_metrics['events_processed']}, "
            f"Failed: {self.queue_metrics['events_failed']}"
        )


class AsyncAnalyticsAdapter:
    """Adapter to make AsyncAnalyticsQueue compatible with existing AnalyticsService interface.

    This allows gradual migration from sync to async analytics.
    """

    def __init__(self, account_id: str, project_id: Optional[str] = None):
        """Initialize adapter with async queue."""
        self.queue = AsyncAnalyticsQueue(
            account_id=account_id, project_id=project_id, enable_background_worker=True
        )
        self.account_id = account_id
        self.execution_id = str(uuid4())

        # Track cumulative metrics locally
        self.execution_metrics = {
            "total_tokens": 0,
            "total_cost": 0.0,
            "agent_metrics": {},
            "start_time": datetime.now(timezone.utc),
        }

    def track_agent_execution(
        self,
        agent_name: str,
        prompt_tokens: int,
        response_tokens: int,
        model: str,
        execution_time: float,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Track agent execution (compatible with AnalyticsService).

        Returns metrics dict for compatibility, but processing is async.
        """
        # Queue the event asynchronously
        queued = self.queue.track_agent_execution(
            agent_name=agent_name,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
            model=model,
            execution_time=execution_time,
            success=success,
            error_message=error_message,
            metadata=metadata,
        )

        if not queued:
            logger.warning(f"Failed to queue analytics for {agent_name}")

        # Calculate metrics for return value (compatibility)
        from .analytics_service import AnalyticsService

        model_pricing = AnalyticsService.MODEL_PRICING.get(
            model, AnalyticsService.MODEL_PRICING["gemini-2.5-flash"]
        )
        prompt_cost = (prompt_tokens / 1_000_000) * model_pricing["prompt"]
        response_cost = (response_tokens / 1_000_000) * model_pricing["response"]
        total_cost = prompt_cost + response_cost

        # Update local metrics
        self.execution_metrics["total_tokens"] += prompt_tokens + response_tokens
        self.execution_metrics["total_cost"] += total_cost

        if agent_name not in self.execution_metrics["agent_metrics"]:
            self.execution_metrics["agent_metrics"][agent_name] = {
                "executions": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "total_time": 0.0,
                "errors": 0,
            }
        agent_m = self.execution_metrics["agent_metrics"][agent_name]
        agent_m["executions"] += 1
        agent_m["total_tokens"] += prompt_tokens + response_tokens
        agent_m["total_cost"] += total_cost
        agent_m["total_time"] += execution_time
        if not success:
            agent_m["errors"] += 1

        # Return metrics for compatibility
        return {
            "execution_id": self.execution_id,
            "agent_name": agent_name,
            "total_tokens": prompt_tokens + response_tokens,
            "total_cost": total_cost,
            "execution_time_seconds": execution_time,
            "success": success,
        }

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get execution summary (compatible with AnalyticsService)."""
        return {
            "execution_id": self.execution_id,
            "account_id": self.account_id,
            "total_tokens": self.execution_metrics["total_tokens"],
            "total_cost": self.execution_metrics["total_cost"],
            "agent_metrics": self.execution_metrics["agent_metrics"],
            "queue_status": self.queue.get_queue_status(),
        }

    def cleanup_old_metrics(self, retention_days: int = 90):
        """Stub for compatibility - cleanup happens server-side."""
        logger.info(f"Cleanup requested for {retention_days} days retention")

    def aggregate_daily_costs(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        """Stub for compatibility - aggregation happens server-side."""
        return {"message": "Aggregation happens asynchronously"}

    def shutdown(self):
        """Shutdown the async queue."""
        self.queue.shutdown()
