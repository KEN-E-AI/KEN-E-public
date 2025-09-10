"""
Monitoring endpoints for Prometheus metrics collection.

This router provides endpoints for Prometheus to scrape metrics
about OAuth flows, performance, and system health.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from prometheus_client import REGISTRY, generate_latest

from ..auth.models import UserContext
from ..auth.user_context import get_current_user_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


@router.get("/metrics", response_class=PlainTextResponse)
async def get_prometheus_metrics() -> str:
    """
    Expose metrics in Prometheus format.
    
    This endpoint can be scraped by Prometheus to collect metrics about:
    - OAuth authorization attempts and success rates
    - Token refresh success/failure rates
    - OAuth flow duration percentiles
    - Encryption operation performance
    - Active OAuth sessions
    - Token expiration monitoring
    
    In production, this endpoint should be protected or exposed on a separate internal port.
    
    Returns:
        Prometheus formatted metrics as plain text.
    """
    # Log access for security auditing
    logger.info("[METRICS] Prometheus metrics endpoint accessed")
    
    try:
        # Generate metrics in Prometheus format
        metrics_output = generate_latest(REGISTRY)
        
        # Convert bytes to string if needed
        if isinstance(metrics_output, bytes):
            return metrics_output.decode('utf-8')
        return metrics_output
    
    except Exception as e:
        logger.error(f"[METRICS] Error generating Prometheus metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate metrics"
        )


@router.get("/health", response_class=PlainTextResponse)
async def monitoring_health() -> str:
    """
    Health check for monitoring service.
    
    Returns:
        Simple OK response to indicate monitoring service is running.
    """
    return "OK"


@router.get("/oauth-stats")
async def get_oauth_statistics(
    current_user: UserContext = Depends(get_current_user_context),
) -> dict:
    """
    Get human-readable OAuth statistics.
    
    This endpoint provides a JSON summary of OAuth metrics for dashboards
    and debugging purposes.
    
    Returns:
        JSON object with OAuth statistics and metrics.
    """
    # Import metrics to get current values
    from ..metrics.oauth_metrics import (
        oauth_auth_attempts,
        oauth_auth_success,
        oauth_callback_errors,
        token_refresh_success,
        token_refresh_failures,
    )
    
    try:
        # Collect current metric values
        # Note: This is a simplified version. In production, you'd want to
        # query Prometheus or use a proper metrics backend
        stats = {
            "oauth_flows": {
                "google_analytics": {
                    "total_attempts": "See /api/monitoring/metrics for raw data",
                    "success_rate": "Calculate from prometheus metrics",
                    "last_hour_attempts": "Query from time-series data",
                }
            },
            "token_refresh": {
                "google_analytics": {
                    "success_count": "See /api/monitoring/metrics",
                    "failure_count": "See /api/monitoring/metrics",
                    "success_rate": "Calculate from metrics",
                }
            },
            "performance": {
                "oauth_flow_p50": "See histogram in /api/monitoring/metrics",
                "oauth_flow_p99": "See histogram in /api/monitoring/metrics",
                "encryption_p50": "See histogram in /api/monitoring/metrics",
                "encryption_p99": "See histogram in /api/monitoring/metrics",
            },
            "alerts": {
                "oauth_success_rate_alert": "Configure in Prometheus/Grafana",
                "token_refresh_failure_alert": "Configure in Prometheus/Grafana",
                "encryption_performance_alert": "Configure in Prometheus/Grafana",
            },
            "info": "Use /api/monitoring/metrics endpoint for Prometheus scraping"
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"[METRICS] Error generating OAuth statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate OAuth statistics"
        )