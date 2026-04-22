"""
shipping_worker.py
------------------
Worker for node_id: "prepare_shipping"

Simulates: Creating a shipment record in the courier system, assigning
a tracking number, and scheduling pickup.

Delay:   2.0s
Failure: 0%
"""
import time
import uuid
import random
from datetime import datetime, timezone, timedelta

from base_worker import register, run, log

CARRIERS = ["MockDHL", "MockFedEx", "MockUPS", "MockBlueDart"]


@register("prepare_shipping")
def handle_shipping(payload: dict) -> dict:
    ctx        = payload.get("global_context", {})
    order_id   = ctx.get("order_id",   "ORD-UNKNOWN")
    customer   = ctx.get("customer_id","CUST-UNKNOWN")
    product_id = ctx.get("product_id", "PROD-UNKNOWN")
    quantity   = ctx.get("quantity",   1)

    carrier    = random.choice(CARRIERS)
    eta_days   = random.randint(2, 5)
    eta_date   = (datetime.now(timezone.utc) + timedelta(days=eta_days)).date().isoformat()

    log.info(f"  [SHIPPING] Creating shipment for order={order_id} via {carrier}")
    time.sleep(2.0)

    tracking_id = f"SHIP-{uuid.uuid4().hex[:10].upper()}"
    log.info(f"  [SHIPPING] Shipment created! tracking_id={tracking_id} ETA={eta_date}")
    return {
        "tracking_id":      tracking_id,
        "order_id":         order_id,
        "customer_id":      customer,
        "product_id":       product_id,
        "quantity":         quantity,
        "carrier":          carrier,
        "eta_days":         eta_days,
        "estimated_date":   eta_date,
        "status":           "PICKUP_SCHEDULED",
        "dispatched_at":    datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    run()
