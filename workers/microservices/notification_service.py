"""
notification_service.py
-----------------------
Microservice 3: Notification Service
Runs on: http://localhost:8003

Endpoint:
  POST /notifications/send
  Body: {"channel": "email", "payload": {"message": "Order confirmed!"}}

The Orchestrator sends channel + payload → this service dispatches the notification
and returns delivered (bool) + timestamp.

Diagram flow:
  Orchestrator → (channel, payload) → Notification Service
  Notification Service → (delivered, timestamp) → Orchestrator

Wraps ReceiptWorker + VendorNotifyWorker logic into one unified HTTP endpoint.
Supports channels: email, sms, webhook, push, slack, mock
"""

import os
import uuid
import random
import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("NotificationService")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Notification Service",
    description="Sends notifications via email, SMS, webhook, and more. Part of the Workflow Orchestrator.",
    version="1.0.0",
)

# ── Supported channels and their mock handlers ────────────────────────────────
SUPPORTED_CHANNELS = {"email", "sms", "webhook", "push", "slack", "mock"}

# ── Notification log (in-memory, for debugging) ───────────────────────────────
NOTIFICATION_LOG: list[dict] = []


# ── Request Model ─────────────────────────────────────────────────────────────
class SendNotificationRequest(BaseModel):
    channel: str = Field(
        ...,
        description="Delivery channel: email | sms | webhook | push | slack | mock",
        example="email",
    )
    payload: dict = Field(
        ...,
        description="Notification content. Can include: message, subject, to, order_id, etc.",
        example={"message": "Order confirmed!", "to": "user@example.com", "subject": "Your order"},
    )
    # Optional metadata
    order_id:    str = Field("", description="Order ID (optional, for logging)")
    customer_id: str = Field("", description="Customer ID (optional, for logging)")
    priority:    str = Field("normal", description="Priority: low | normal | high")

    class Config:
        json_schema_extra = {
            "example": {
                "channel": "email",
                "payload": {
                    "message": "Order confirmed!",
                    "to":      "user@example.com",
                    "subject": "Your Order Has Been Confirmed",
                },
                "order_id": "ord_abc123",
            }
        }


# ── Channel dispatch functions ────────────────────────────────────────────────

def _send_email(payload: dict) -> dict:
    """
    Simulate sending an email.
    In production: call SendGrid / AWS SES / SMTP.
    """
    to      = payload.get("to", payload.get("email", "unknown@example.com"))
    subject = payload.get("subject", "Notification")
    message = payload.get("message", "")

    # Simulate occasional failure (configurable via env)
    fail_rate = float(os.getenv("SIMULATE_EMAIL_FAIL_RATE", "0.0"))
    if fail_rate > 0 and random.random() < fail_rate:
        raise RuntimeError(f"Email API (MockSMTP) returned 503 Service Unavailable")

    msg_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"  📧 [MOCK EMAIL] To: {to} | Subject: {subject} | MsgId: {msg_id}")
    return {
        "provider":   "MockSMTP",
        "message_id": msg_id,
        "to":         to,
        "subject":    subject,
    }


def _send_sms(payload: dict) -> dict:
    """
    Simulate sending an SMS.
    In production: call Twilio / AWS SNS.
    """
    to      = payload.get("to", payload.get("phone", "unknown"))
    message = payload.get("message", "")

    fail_rate = float(os.getenv("SIMULATE_SMS_FAIL_RATE", "0.0"))
    if fail_rate > 0 and random.random() < fail_rate:
        raise RuntimeError("SMS API (MockTwilio) returned 503")

    sms_id = f"SMS-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"  📱 [MOCK SMS] To: {to} | MsgId: {sms_id}")
    return {
        "provider":   "MockTwilio",
        "message_id": sms_id,
        "to":         to,
    }


def _send_webhook(payload: dict) -> dict:
    """
    Send HTTP POST to a webhook URL.
    In production: use httpx or requests.
    """
    import json
    import urllib.request
    import urllib.error

    url = payload.get("url", payload.get("webhook_url", ""))
    if not url:
        raise ValueError("Webhook channel requires 'url' in payload")

    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            status = resp.getcode()
            logger.info(f"  🌐 Webhook sent to {url} | HTTP {status}")
            return {"url": url, "http_status": status}
    except urllib.error.URLError as e:
        raise RuntimeError(f"Webhook POST to '{url}' failed: {e.reason}")


def _send_push(payload: dict) -> dict:
    """
    Simulate push notification (Firebase / APNs).
    """
    device_token = payload.get("device_token", "unknown-device")
    message      = payload.get("message", "")
    push_id      = f"PUSH-{uuid.uuid4().hex[:8].upper()}"
    logger.info(f"  🔔 [MOCK PUSH] Device: {device_token} | PushId: {push_id}")
    return {"provider": "MockFCM", "push_id": push_id, "device_token": device_token}


def _send_slack(payload: dict) -> dict:
    """
    Simulate Slack message via webhook or bot token.
    """
    channel = payload.get("slack_channel", "#general")
    message = payload.get("message", "")
    ts      = f"SLACK-{uuid.uuid4().hex[:8]}"
    logger.info(f"  💬 [MOCK SLACK] Channel: {channel} | ts: {ts}")
    return {"channel": channel, "ts": ts}


def _send_mock(payload: dict) -> dict:
    """
    Pure mock — always succeeds. Useful for testing.
    """
    logger.info(f"  🧪 [MOCK] Notification simulated")
    return {"mock": True, "payload_received": payload}


# ── Channel router ────────────────────────────────────────────────────────────
CHANNEL_HANDLERS = {
    "email":   _send_email,
    "sms":     _send_sms,
    "webhook": _send_webhook,
    "push":    _send_push,
    "slack":   _send_slack,
    "mock":    _send_mock,
}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"service": "NotificationService", "status": "running", "port": 8003}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ── Main endpoint ─────────────────────────────────────────────────────────────
@app.post("/notifications/send", tags=["Notifications"])
def send_notification(body: SendNotificationRequest):
    """
    Send a notification via the specified channel.

    Supported channels: email | sms | webhook | push | slack | mock

    The Orchestrator calls this after a successful order to notify
    the customer (email/SMS) and log confirmation.

    Returns:
    - delivered (bool): True if successfully sent
    - timestamp (str): ISO 8601 when the notification was dispatched
    - notification_id (str): Unique ID for this notification
    - channel_response (dict): Channel-specific response data
    """
    channel = body.channel.lower().strip()
    logger.info(
        f"📣 Notification request: channel={channel} "
        f"order={body.order_id or 'N/A'} priority={body.priority}"
    )

    # ── Validate channel ──────────────────────────────────────────────────────
    if channel not in SUPPORTED_CHANNELS:
        raise HTTPException(
            status_code=400,
            detail={
                "error":              "UNSUPPORTED_CHANNEL",
                "channel":            channel,
                "supported_channels": list(SUPPORTED_CHANNELS),
                "message": (
                    f"Channel '{channel}' is not supported. "
                    f"Use one of: {', '.join(sorted(SUPPORTED_CHANNELS))}"
                ),
            },
        )

    # ── Dispatch to channel handler ───────────────────────────────────────────
    notification_id = f"NOTIF-{uuid.uuid4().hex[:10].upper()}"
    timestamp       = datetime.now(timezone.utc).isoformat()
    handler         = CHANNEL_HANDLERS[channel]

    try:
        channel_response = handler(body.payload)
    except (ValueError, RuntimeError) as e:
        # Log the failure
        logger.error(f"  ❌ Notification failed on channel={channel}: {e}")
        NOTIFICATION_LOG.append({
            "notification_id": notification_id,
            "channel":         channel,
            "order_id":        body.order_id,
            "status":          "FAILED",
            "error":           str(e),
            "timestamp":       timestamp,
        })
        raise HTTPException(
            status_code=502,
            detail={
                "error":           "NOTIFICATION_FAILED",
                "notification_id": notification_id,
                "channel":         channel,
                "delivered":       False,
                "message":         str(e),
            },
        )

    # ── Log success ───────────────────────────────────────────────────────────
    log_entry = {
        "notification_id":  notification_id,
        "channel":          channel,
        "order_id":         body.order_id,
        "customer_id":      body.customer_id,
        "status":           "DELIVERED",
        "channel_response": channel_response,
        "timestamp":        timestamp,
    }
    NOTIFICATION_LOG.append(log_entry)
    logger.info(f"  ✅ Notification delivered | id={notification_id}")

    # ── Return (matches diagram: delivered, timestamp) ────────────────────────
    return {
        "delivered":        True,
        "notification_id":  notification_id,
        "channel":          channel,
        "timestamp":        timestamp,
        "channel_response": channel_response,
        "message":          f"Notification delivered via {channel}.",
    }


# ── Admin: view notification log ──────────────────────────────────────────────
@app.get("/notifications/log", tags=["Admin"])
def get_notification_log(limit: int = 50):
    """View recent notification history (useful for debugging)."""
    recent = NOTIFICATION_LOG[-limit:]
    return {
        "total":         len(NOTIFICATION_LOG),
        "showing":       len(recent),
        "notifications": list(reversed(recent)),
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("NOTIFICATION_PORT", 8003))
    logger.info(f"🚀 Starting Notification Service on port {port}")
    uvicorn.run("notification_service:app", host="0.0.0.0", port=port, reload=True)
