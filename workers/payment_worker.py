"""
payment_worker.py
-----------------
Worker for node_id: "charge_payment"

Simulates: Charging the customer via a payment gateway.
Intentionally has a 10% failure rate to demonstrate the retry mechanism
in the orchestrator (the 10% rate makes a failure very likely during demo).

Delay:   2.0s
Failure: 10% (raises Exception → triggers task-failed callback)
"""
import random
import time
import uuid
from datetime import datetime, timezone

from base_worker import register, run, log

# Failure rate — increase to 0.9 for guaranteed demo of retry behaviour
FAILURE_RATE = float(0.10)


@register("charge_payment")
def handle_payment(payload: dict) -> dict:
    ctx      = payload.get("global_context", {})
    order_id = ctx.get("order_id",     "ORD-UNKNOWN")
    amount   = ctx.get("total_amount", 0.0)
    currency = ctx.get("currency",     "USD")
    customer = ctx.get("customer_id",  "CUST-UNKNOWN")

    log.info(f"  [PAYMENT] Charging {currency} {amount} for order={order_id} customer={customer}")
    time.sleep(2.0)

    # Simulate payment gateway failure
    if random.random() < FAILURE_RATE:
        raise Exception(
            f"Payment gateway timeout: Could not process {currency} {amount} "
            f"for order {order_id}. Stripe error: connection reset."
        )

    txn_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
    log.info(f"  [PAYMENT] Captured! txn_id={txn_id} amount={currency} {amount}")
    return {
        "transaction_id":   txn_id,
        "payment_status":   "CAPTURED",
        "order_id":         order_id,
        "amount_charged":   amount,
        "currency":         currency,
        "customer_id":      customer,
        "processed_at":     datetime.now(timezone.utc).isoformat(),
        "gateway":          "MockStripe",
    }


if __name__ == "__main__":
    run()
