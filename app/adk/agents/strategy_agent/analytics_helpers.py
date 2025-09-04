"""Helper functions for analytics integration in the orchestrator.

This module contains extracted functions to reduce complexity in the main orchestrator.
"""

import logging
import time
from typing import Optional, Tuple, Any

from .analytics_service import AnalyticsService
from .performance_profiler import PerformanceProfiler
from .alert_manager import AlertManager
from .optimization_analyzer import OptimizationAnalyzer
from .token_utils import TokenEstimator

logger = logging.getLogger(__name__)


def initialize_analytics_services(
    account_id: str,
    project_id: Optional[str],
    enable_analytics: bool = True
) -> Tuple[Optional[AnalyticsService], Optional[PerformanceProfiler],
           Optional[AlertManager], Optional[OptimizationAnalyzer]]:
    """Initialize all analytics services for strategy generation.
    
    Args:
        account_id: Account identifier
        project_id: Optional GCP project ID
        enable_analytics: Whether to enable analytics tracking
        
    Returns:
        Tuple of (analytics_service, performance_profiler, alert_manager, optimization_analyzer)
        Returns (None, None, None, None) if analytics disabled or initialization fails
    """
    if not enable_analytics:
        logger.info("[ANALYTICS] Analytics disabled")
        return None, None, None, None
    
    try:
        analytics_service = AnalyticsService(account_id, project_id)
        performance_profiler = PerformanceProfiler(account_id, project_id)
        alert_manager = AlertManager(account_id, project_id)
        optimization_analyzer = OptimizationAnalyzer(account_id, project_id)
        
        logger.info("[ANALYTICS] Successfully initialized all analytics services")
        return analytics_service, performance_profiler, alert_manager, optimization_analyzer
        
    except Exception as e:
        logger.warning(f"[ANALYTICS] Failed to initialize analytics services: {e}")
        return None, None, None, None


def check_token_limits_before_execution(
    alert_manager: Optional[AlertManager],
    execution_input: str,
    performance_profiler: Optional[PerformanceProfiler] = None,
    main_operation: Optional[Any] = None
) -> Optional[str]:
    """Check token limits and circuit breaker before execution.
    
    Args:
        alert_manager: Alert manager instance
        execution_input: Input text to check
        performance_profiler: Optional performance profiler
        main_operation: Optional performance operation to end if aborting
        
    Returns:
        Error message if execution should be aborted, None otherwise
    """
    if not alert_manager:
        return None
    
    try:
        estimated_tokens = TokenEstimator.estimate_tokens(execution_input)
        alerts = alert_manager.check_token_usage(
            current_tokens=estimated_tokens,
            max_tokens=TokenEstimator.MAX_INPUT_TOKENS,
            context="initial_input",
            agent_name="orchestrator"
        )
        
        if alerts:
            logger.warning(f"[ALERTS] {len(alerts)} alerts triggered for initial input")
        
        # Check circuit breaker
        if alert_manager.check_circuit_breaker():
            error_msg = "Circuit breaker open - token limit exceeded. Aborting execution."
            logger.error(f"[CIRCUIT_BREAKER] {error_msg}")
            
            # End performance tracking if applicable
            if performance_profiler and main_operation:
                performance_profiler.end_operation(
                    main_operation,
                    success=False,
                    error=error_msg
                )
            
            return error_msg
            
    except Exception as e:
        logger.error(f"[ALERTS] Error checking token limits: {e}")
    
    return None


def report_execution_summary(
    analytics_service: Optional[AnalyticsService],
    performance_profiler: Optional[PerformanceProfiler],
    optimization_analyzer: Optional[OptimizationAnalyzer],
    main_operation: Optional[Any],
    execution_time: float,
    documents_generated: int
) -> None:
    """Generate and log comprehensive execution summary reports.
    
    Args:
        analytics_service: Analytics service instance
        performance_profiler: Performance profiler instance
        optimization_analyzer: Optimization analyzer instance
        main_operation: Main performance operation
        execution_time: Total execution time in seconds
        documents_generated: Number of documents generated
    """
    logger.info(
        f"[EXECUTION] Summary - Generated {documents_generated} documents in {execution_time:.2f}s"
    )
    
    # Performance profiling summary
    if performance_profiler and main_operation:
        try:
            performance_profiler.end_operation(main_operation, success=True)
            
            perf_summary = performance_profiler.get_performance_summary()
            logger.info(f"[PERFORMANCE] Operations: {perf_summary.get('total_operations', 0)}")
            logger.info(f"[PERFORMANCE] Total duration: {perf_summary.get('total_duration', 0):.2f}s")
            
            if 'slowest_agent' in perf_summary:
                slowest = perf_summary['slowest_agent']
                logger.info(
                    f"[PERFORMANCE] Slowest agent: {slowest['name']} "
                    f"({slowest['avg_duration']:.2f}s avg)"
                )
            
            # Check for bottlenecks
            bottlenecks = performance_profiler.get_bottlenecks(time_window_hours=1)
            if bottlenecks:
                logger.warning(f"[PERFORMANCE] Found {len(bottlenecks)} bottlenecks:")
                for bottleneck in bottlenecks[:3]:
                    logger.warning(
                        f"  • {bottleneck['agent_name']}: {bottleneck['duration']:.2f}s "
                        f"({bottleneck['severity']} severity)"
                    )
        except Exception as e:
            logger.error(f"[PERFORMANCE] Error generating performance summary: {e}")
    
    # Analytics cost summary
    if analytics_service:
        try:
            exec_summary = analytics_service.get_execution_summary()
            logger.info(
                f"[ANALYTICS] Total tokens: {exec_summary['total_tokens']:,}"
            )
            logger.info(
                f"[ANALYTICS] Total cost: ${exec_summary['total_cost']:.4f}"
            )
            
            # Cost per document
            if documents_generated > 0:
                cost_per_doc = exec_summary['total_cost'] / documents_generated
                logger.info(f"[ANALYTICS] Cost per document: ${cost_per_doc:.4f}")
            
            # Aggregate daily costs
            analytics_service.aggregate_daily_costs()
            
        except Exception as e:
            logger.error(f"[ANALYTICS] Error generating analytics summary: {e}")
    
    # Optimization recommendations
    if optimization_analyzer:
        try:
            recommendations = optimization_analyzer.generate_recommendations()
            if recommendations:
                logger.info(
                    f"[OPTIMIZATION] Generated {len(recommendations)} recommendations:"
                )
                for rec in recommendations[:3]:
                    logger.info(
                        f"  • {rec.description} "
                        f"(Priority: {rec.priority}, Savings: {rec.estimated_savings_percentage:.1f}%)"
                    )
            else:
                logger.info("[OPTIMIZATION] No optimization recommendations at this time")
                
        except Exception as e:
            logger.error(f"[OPTIMIZATION] Error generating recommendations: {e}")