"""
notification_worker.py
----------------------
Worker for node_id: "send_confirmation"

Simulates: Sending an order confirmation email to the customer after
the entire order has been processed and shipment is scheduled.

Delay:   0.5s
Failure: 0%
"""
import time
import uuid
from datetime import datetime, timezone

from base_worker import register, run, log


@register("send_confirmation")
def handle_notification(payload: dict) -> dict:
    ctx        = payload.get("global_context", {})
    order_id   = ctx.get("order_id",       "ORD-UNKNOWN")
    customer   = ctx.get("customer_id",    "CUST-UNKNOWN")
    email      = ctx.get("customer_email", f"{customer.lower()}@example.com")
    product_id = ctx.get("product_id",     "PROD-UNKNOWN")
    amount     = ctx.get("total_amount",   0.0)
    currency   = ctx.get("currency",       "USD")

    log.info(f"  [NOTIFICATION] Sending confirmation to {email} for order={order_id}")
    time.sleep(0.5)

    message_id = f"MSG-{uuid.uuid4().hex[:8].upper()}"
    log.info(f"  [NOTIFICATION] Email sent! message_id={message_id} to={email}")
    return {
        "email_sent":   True,
        "message_id":   message_id,
        "recipient":    email,
        "customer_id":  customer,
        "order_id":     order_id,
        "subject":      f"Your order {order_id} has been confirmed!",
        "body_preview": (
            f"Hi {customer}, your order for {product_id} "
            f"totalling {currency} {amount} has been confirmed "
            f"and is on its way!"
        ),
        "channel":      "email",
        "sent_at":      datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    run()
