"""
order_service.py
----------------
Microservice 2: Order Service
Runs on: http://localhost:8002

Endpoints:
  POST /orders/create  → {"customer_id": "cust_99", "product_id": "prod_123"}
  POST /orders/update  → {"order_id": "ord_555", "status": "COMPLETED"}

The Orchestrator:
  → Sends customer_id + product_id to /create
  ← Gets back order_id + status
  → Sends order_id + new status to /update
  ← Gets back success + updated_at

Wraps OrderDBWorker + StatusUpdateWorker logic into HTTP endpoints.
No Redis needed for this HTTP mode.
"""

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("OrderService")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Order Service",
    description="Creates and updates orders. Part of the Workflow Orchestrator system.",
    version="1.0.0",
)

# ── In-memory orders database ─────────────────────────────────────────────────
# In production: PostgreSQL with SQLAlchemy or asyncpg
ORDERS_DB: dict[str, dict] = {}

# ── Valid status transitions (state machine — from status_update_worker.py) ───
VALID_TRANSITIONS: dict[Optional[str], list[str]] = {
    None:         ["PENDING", "CONFIRMED"],
    "PENDING":    ["CONFIRMED", "CANCELLED", "FAILED"],
    "CONFIRMED":  ["PROCESSING", "CANCELLED"],
    "PROCESSING": ["SHIPPED", "FAILED", "CANCELLED"],
    "SHIPPED":    ["DELIVERED", "RETURNED"],
    "DELIVERED":  ["RETURNED"],
    "FAILED":     ["PENDING"],
    "CANCELLED":  [],
    "RETURNED":   [],
    # Allow COMPLETED as an alias for DELIVERED (spec uses it)
    "COMPLETED":  ["RETURNED"],
}

# Add COMPLETED as a valid target from PROCESSING/SHIPPED
VALID_TRANSITIONS["PROCESSING"].append("COMPLETED")
VALID_TRANSITIONS["SHIPPED"].append("COMPLETED")


# ── Request / Response Models ─────────────────────────────────────────────────

class CreateOrderRequest(BaseModel):
    customer_id:    str = Field(..., description="Customer identifier", example="cust_99")
    product_id:     str = Field(..., description="Product being ordered", example="prod_123")
    quantity:       int = Field(1, description="Number of units", ge=1)
    customer_email: str = Field("", description="Customer email (optional)")
    total_amount:   float = Field(0.0, description="Total price (optional)")
    currency:       str = Field("USD", description="Currency code")
    vendor_id:      str = Field("VENDOR-DEFAULT", description="Vendor/supplier ID")

    class Config:
        json_schema_extra = {
            "example": {
                "customer_id":    "cust_99",
                "product_id":     "prod_123",
                "quantity":       2,
                "customer_email": "user@example.com",
                "total_amount":   59.98,
                "currency":       "USD",
            }
        }


class UpdateOrderRequest(BaseModel):
    order_id: str = Field(..., description="Order ID to update", example="ord_555")
    status:   str = Field(..., description="New status to set", example="COMPLETED")
    metadata: dict = Field({}, description="Optional extra info (e.g. tracking number)")

    class Config:
        json_schema_extra = {
            "example": {
                "order_id": "ord_555",
                "status":   "COMPLETED",
            }
        }


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"service": "OrderService", "status": "running", "port": 8002}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ── Endpoint 1: Create Order ──────────────────────────────────────────────────
@app.post("/orders/create", tags=["Orders"], status_code=201)
def create_order(body: CreateOrderRequest):
    """
    Create a new order record.

    Called by the Orchestrator with customer_id + product_id.
    Returns order_id + status for the Orchestrator to use in downstream steps.

    Diagram flow: Orchestrator → (customer_id, product_id) → Order Service
                  Order Service → (order_id, status) → Orchestrator
    """
    logger.info(f"💾 Creating order: customer={body.customer_id}, product={body.product_id}")

    # ── Generate IDs ──────────────────────────────────────────────────────────
    order_id          = f"ord_{uuid.uuid4().hex[:8]}"
    confirmation_code = f"CONF-{uuid.uuid4().hex[:6].upper()}"
    created_at        = datetime.now(timezone.utc).isoformat()

    # ── Build order record ────────────────────────────────────────────────────
    order = {
        "order_id":          order_id,
        "customer_id":       body.customer_id,
        "customer_email":    body.customer_email,
        "product_id":        body.product_id,
        "quantity":          body.quantity,
        "total_amount":      body.total_amount,
        "currency":          body.currency,
        "vendor_id":         body.vendor_id,
        "confirmation_code": confirmation_code,
        "status":            "CONFIRMED",
        "created_at":        created_at,
        "updated_at":        created_at,
        "status_history": [
            {"status": "CONFIRMED", "changed_at": created_at, "metadata": {}}
        ],
    }

    # ── Save to mock DB ───────────────────────────────────────────────────────
    ORDERS_DB[order_id] = order
    logger.info(f"  ✅ Order created: {order_id} | conf={confirmation_code}")

    # ── Return (matches diagram: order_id, status) ────────────────────────────
    return {
        "order_id":          order_id,
        "status":            "CONFIRMED",
        "confirmation_code": confirmation_code,
        "customer_id":       body.customer_id,
        "product_id":        body.product_id,
        "quantity":          body.quantity,
        "created_at":        created_at,
        "message":           "Order created and confirmed successfully.",
    }


# ── Endpoint 2: Update Order Status ──────────────────────────────────────────
@app.post("/orders/update", tags=["Orders"])
def update_order(body: UpdateOrderRequest):
    """
    Update the status of an existing order.

    Called by the Orchestrator to advance an order through its lifecycle.
    Enforces valid state transitions (e.g. CONFIRMED → PROCESSING is ok,
    DELIVERED → PENDING is not).

    Diagram flow: Orchestrator → (order_id, status) → Order Service
                  Order Service → (success, updated_at) → Orchestrator
    """
    logger.info(f"📋 Updating order {body.order_id} → {body.status}")

    # ── Find order ────────────────────────────────────────────────────────────
    order = ORDERS_DB.get(body.order_id)
    if not order:
        raise HTTPException(
            status_code=404,
            detail={
                "error":    "ORDER_NOT_FOUND",
                "order_id": body.order_id,
                "message":  f"Order '{body.order_id}' not found. Create it first via POST /orders/create",
            },
        )

    current_status = order["status"]

    # ── Validate transition ───────────────────────────────────────────────────
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if body.status not in allowed:
        raise HTTPException(
            status_code=422,
            detail={
                "error":           "INVALID_STATUS_TRANSITION",
                "order_id":        body.order_id,
                "current_status":  current_status,
                "requested_status": body.status,
                "allowed_next":    allowed,
                "message": (
                    f"Cannot transition '{body.order_id}' from '{current_status}' to '{body.status}'. "
                    f"Allowed transitions: {allowed}"
                ),
            },
        )

    # ── Apply transition ──────────────────────────────────────────────────────
    updated_at = datetime.now(timezone.utc).isoformat()
    order["status"]     = body.status
    order["updated_at"] = updated_at
    order["status_history"].append({
        "status":     body.status,
        "changed_at": updated_at,
        "metadata":   body.metadata,
    })

    logger.info(f"  ✅ {body.order_id}: {current_status} → {body.status}")

    # ── Return (matches diagram: success, updated_at) ─────────────────────────
    return {
        "success":          True,
        "order_id":         body.order_id,
        "previous_status":  current_status,
        "new_status":       body.status,
        "updated_at":       updated_at,
        "message":          f"Order status updated: {current_status} → {body.status}",
    }


# ── Admin: get single order ───────────────────────────────────────────────────
@app.get("/orders/{order_id}", tags=["Admin"])
def get_order(order_id: str):
    """Fetch a single order record by ID (useful for debugging)."""
    order = ORDERS_DB.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail={"error": "ORDER_NOT_FOUND"})
    return order


@app.get("/orders", tags=["Admin"])
def list_orders():
    """List all orders in the mock DB (useful for debugging)."""
    return {"total": len(ORDERS_DB), "orders": list(ORDERS_DB.values())}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("ORDER_PORT", 8002))
    logger.info(f"🚀 Starting Order Service on port {port}")
    uvicorn.run("order_service:app", host="0.0.0.0", port=port, reload=True)
