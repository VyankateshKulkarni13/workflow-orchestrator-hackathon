# Mock Microservices Reference Guide
### Workflow Orchestrator — E-Commerce Domain

> [!NOTE]
> All services listed here are **simulated Python scripts**. They do NOT implement real business logic.  
> Their sole purpose is to **honour the data contract** — accept a known input shape and return a known output shape — so the Orchestrator has real services to coordinate against during development and demo.

---

## The Core Idea: Contracts, Not Logic

In production, each of these services would be a full codebase (Node.js, Java Spring Boot, etc.) connected to real 3rd party APIs (Stripe, FedEx, SendGrid). In our system, all we care about is the **contract**:

```
Input  → [Worker Script] → Output → Orchestrator Webhook
```

Each worker:
1. **Listens** to a named Redis channel
2. **Sleeps** for 1-3 seconds (simulating real processing time)
3. **Returns** a realistic JSON output to the orchestrator's webhook

---

## Mock Worker #1 — Order Validation Service

**Purpose:** Validates an incoming order's structure, checks if the customer account is valid, and confirms the ordered items exist in the catalog.

**Redis Channel:** `queue:validate_order`

**Input Payload (sent by Orchestrator):**
```json
{
  "task_id": "uuid-of-task",
  "execution_id": "uuid-of-execution",
  "payload": {
    "order_id": "ORD-20240421-001",
    "customer_id": "CUST-789",
    "items": [
      { "sku": "TSHIRT-BLK-L", "quantity": 2, "unit_price": 999 },
      { "sku": "JEANS-BLU-32", "quantity": 1, "unit_price": 2499 }
    ],
    "total_amount": 4497,
    "currency": "INR"
  }
}
```

**Success Output (posted to Orchestrator webhook):**
```json
{
  "task_id": "uuid-of-task",
  "status": "success",
  "output": {
    "validation_status": "VALID",
    "validated_order_id": "ORD-20240421-001",
    "item_count": 3,
    "validated_at": "2024-04-21T13:45:00Z"
  }
}
```

**Failure Output (e.g., invalid SKU):**
```json
{
  "task_id": "uuid-of-task",
  "status": "failure",
  "error": "SKU 'JEANS-BLU-32' not found in catalog"
}
```

**Simulated Delay:** `1.0 seconds`

---

## Mock Worker #2 — Payment Processing Service

**Purpose:** Charges the customer's payment method. In the real world this would call Stripe/Razorpay. Our mock will randomly succeed 90% of the time and fail 10% to demonstrate the **retry policy**.

**Redis Channel:** `queue:charge_payment`

**Input Payload:**
```json
{
  "task_id": "uuid-of-task",
  "execution_id": "uuid-of-execution",
  "payload": {
    "order_id": "ORD-20240421-001",
    "customer_id": "CUST-789",
    "amount": 4497,
    "currency": "INR",
    "payment_method": "CARD",
    "card_last4": "4242"
  }
}
```

**Success Output:**
```json
{
  "task_id": "uuid-of-task",
  "status": "success",
  "output": {
    "transaction_id": "TXN-STRIPE-XYZ-789",
    "amount_charged": 4497,
    "currency": "INR",
    "payment_status": "CAPTURED",
    "gateway": "mock-stripe",
    "captured_at": "2024-04-21T13:45:03Z"
  }
}
```

**Failure Output (simulated gateway timeout):**
```json
{
  "task_id": "uuid-of-task",
  "status": "failure",
  "error": "Payment gateway timeout. Connection refused after 30s."
}
```

**Simulated Delay:** `2.0 seconds`  
**Failure Rate:** 10% random (to demo retries)

---

## Mock Worker #3 — Inventory Reservation Service

**Purpose:** Reserves (locks) the ordered SKUs in the warehouse inventory so they cannot be sold to another customer while this order is being processed.

**Redis Channel:** `queue:update_inventory`

**Input Payload:**
```json
{
  "task_id": "uuid-of-task",
  "execution_id": "uuid-of-execution",
  "payload": {
    "order_id": "ORD-20240421-001",
    "items": [
      { "sku": "TSHIRT-BLK-L", "quantity": 2 },
      { "sku": "JEANS-BLU-32", "quantity": 1 }
    ]
  }
}
```

**Success Output:**
```json
{
  "task_id": "uuid-of-task",
  "status": "success",
  "output": {
    "reservation_id": "RES-WH-456",
    "items_reserved": [
      { "sku": "TSHIRT-BLK-L", "quantity": 2, "warehouse": "WH-MUMBAI-01" },
      { "sku": "JEANS-BLU-32", "quantity": 1, "warehouse": "WH-MUMBAI-01" }
    ],
    "reserved_until": "2024-04-21T14:45:00Z"
  }
}
```

**Failure Output (out of stock):**
```json
{
  "task_id": "uuid-of-task",
  "status": "failure",
  "error": "Insufficient stock for SKU 'JEANS-BLU-32'. Available: 0, Requested: 1"
}
```

**Simulated Delay:** `1.5 seconds`

---

## Mock Worker #4 — Shipping & Logistics Service

**Purpose:** Creates a shipment record and books a courier pickup slot. In real life this calls FedEx/Delhivery/Shiprocket APIs.

**Redis Channel:** `queue:dispatch_shipping`

**Input Payload:**
```json
{
  "task_id": "uuid-of-task",
  "execution_id": "uuid-of-execution",
  "payload": {
    "order_id": "ORD-20240421-001",
    "reservation_id": "RES-WH-456",
    "customer_address": {
      "name": "Vyankatesh Kulkarni",
      "line1": "Flat 12, Sunrise Apts",
      "city": "Pune",
      "state": "Maharashtra",
      "pincode": "411001"
    },
    "items_count": 3,
    "weight_kg": 1.2
  }
}
```

**Success Output:**
```json
{
  "task_id": "uuid-of-task",
  "status": "success",
  "output": {
    "tracking_id": "DELHIVERY-TRK-98765",
    "courier": "Mock Delhivery",
    "estimated_delivery": "2024-04-23",
    "pickup_scheduled_at": "2024-04-21T18:00:00Z",
    "label_url": "https://mock-courier.internal/labels/98765.pdf"
  }
}
```

**Simulated Delay:** `2.0 seconds`

---

## Mock Worker #5 — Notification Service

**Purpose:** Sends an order confirmation email and SMS to the customer. In real life this calls SendGrid (email) and Twilio (SMS).

**Redis Channel:** `queue:send_receipt`

**Input Payload:**
```json
{
  "task_id": "uuid-of-task",
  "execution_id": "uuid-of-execution",
  "payload": {
    "order_id": "ORD-20240421-001",
    "customer_email": "customer@example.com",
    "customer_phone": "+919876543210",
    "order_total": 4497,
    "tracking_id": "DELHIVERY-TRK-98765",
    "estimated_delivery": "2024-04-23"
  }
}
```

**Success Output:**
```json
{
  "task_id": "uuid-of-task",
  "status": "success",
  "output": {
    "email_sent": true,
    "sms_sent": true,
    "email_message_id": "MSG-SENDGRID-AAA111",
    "notification_sent_at": "2024-04-21T13:45:08Z"
  }
}
```

**Simulated Delay:** `0.5 seconds`

---

## Human Approval — Fraud Review Gate

**Purpose:** NOT a worker script. This is a special node type handled entirely by the Orchestrator itself. When encountered, the engine suspends the workflow branch and waits for a manual admin decision via the dashboard.

**Trigger:** Orders above ₹10,000 are automatically routed through this gate.

**Dashboard UI shows:**
- Order details
- Customer history summary (mocked)
- An **Approve** button → calls `POST /api/v1/tasks/{task_id}/approve`
- A **Reject** button → calls `POST /api/v1/tasks/{task_id}/reject` → marks as FAILED

**Output after approval:**
```json
{
  "approved_by": "VyankateshKulkarni13",
  "approved_at": "2024-04-21T13:50:00Z",
  "notes": "Customer verified, order cleared."
}
```

---

## Complete Execution Flow with Contracts

```
ORDER PLACED
     │
     ▼
[validate_order] ──────────────────────────────────────────────────────────────────┐
  Input:  { order_id, items[], total }                                              │
  Output: { validation_status: "VALID" }                                            │
     │                                                                              │
     ├──────────────────────────────────────────────────────────────────────────────┤
     │                                                                              │
     ▼                                                                              ▼
[charge_payment] (MOCK_HTTP)                                         [fraud_check] (HUMAN_APPROVAL)
  Input:  { order_id, amount, currency }                               → Admin sees this in dashboard
  Output: { transaction_id, payment_status: "CAPTURED" }              → Admin clicks "Approve"
     │                                                                              │
     │    ┌─────────────────────────────────────────────────────────────────────────┘
     │    │  (Both branches must complete before this node unlocks)
     │    │
     ▼    ▼
[update_inventory] (MESSAGE_QUEUE)
  Input:  { order_id, items[] }
  Output: { reservation_id, items_reserved[] }
     │
     ├──────────────────────────────────────────────────────────────┐
     │                                                              │
     ▼                                                              ▼
[dispatch_shipping] (MESSAGE_QUEUE)               [send_receipt] unblocks from charge_payment ─►
  Input:  { order_id, reservation_id, address }  Input:  { order_id, email, tracking_id }
  Output: { tracking_id, estimated_delivery }    Output: { email_sent: true, sms_sent: true }

ORDER COMPLETE ✓
```

---

## Summary Table

| Worker | Redis Channel | Delay | Failure Rate | Real-World Equivalent |
|---|---|---|---|---|
| `order_validation_worker.py` | `queue:validate_order` | 1.0s | 0% | Internal catalog DB check |
| `payment_worker.py` | `queue:charge_payment` | 2.0s | 10% | Stripe / Razorpay API |
| `inventory_worker.py` | `queue:update_inventory` | 1.5s | 0% | Warehouse Management System |
| `shipping_worker.py` | `queue:dispatch_shipping` | 2.0s | 0% | FedEx / Delhivery API |
| `notification_worker.py` | `queue:send_receipt` | 0.5s | 0% | SendGrid / Twilio API |
| *(No script)* `HUMAN_APPROVAL` | N/A (Dashboard) | Admin decision | N/A | Manual fraud review team |
