"""
test_phase4.py
--------------
End-to-end Phase 4 integration test.

Tests the FULL loop:
  1. Upload the 6-node e-commerce DAG template
  2. Trigger an execution with a realistic global_context
  3. Wait for the worker to process all MOCK_HTTP tasks automatically
  4. Simulate human approval for the fraud_check node (HUMAN_APPROVAL)
  5. Assert the final state is COMPLETED with all 6 tasks COMPLETED

Prerequisites (must be running before executing this test):
  - Docker: postgres (port 5434) + redis (port 6379)
  - FastAPI server: cd orchestrator && python -m uvicorn api:app --port 8000
  - Workers:        cd workers    && python run_workers.py
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

BASE_URL  = "http://localhost:8000/api/v1"
TIMEOUT   = 120   # seconds to wait for full workflow completion
POLL_SECS = 2     # seconds between status polls

# Load the workflow definition from the JSON file
WORKFLOW_JSON = json.loads(
    (Path(__file__).parent.parent / "workflows" / "ecommerce_workflow.json").read_text()
)

# A realistic global context that workers can use
GLOBAL_CONTEXT = {
    "order_id":       "ORD-TEST-9901",
    "customer_id":    "CUST-042",
    "customer_email": "alice@example.com",
    "product_id":     "ITEM-001",
    "quantity":       2,
    "total_amount":   59.98,
    "currency":       "USD",
    "warehouse":      "WH-CENTRAL",
}


async def run_tests():
    print("\n" + "=" * 60)
    print("  Phase 4 End-to-End Integration Test")
    print("=" * 60)

    async with httpx.AsyncClient(timeout=20.0) as client:

        # STEP 0: Pre-flight — make sure the server is up
        print("\n[Pre-flight] Checking orchestrator is up...")
        try:
            resp = await client.get(f"{BASE_URL}/executions")
            assert resp.status_code == 200, f"Unexpected: {resp.status_code}"
            print("  [OK] Orchestrator is responding.")
        except (httpx.ConnectError, AssertionError) as e:
            print(f"  [FAIL] Cannot reach orchestrator at {BASE_URL}: {e}")
            print("  --> Make sure: cd orchestrator && python -m uvicorn api:app --port 8000")
            sys.exit(1)

        # TEST 1: Upload e-commerce DAG template
        print("\n[Test 1] POST /templates — Upload 6-node e-commerce DAG")
        resp = await client.post(f"{BASE_URL}/templates", json={
            "name":        "E-Commerce Order Processing",
            "description": "Full order lifecycle: validation -> payment -> inventory -> shipping -> notification",
            "definition":  WORKFLOW_JSON,
        })
        assert resp.status_code == 201, f"FAIL ({resp.status_code}): {resp.text}"
        template_id = resp.json()["template_id"]
        print(f"  [PASS] Template uploaded. template_id={template_id}")

        # TEST 2: Trigger execution
        print("\n[Test 2] POST /executions — Trigger e-commerce workflow")
        resp = await client.post(f"{BASE_URL}/executions", json={
            "template_id":    template_id,
            "global_context": GLOBAL_CONTEXT,
        })
        assert resp.status_code == 201, f"FAIL ({resp.status_code}): {resp.text}"
        execution_id = resp.json()["details"]["execution_id"]
        print(f"  [PASS] Execution triggered. execution_id={execution_id}")

        await asyncio.sleep(2)

        # TEST 3: Verify initial state — only validate_order should start
        print("\n[Test 3] Verify initial DAG state (only validate_order should be IN_PROGRESS)")
        resp = await client.get(f"{BASE_URL}/executions/{execution_id}")
        assert resp.status_code == 200

        state = resp.json()
        task_map = {t["node_id"]: t for t in state["tasks"]}

        assert task_map["validate_order"]["status"] == "IN_PROGRESS", \
            f"validate_order should be IN_PROGRESS, got {task_map['validate_order']['status']}"
        assert task_map["charge_payment"]["status"] == "PENDING", \
            f"charge_payment should be PENDING, got {task_map['charge_payment']['status']}"
        assert task_map["fraud_check"]["status"] == "PENDING", \
            f"fraud_check should be PENDING, got {task_map['fraud_check']['status']}"
        print(f"  [PASS] Kahn's Algorithm holding back downstream tasks correctly.")

        # TEST 4: Wait for worker to auto-complete MOCK_HTTP tasks
        #         Meanwhile, we need to approve the fraud_check HUMAN_APPROVAL
        print(f"\n[Test 4] Watching DAG progress (max {TIMEOUT}s)...")
        print("         Workers running in background. Waiting for tasks to complete...")

        fraud_approved = False
        deadline = time.time() + TIMEOUT

        while time.time() < deadline:
            await asyncio.sleep(POLL_SECS)

            resp = await client.get(f"{BASE_URL}/executions/{execution_id}")
            assert resp.status_code == 200
            state    = resp.json()
            task_map = {t["node_id"]: t for t in state["tasks"]}
            statuses = {k: v["status"] for k, v in task_map.items()}

            # Print current state
            status_line = " | ".join(f"{k}={v}" for k, v in statuses.items())
            print(f"  [{int(deadline - time.time()):3d}s left] {status_line}")

            # Auto-approve fraud_check once it's AWAITING_APPROVAL
            if not fraud_approved and task_map["fraud_check"]["status"] == "AWAITING_APPROVAL":
                fraud_task_id = task_map["fraud_check"]["task_id"]
                print(f"\n  --> fraud_check is AWAITING_APPROVAL. Auto-approving for test...")
                approve_resp = await client.post(
                    f"{BASE_URL}/tasks/{fraud_task_id}/approve",
                    json={"comment": "Auto-approved by test suite — no fraud signals detected."}
                )
                if approve_resp.status_code == 200:
                    print(f"  [PASS] fraud_check approved.")
                    fraud_approved = True
                else:
                    print(f"  [WARN] Approval failed: {approve_resp.status_code} {approve_resp.text}")

            # Check if workflow is done
            if state["status"] in ("COMPLETED", "FAILED", "TERMINATED"):
                break

        # TEST 5: Final state assertions
        print(f"\n[Test 5] Final state verification")
        resp = await client.get(f"{BASE_URL}/executions/{execution_id}")
        final  = resp.json()
        task_map = {t["node_id"]: t for t in final["tasks"]}
        statuses = {k: v["status"] for k, v in task_map.items()}

        print(f"  Execution status : {final['status']}")
        for node_id, status in statuses.items():
            mark = "[PASS]" if status == "COMPLETED" else "[FAIL]"
            print(f"  {mark} {node_id:25s} -> {status}")

        failed_tasks = [k for k, v in statuses.items() if v != "COMPLETED"]

        if final["status"] == "COMPLETED" and not failed_tasks:
            print("\n" + "=" * 60)
            print("  [DONE] ALL TESTS PASSED. Phase 4 is complete!")
            print("  Full DAG flow: Orchestrator -> Redis -> Workers -> Callbacks")
            print("=" * 60)
        else:
            print(f"\n[FAIL] Workflow ended in '{final['status']}'. Non-completed tasks: {failed_tasks}")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
