"""
order_validation_worker.py
--------------------------
Worker for node_id: "validate_order"

Simulates: Validating the incoming order — checks schema, customer account,
and product existence. Always passes (0% failure rate).

Delay: 1.0s
Failure: 0%
"""
import time
import uuid
from datetime import datetime, timezone

from base_worker import register, run, log


@register("validate_order")
def handle_order_validation(payload: dict) -> dict:
    ctx      = payload.get("global_context", {})
    order_id = ctx.get("order_id", f"ORD-{uuid.uuid4().hex[:6].upper()}")
    customer = ctx.get("customer_id", "CUST-UNKNOWN")
    product  = ctx.get("product_id",  "PROD-UNKNOWN")

    log.info(f"  [VALIDATION] Validating order={order_id} customer={customer} product={product}")
    time.sleep(1.0)

    log.info(f"  [VALIDATION] All checks passed for order={order_id}")
    return {
        "validation_status": "PASSED",
        "order_id":          order_id,
        "customer_id":       customer,
        "product_id":        product,
        "validated_at":      datetime.now(timezone.utc).isoformat(),
        "checks_passed": [
            "schema_valid",
            "customer_account_active",
            "product_exists_in_catalog",
        ],
    }


if __name__ == "__main__":
    run()
