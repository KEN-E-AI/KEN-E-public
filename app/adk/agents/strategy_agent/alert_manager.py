"""Alert Manager for monitoring token limits and triggering notifications.

This module provides real-time alerting capabilities for token usage,
with configurable thresholds and multiple notification channels.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1 import FieldFilter

from .retry_utils import with_write_retry, with_read_retry
from .token_utils import TokenEstimator

# Optional import for webhook support
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Supported alert notification channels."""
    LOGGING = "logging"
    EMAIL = "email"
    WEBHOOK = "webhook"
    FIRESTORE = "firestore"


class AlertThreshold:
    """Configuration for alert thresholds."""
    
    def __init__(
        self,
        percentage: float,
        severity: AlertSeverity,
        channels: List[AlertChannel],
        message_template: Optional[str] = None
    ):
        """Initialize alert threshold.
        
        Args:
            percentage: Threshold percentage (0-100)
            severity: Alert severity level
            channels: Notification channels to use
            message_template: Optional message template
        """
        self.percentage = percentage
        self.severity = severity
        self.channels = channels
        self.message_template = message_template or (
            "Token usage at {percentage:.1f}% of limit "
            "({tokens:,} / {limit:,} tokens)"
        )


class AlertManager:
    """Manager for token limit alerts and notifications."""
    
    # Default alert thresholds
    DEFAULT_THRESHOLDS = [
        AlertThreshold(50, AlertSeverity.INFO, [AlertChannel.LOGGING]),
        AlertThreshold(75, AlertSeverity.WARNING, [AlertChannel.LOGGING, AlertChannel.FIRESTORE]),
        AlertThreshold(90, AlertSeverity.ERROR, [AlertChannel.LOGGING, AlertChannel.FIRESTORE, AlertChannel.WEBHOOK]),
        AlertThreshold(95, AlertSeverity.CRITICAL, [AlertChannel.LOGGING, AlertChannel.FIRESTORE, AlertChannel.WEBHOOK, AlertChannel.EMAIL])
    ]
    
    def __init__(self, account_id: str, project_id: Optional[str] = None):
        """Initialize Alert Manager.
        
        Args:
            account_id: Account identifier
            project_id: Optional GCP project ID
        """
        self.account_id = account_id
        self.project_id = project_id
        
        # Initialize Firestore client for default database
        self._init_firestore_client()
        
        # Load alert configuration
        self.config = self._load_configuration()
        
        # Track triggered alerts to avoid duplicates
        self.triggered_alerts: Dict[str, datetime] = {}
        
        # Circuit breaker state
        self.circuit_breaker_open = False
        self.circuit_breaker_threshold = 100  # Percentage to trigger circuit breaker
    
    def _init_firestore_client(self):
        """Initialize Firestore client for default database."""
        try:
            self.db = firestore.Client(project=self.project_id)
            logger.info(f"Initialized alert manager for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore client: {e}")
            self.db = None
    
    def _load_configuration(self) -> Dict[str, Any]:
        """Load alert configuration from Firestore.
        
        Returns:
            Alert configuration dictionary
        """
        if not self.db:
            return self._get_default_config()
        
        try:
            # Load from alert_configurations collection
            doc = self.db.collection("alert_configurations").document(self.account_id).get()
            
            if doc.exists:
                config = doc.to_dict()
                logger.info(f"Loaded alert configuration for account {self.account_id}")
                return config
            else:
                # Create default configuration
                config = self._get_default_config()
                self._save_configuration(config)
                return config
                
        except Exception as e:
            logger.error(f"Failed to load alert configuration: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default alert configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "account_id": self.account_id,
            "enabled": True,
            "thresholds": [
                {
                    "percentage": t.percentage,
                    "severity": t.severity.value,
                    "channels": [c.value for c in t.channels]
                }
                for t in self.DEFAULT_THRESHOLDS
            ],
            "notification_channels": {
                "email": {
                    "enabled": False,
                    "recipients": []
                },
                "webhook": {
                    "enabled": False,
                    "url": None,
                    "headers": {}
                }
            },
            "cooldown_minutes": 15,  # Avoid duplicate alerts within this period
            "circuit_breaker_enabled": True,
            "circuit_breaker_threshold": 100
        }
    
    def _save_configuration(self, config: Dict[str, Any]):
        """Save alert configuration to Firestore.
        
        Args:
            config: Configuration to save
        """
        if not self.db:
            return
        
        try:
            self.db.collection("alert_configurations").document(self.account_id).set(config)
            logger.info(f"Saved alert configuration for account {self.account_id}")
        except Exception as e:
            logger.error(f"Failed to save alert configuration: {e}")
    
    def check_token_usage(
        self,
        current_tokens: int,
        max_tokens: int,
        context: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Check token usage against alert thresholds.
        
        Args:
            current_tokens: Current token count
            max_tokens: Maximum allowed tokens
            context: Optional context for the check
            agent_name: Optional agent name
            
        Returns:
            List of triggered alerts
        """
        if not self.config.get("enabled", True):
            return []
        
        percentage = (current_tokens / max_tokens) * 100
        triggered = []
        
        # Check circuit breaker first
        circuit_alert = self._check_circuit_breaker(
            percentage, current_tokens, max_tokens, context, agent_name
        )
        if circuit_alert:
            triggered.append(circuit_alert)
            return triggered  # Exit early if circuit breaker triggered
        
        # Check normal thresholds
        for threshold_config in self.config.get("thresholds", []):
            if self._should_trigger_alert(percentage, threshold_config, context):
                alert = self._create_and_send_threshold_alert(
                    threshold_config, percentage, current_tokens, 
                    max_tokens, context, agent_name
                )
                triggered.append(alert)
        
        return triggered
    
    def _check_circuit_breaker(
        self,
        percentage: float,
        current_tokens: int,
        max_tokens: int,
        context: Optional[str],
        agent_name: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Check if circuit breaker should be triggered.
        
        Args:
            percentage: Usage percentage
            current_tokens: Current token count
            max_tokens: Maximum tokens
            context: Optional context
            agent_name: Optional agent name
            
        Returns:
            Circuit breaker alert if triggered, None otherwise
        """
        if percentage >= self.config.get("circuit_breaker_threshold", 100):
            self.circuit_breaker_open = True
            logger.critical(f"Circuit breaker triggered at {percentage:.1f}% token usage")
            
            alert = self._create_alert(
                AlertSeverity.CRITICAL,
                percentage,
                current_tokens,
                max_tokens,
                "CIRCUIT BREAKER: Token limit exceeded. Operations halted.",
                context,
                agent_name
            )
            
            self._send_alert(
                alert, 
                [AlertChannel.LOGGING, AlertChannel.FIRESTORE, 
                 AlertChannel.WEBHOOK, AlertChannel.EMAIL]
            )
            
            return alert
        
        return None
    
    def _should_trigger_alert(
        self,
        percentage: float,
        threshold_config: Dict[str, Any],
        context: Optional[str]
    ) -> bool:
        """Check if alert should be triggered based on threshold and cooldown.
        
        Args:
            percentage: Current usage percentage
            threshold_config: Threshold configuration
            context: Optional context
            
        Returns:
            True if alert should be triggered
        """
        threshold_pct = threshold_config["percentage"]
        
        if percentage < threshold_pct:
            return False
        
        # Check cooldown
        if self._is_in_cooldown(threshold_pct, context):
            return False
        
        return True
    
    def _is_in_cooldown(
        self,
        threshold_pct: float,
        context: Optional[str]
    ) -> bool:
        """Check if alert is in cooldown period.
        
        Args:
            threshold_pct: Threshold percentage
            context: Optional context
            
        Returns:
            True if in cooldown period
        """
        alert_key = f"{self.account_id}:{threshold_pct}:{context or 'global'}"
        cooldown_minutes = self.config.get("cooldown_minutes", 15)
        
        if alert_key not in self.triggered_alerts:
            return False
        
        last_triggered = self.triggered_alerts[alert_key]
        time_since = (datetime.now(timezone.utc) - last_triggered).total_seconds() / 60
        
        return time_since < cooldown_minutes
    
    def _create_and_send_threshold_alert(
        self,
        threshold_config: Dict[str, Any],
        percentage: float,
        current_tokens: int,
        max_tokens: int,
        context: Optional[str],
        agent_name: Optional[str]
    ) -> Dict[str, Any]:
        """Create and send alert for threshold breach.
        
        Args:
            threshold_config: Threshold configuration
            percentage: Usage percentage
            current_tokens: Current token count
            max_tokens: Maximum tokens
            context: Optional context
            agent_name: Optional agent name
            
        Returns:
            Created alert dictionary
        """
        severity = AlertSeverity(threshold_config["severity"])
        channels = [AlertChannel(c) for c in threshold_config["channels"]]
        
        alert = self._create_alert(
            severity,
            percentage,
            current_tokens,
            max_tokens,
            None,
            context,
            agent_name
        )
        
        self._send_alert(alert, channels)
        
        # Record triggered alert
        alert_key = f"{self.account_id}:{threshold_config['percentage']}:{context or 'global'}"
        self.triggered_alerts[alert_key] = datetime.now(timezone.utc)
        
        return alert
    
    def _create_alert(
        self,
        severity: AlertSeverity,
        percentage: float,
        current_tokens: int,
        max_tokens: int,
        message: Optional[str],
        context: Optional[str],
        agent_name: Optional[str]
    ) -> Dict[str, Any]:
        """Create alert dictionary.
        
        Args:
            severity: Alert severity
            percentage: Usage percentage
            current_tokens: Current token count
            max_tokens: Maximum tokens
            message: Optional custom message
            context: Optional context
            agent_name: Optional agent name
            
        Returns:
            Alert dictionary
        """
        if not message:
            message = f"Token usage at {percentage:.1f}% of limit ({current_tokens:,} / {max_tokens:,} tokens)"
        
        alert = {
            "alert_id": str(uuid4()),
            "account_id": self.account_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": severity.value,
            "percentage": percentage,
            "current_tokens": current_tokens,
            "max_tokens": max_tokens,
            "message": message,
            "context": context,
            "agent_name": agent_name,
            "circuit_breaker_open": self.circuit_breaker_open
        }
        
        return alert
    
    def _send_alert(self, alert: Dict[str, Any], channels: List[AlertChannel]):
        """Send alert through specified channels.
        
        Args:
            alert: Alert to send
            channels: Channels to send through
        """
        for channel in channels:
            try:
                if channel == AlertChannel.LOGGING:
                    self._send_logging_alert(alert)
                elif channel == AlertChannel.FIRESTORE:
                    self._send_firestore_alert(alert)
                elif channel == AlertChannel.WEBHOOK:
                    self._send_webhook_alert(alert)
                elif channel == AlertChannel.EMAIL:
                    self._send_email_alert(alert)
            except Exception as e:
                logger.error(f"Failed to send alert via {channel.value}: {e}")
    
    def _send_logging_alert(self, alert: Dict[str, Any]):
        """Send alert via logging.
        
        Args:
            alert: Alert to send
        """
        severity = alert["severity"]
        message = alert["message"]
        
        if severity == AlertSeverity.CRITICAL.value:
            logger.critical(f"[ALERT] {message}")
        elif severity == AlertSeverity.ERROR.value:
            logger.error(f"[ALERT] {message}")
        elif severity == AlertSeverity.WARNING.value:
            logger.warning(f"[ALERT] {message}")
        else:
            logger.info(f"[ALERT] {message}")
    
    @with_write_retry(operation_name="send_firestore_alert")
    def _send_firestore_alert(self, alert: Dict[str, Any]):
        """Store alert in Firestore.
        
        Args:
            alert: Alert to store
        """
        if not self.db:
            return
        
        try:
            # Store in alerts subcollection
            self.db.collection("alert_configurations").document(
                self.account_id
            ).collection("alerts").add(alert)
        except Exception as e:
            logger.error(f"Failed to store alert in Firestore: {e}")
    
    def _send_email_alert(self, alert: Dict[str, Any]):
        """Send alert via email.
        
        This is a stub implementation that serves as an extension point for email
        notifications. To implement email alerts, you can:
        
        1. Use a service like SendGrid, AWS SES, or Google Cloud Email API
        2. Integrate with your existing email infrastructure
        3. Use SMTP directly (though this requires credentials management)
        
        Example implementation with SendGrid:
        ```python
        import sendgrid
        from sendgrid.helpers.mail import Mail
        
        sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))
        message = Mail(
            from_email='alerts@yourcompany.com',
            to_emails=email_config.get('recipients', []),
            subject=f'[{alert["severity"]}] Token Usage Alert',
            html_content=self._format_email_body(alert)
        )
        response = sg.send(message)
        ```
        
        Example implementation with AWS SES:
        ```python
        import boto3
        
        ses = boto3.client('ses', region_name='us-east-1')
        ses.send_email(
            Source='alerts@yourcompany.com',
            Destination={'ToAddresses': email_config.get('recipients', [])},
            Message={
                'Subject': {'Data': f'[{alert["severity"]}] Token Usage Alert'},
                'Body': {'Html': {'Data': self._format_email_body(alert)}}
            }
        )
        ```
        
        Args:
            alert: Alert to send via email
        """
        email_config = self.config.get("notification_channels", {}).get("email", {})
        
        if not email_config.get("enabled"):
            return
        
        recipients = email_config.get("recipients", [])
        if not recipients:
            logger.warning("Email alerts enabled but no recipients configured")
            return
        
        # Log the alert that would be sent
        logger.info(
            f"Email alert (stub): Would send {alert['severity']} alert to {recipients}. "
            f"Message: {alert['message']}"
        )
        
        # TODO: Implement actual email sending based on your infrastructure
        # See examples in the docstring above
    
    def _send_webhook_alert(self, alert: Dict[str, Any]):
        """Send alert via webhook.
        
        Args:
            alert: Alert to send
        """
        webhook_config = self.config.get("notification_channels", {}).get("webhook", {})
        
        if not webhook_config.get("enabled") or not webhook_config.get("url"):
            return
        
        if not HAS_REQUESTS:
            logger.warning("Webhook alerts require 'requests' package to be installed")
            return
        
        try:
            response = requests.post(
                webhook_config["url"],
                json=alert,
                headers=webhook_config.get("headers", {}),
                timeout=10
            )
            response.raise_for_status()
            
            logger.info(f"Sent webhook alert to {webhook_config['url']}")
            
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def check_circuit_breaker(self) -> bool:
        """Check if circuit breaker is open.
        
        Returns:
            True if circuit breaker is open (operations should halt)
        """
        return self.circuit_breaker_open
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self.circuit_breaker_open = False
        logger.info("Circuit breaker reset")
    
    def update_configuration(
        self,
        thresholds: Optional[List[Dict[str, Any]]] = None,
        notification_channels: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None
    ):
        """Update alert configuration.
        
        Args:
            thresholds: New threshold configurations
            notification_channels: New notification channel settings
            enabled: Whether alerts are enabled
        """
        if thresholds is not None:
            self.config["thresholds"] = thresholds
        
        if notification_channels is not None:
            self.config["notification_channels"] = notification_channels
        
        if enabled is not None:
            self.config["enabled"] = enabled
        
        self._save_configuration(self.config)
        logger.info(f"Updated alert configuration for account {self.account_id}")
    
    @with_read_retry(operation_name="get_recent_alerts")
    def get_recent_alerts(
        self,
        hours: int = 24,
        severity_filter: Optional[AlertSeverity] = None
    ) -> List[Dict[str, Any]]:
        """Get recent alerts from Firestore.
        
        Args:
            hours: Hours to look back
            severity_filter: Optional severity filter
            
        Returns:
            List of recent alerts
        """
        if not self.db:
            return []
        
        try:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            query = self.db.collection("alert_configurations").document(
                self.account_id
            ).collection("alerts").where(
                filter=FieldFilter("timestamp", ">=", cutoff_time.isoformat())
            )
            
            if severity_filter:
                query = query.where(
                    filter=FieldFilter("severity", "==", severity_filter.value)
                )
            
            alerts = []
            for doc in query.stream():
                alerts.append(doc.to_dict())
            
            return sorted(alerts, key=lambda x: x["timestamp"], reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to get recent alerts: {e}")
            return []