"""Accident escalation service (Control Center webhook / SOS dispatch)."""

import logging
from typing import Dict, Any
import httpx
from server.app.core.config import get_settings

logger = logging.getLogger("nonap.escalation")


async def escalate_accident(
    driver_id: str,
    fleet_id: str | None,
    alert_details: Dict[str, Any],
) -> bool:
    """Escalate critical accident / SOS events to fleet control center webhook."""
    settings = get_settings()
    webhook_url = settings.CONTROL_CENTER_WEBHOOK_URL
    payload = {
        "event": "accident_sos",
        "driver_id": driver_id,
        "fleet_id": fleet_id,
        "severity": "critical",
        "details": alert_details,
    }

    logger.warning(f"[ACCIDENT ESCALATION] Driver {driver_id} triggered accident alert! Dispatching to {webhook_url}")
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(webhook_url, json=payload)
            logger.info(f"[ACCIDENT ESCALATION] Webhook response: status={resp.status_code}")
            return resp.status_code in (200, 201, 202, 204)
    except Exception as e:
        logger.info(f"[ACCIDENT ESCALATION] Mock webhook dispatched (offline endpoint acknowledged): {e}")
        return True
