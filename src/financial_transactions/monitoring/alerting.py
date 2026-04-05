"""Alerting module for drift, performance, and retraining notifications."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import requests
from loguru import logger


class AlertManager:
    """Send alerts for drift, performance degradation, and retraining events.

    Supports webhook-based alerts (Slack, Teams) and Delta audit logging.

    Usage:
        alerter = AlertManager(webhook_url="https://hooks.slack.com/...")
        alerter.send_drift_alert(drift_report)
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        spark: Any | None = None,
        audit_table: str | None = None,
    ) -> None:
        self.webhook_url = webhook_url
        self.spark = spark
        self.audit_table = audit_table

    def send_drift_alert(self, drift_report: dict[str, Any]) -> None:
        """Send alert when data drift is detected."""
        drifted = drift_report.get("drifted_features", [])
        message = (
            f"⚠️ *Data Drift Detected*\n"
            f"• Drifted features: {', '.join(drifted)}\n"
            f"• Reference size: {drift_report.get('reference_size', 'N/A')}\n"
            f"• Current size: {drift_report.get('current_size', 'N/A')}\n"
            f"• Time: {drift_report.get('timestamp', 'N/A')}"
        )
        self._send(message, "drift_alert", drift_report)

    def send_performance_alert(self, metrics: dict[str, float], threshold: str = "") -> None:
        """Send alert when model performance degrades."""
        message = (
            f"🔴 *Model Performance Degradation*\n"
            f"• Metrics: {json.dumps(metrics, indent=2)}\n"
            f"• Threshold: {threshold}\n"
            f"• Time: {datetime.now(tz=UTC).isoformat()}"
        )
        self._send(message, "performance_alert", metrics)

    def send_retraining_notification(self, reason: str, model_type: str = "") -> None:
        """Send notification when retraining is triggered."""
        message = (
            f"🔄 *Retraining Triggered*\n"
            f"• Reason: {reason}\n"
            f"• Model: {model_type}\n"
            f"• Time: {datetime.now(tz=UTC).isoformat()}"
        )
        self._send(message, "retraining_trigger", {"reason": reason, "model_type": model_type})

    def send_deployment_notification(self, version: str, model_type: str, decision: str) -> None:
        """Send notification for deployment events."""
        icon = "✅" if decision == "PROMOTE" else "❌"
        message = (
            f"{icon} *Deployment Decision: {decision}*\n"
            f"• Model: {model_type} v{version}\n"
            f"• Time: {datetime.now(tz=UTC).isoformat()}"
        )
        self._send(message, "deployment", {"version": version, "model_type": model_type, "decision": decision})

    def _send(self, message: str, alert_type: str, data: Any = None) -> None:
        """Send alert via webhook and/or log to Delta."""
        logger.info(f"Alert [{alert_type}]: {message[:200]}")

        if self.webhook_url:
            try:
                payload = {"text": message}
                requests.post(self.webhook_url, json=payload, timeout=10)
            except Exception:
                logger.warning(f"Failed to send webhook alert for {alert_type}")

        if self.spark and self.audit_table:
            self._log_to_delta(alert_type, message, data)

    def _log_to_delta(self, alert_type: str, message: str, data: Any) -> None:
        """Log alert to Delta audit table."""
        from pyspark.sql import Row

        row = Row(
            timestamp=datetime.now(tz=UTC).isoformat(),
            alert_type=alert_type,
            message=message[:500],
            data=json.dumps(data) if data else "{}",
        )
        try:
            df = self.spark.createDataFrame([row])
            df.write.format("delta").mode("append").saveAsTable(self.audit_table)
        except Exception:
            logger.warning(f"Failed to write alert to {self.audit_table}")
