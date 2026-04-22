"""
test_phase3.py
--------------
End-to-end integration test for the Phase 3 FastAPI REST layer.

Tests the full DAG flow:
  1. Upload template   → POST /api/v1/templates
  2. Trigger execution → POST /api/v1/executions
  3. Check state       → GET  /api/v1/executions/{id}
  4. Worker callback   → POST /api/v1/callbacks/task-complete
  5. Verify DAG moved  → GET  /api/v1/executions/{id}

Requirements:
  - FastAPI server running on port 8000
  - PostgreSQL + Redis Docker containers running
"""

import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1"


async def run_tests():
    print("--- Starting Phase 3 API Integration Tests ---")

    async with httpx.AsyncClient(timeout=15.0) as client:

        # ------------------------------------------------------------------
        # TEST 1: Upload a 2-node DAG template
        # task_1 has no dependencies, task_2 depends on task_1.
        # Key: "depends_on" is our engine's standard field name.
        # ------------------------------------------------------------------
        print("\n[Test 1] POST /api/v1/templates — Upload DAG blueprint")
        payload = {
            "name": "Phase3 Integration Test DAG",
            "description": "2-node linear DAG: task_1 -> task_2",
            "definition": {
                "tasks": [
                    {"id": "task_1", "type": "MOCK_HTTP", "depends_on": []},
                    {"id": "task_2", "type": "MOCK_HTTP", "depends_on": ["task_1"]}
                ]
            }
        }
        resp = await client.post(f"{BASE_URL}/templates", json=payload)
        assert resp.status_code == 201, f"FAIL (status {resp.status_code}): {resp.text}"
        template_id = resp.json()["template_id"]
        print(f"  [PASS] Template created. template_id: {template_id}")

        # ------------------------------------------------------------------
        # TEST 2: Trigger execution
        # ------------------------------------------------------------------
        print("\n[Test 2] POST /api/v1/executions — Trigger execution")
        exec_payload = {
            "template_id": template_id,
            "global_context": {"test_run": True, "order_id": "TEST-001"}
        }
        resp = await client.post(f"{BASE_URL}/executions", json=exec_payload)
        assert resp.status_code == 201, f"FAIL (status {resp.status_code}): {resp.text}"
        execution_id = resp.json()["details"]["execution_id"]
        print(f"  [PASS] Execution triggered. execution_id: {execution_id}")

        # Wait for the async engine to complete the dispatch
        await asyncio.sleep(1)

        # ------------------------------------------------------------------
        # TEST 3: Verify initial state — task_1 IN_PROGRESS, task_2 PENDING
        # This proves Kahn's Algorithm is correctly blocking task_2.
        # ------------------------------------------------------------------
        print(f"\n[Test 3] GET /api/v1/executions/{execution_id} — Verify initial DAG state")
        resp = await client.get(f"{BASE_URL}/executions/{execution_id}")
        assert resp.status_code == 200, f"FAIL: {resp.text}"

        state = resp.json()
        task_1 = next((t for t in state["tasks"] if t["node_id"] == "task_1"), None)
        task_2 = next((t for t in state["tasks"] if t["node_id"] == "task_2"), None)

        assert task_1 is not None, "task_1 not found in execution state"
        assert task_2 is not None, "task_2 not found in execution state"
        assert task_1["status"] == "IN_PROGRESS", f"task_1 should be IN_PROGRESS, got {task_1['status']}"
        assert task_2["status"] == "PENDING", f"task_2 should be PENDING, got {task_2['status']}"

        print(f"  Execution Status : {state['status']}")
        print(f"  task_1 status    : {task_1['status']} (expected: IN_PROGRESS)")
        print(f"  task_2 status    : {task_2['status']} (expected: PENDING)")
        print(f"  [PASS] Kahn's Algorithm correctly blocked task_2 until task_1 completes.")

        # ------------------------------------------------------------------
        # TEST 4: Simulate worker completing task_1 via callback webhook
        # ------------------------------------------------------------------
        print("\n[Test 4] POST /api/v1/callbacks/task-complete — Simulate worker success")
        cb_payload = {
            "task_id": task_1["task_id"],
            "output": {"result": "order validated", "code": 200}
        }
        resp = await client.post(f"{BASE_URL}/callbacks/task-complete", json=cb_payload)
        assert resp.status_code == 200, f"FAIL: {resp.text}"
        print(f"  [PASS] Worker webhook accepted for task_1.")

        # Wait for engine to process and unlock task_2
        await asyncio.sleep(1)

        # ------------------------------------------------------------------
        # TEST 5: Verify DAG progressed — task_1 COMPLETED, task_2 IN_PROGRESS
        # This proves the callback correctly fired Kahn's next wave.
        # ------------------------------------------------------------------
        print(f"\n[Test 5] GET /api/v1/executions/{execution_id} — Verify DAG progressed")
        resp = await client.get(f"{BASE_URL}/executions/{execution_id}")
        assert resp.status_code == 200, f"FAIL: {resp.text}"

        state = resp.json()
        task_1_new = next(t for t in state["tasks"] if t["node_id"] == "task_1")
        task_2_new = next(t for t in state["tasks"] if t["node_id"] == "task_2")

        assert task_1_new["status"] == "COMPLETED", f"task_1 should be COMPLETED, got {task_1_new['status']}"
        assert task_2_new["status"] == "IN_PROGRESS", f"task_2 should be IN_PROGRESS, got {task_2_new['status']}"

        print(f"  task_1 status : {task_1_new['status']} (expected: COMPLETED)")
        print(f"  task_2 status : {task_2_new['status']} (expected: IN_PROGRESS)")
        print(f"  [PASS] DAG progressed correctly. task_2 unlocked after task_1 completed.")

        print("\n[DONE] ALL 5 TESTS PASSED. Phase 3 is clean and bug-free.")


if __name__ == "__main__":
    asyncio.run(run_tests())
