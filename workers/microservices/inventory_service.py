"""
inventory_service.py
--------------------
Microservice 1: Inventory Service
Runs on: http://localhost:8001

Endpoint:
  GET /inventory/check?product_id=ITEM-001&quantity=2

The Orchestrator sends product_id + quantity → this service checks stock
and returns available + stock_left (matching the diagram arrows).

Wraps InventoryWorker business logic directly — no Redis needed for HTTP mode.
"""

import os
import logging
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("InventoryService")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Inventory Service",
    description="Checks product stock levels. Part of the Workflow Orchestrator system.",
    version="1.0.0",
)

# ── Mock Stock Database ───────────────────────────────────────────────────────
# In production this would be a real PostgreSQL/MySQL call.
# product_id → available quantity
MOCK_STOCK: dict[str, int] = {
    "ITEM-001":   50,
    "ITEM-002":    0,   # always out of stock (for testing error paths)
    "ITEM-003":   10,
    "ITEM-004":  100,
    "ITEM-005":    5,
    "prod_123":   20,   # matches the example in the spec
    "prod_456":    0,
    "prod_789":   15,
}


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"service": "InventoryService", "status": "running", "port": 8001}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ── Main endpoint ─────────────────────────────────────────────────────────────
@app.get("/inventory/check", tags=["Inventory"])
def check_inventory(
    product_id: str = Query(..., description="Product ID to check stock for"),
    quantity:   int = Query(1,   description="Quantity requested (must be >= 1)", ge=1),
):
    """
    Check if a product is available in the requested quantity.

    Called by the Orchestrator with: ?product_id=ITEM-001&quantity=2

    Returns:
    - available (bool): True if stock >= requested quantity
    - stock_left (int): Remaining stock AFTER reservation (if available)
    - product_id (str): Echoed back for the Orchestrator to use
    - quantity_requested (int): What was asked for

    Error cases:
    - 404: product not found in catalogue
    - 409: out of stock (available=False)
    - 422: invalid input (FastAPI handles this automatically)
    """
    logger.info(f"📦 Inventory check: product_id={product_id}, quantity={quantity}")

    # ── Lookup product ────────────────────────────────────────────────────────
    if product_id not in MOCK_STOCK:
        logger.warning(f"  ❌ Product not found: {product_id}")
        raise HTTPException(
            status_code=404,
            detail={
                "error":      "PRODUCT_NOT_FOUND",
                "product_id": product_id,
                "message":    f"Product '{product_id}' does not exist in the catalogue.",
            },
        )

    current_stock = MOCK_STOCK[product_id]

    # ── Check availability ────────────────────────────────────────────────────
    if current_stock < quantity:
        logger.warning(
            f"  ⛔ Out of stock: {product_id} has {current_stock}, need {quantity}"
        )
        raise HTTPException(
            status_code=409,
            detail={
                "error":              "OUT_OF_STOCK",
                "product_id":         product_id,
                "quantity_requested": quantity,
                "quantity_available": current_stock,
                "available":          False,
                "message":            f"Only {current_stock} units of '{product_id}' available.",
            },
        )

    # ── Reserve stock (decrement) ─────────────────────────────────────────────
    MOCK_STOCK[product_id] -= quantity
    stock_left = MOCK_STOCK[product_id]

    logger.info(
        f"  ✅ Reserved {quantity}x {product_id}. Stock left: {stock_left}"
    )

    # ── Return response (matches diagram: available, stock_left) ──────────────
    return {
        "available":          True,
        "product_id":         product_id,
        "quantity_requested": quantity,
        "stock_left":         stock_left,
        "message":            f"Stock confirmed. {stock_left} units remaining after reservation.",
    }


# ── Admin: view stock (useful for testing) ────────────────────────────────────
@app.get("/inventory/stock", tags=["Admin"])
def view_all_stock():
    """Returns the full stock table. Useful for debugging."""
    return {"stock": MOCK_STOCK}


@app.post("/inventory/restock", tags=["Admin"])
def restock(product_id: str = Query(...), quantity: int = Query(..., ge=1)):
    """Manually restock a product (for testing)."""
    if product_id not in MOCK_STOCK:
        MOCK_STOCK[product_id] = 0
    MOCK_STOCK[product_id] += quantity
    return {
        "product_id": product_id,
        "new_stock":  MOCK_STOCK[product_id],
        "message":    f"Restocked {quantity} units.",
    }


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("INVENTORY_PORT", 8001))
    logger.info(f"🚀 Starting Inventory Service on port {port}")
    uvicorn.run("inventory_service:app", host="0.0.0.0", port=port, reload=True)
