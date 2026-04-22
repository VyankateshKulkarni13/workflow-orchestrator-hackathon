"""
inventory_worker.py
-------------------
Worker for node_id: "update_inventory"

Simulates: Reserving stock for the confirmed order in the warehouse system.
Updates inventory counts and generates a reservation ID.

Delay:   1.5s
Failure: 0%
"""
import time
import uuid
from datetime import datetime, timezone

from base_worker import register, run, log


@register("update_inventory")
def handle_inventory(payload: dict) -> dict:
    ctx        = payload.get("global_context", {})
    order_id   = ctx.get("order_id",   "ORD-UNKNOWN")
    product_id = ctx.get("product_id", "PROD-UNKNOWN")
    quantity   = ctx.get("quantity",   1)
    warehouse  = ctx.get("warehouse",  "WH-CENTRAL")

    log.info(f"  [INVENTORY] Reserving {quantity}x {product_id} for order={order_id}")
    time.sleep(1.5)

    reservation_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    log.info(f"  [INVENTORY] Reserved! reservation_id={reservation_id}")
    return {
        "reservation_id":    reservation_id,
        "inventory_reserved": True,
        "order_id":          order_id,
        "product_id":        product_id,
        "quantity_reserved": quantity,
        "warehouse":         warehouse,
        "reserved_at":       datetime.now(timezone.utc).isoformat(),
    }


if __name__ == "__main__":
    run()
