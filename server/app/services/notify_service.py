"""Push notification service (FCM mock / stub)."""

import logging
from typing import Dict, Any

logger = logging.getLogger("nonap.notify")


async def send_push_notification(
    driver_id: str,
    title: str,
    body: str,
    data: Dict[str, Any] | None = None,
) -> bool:
    """Mock push notification sender.

    In production, this would send an FCM / APNs notification to the registered
    device token for `driver_id`. For our local setup, we log it and deliver
    via active WebSocket.
    """
    logger.info(f"[NOTIFY MOCK] To: driver_id={driver_id} | Title: {title} | Body: {body} | Data: {data}")
    return True
