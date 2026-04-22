"""
base_worker.py
--------------
Shared Redis listener used by all 5 mock workers.

Pattern:
  - Workers register handlers with @register("node_id")
  - run() blocks forever, reading from queue:MOCK_HTTP
  - On task received, dispatches to the registered handler
  - On success: POST /api/v1/callbacks/task-complete
  - On failure: POST /api/v1/callbacks/task-failed
"""

import json
import logging
import os
import time
from pathlib import Path

import httpx
import redis
from dotenv import load_dotenv

# Load .env from project root (one level up from /workers)
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

REDIS_URL       = os.getenv("REDIS_URL",        "redis://localhost:6379")
ORCHESTRATOR    = os.getenv("ORCHESTRATOR_HOST", "http://localhost:8000")
QUEUE_NAME      = "queue:MOCK_HTTP"

# ---------------------------------------------------------------------------
# Logging setup — clean, timestamped output for every worker
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("Worker")

# ---------------------------------------------------------------------------
# Handler Registry
# Maps node_id (e.g., "charge_payment") → handler function
# ---------------------------------------------------------------------------
_HANDLERS: dict = {}


def register(node_id: str):
    """
    Decorator to register a handler function for a specific DAG node.

    Usage:
        @register("charge_payment")
        def handle_payment(payload: dict) -> dict:
            ...
            return {"transaction_id": "TXN-..."}
    """
    def decorator(fn):
        _HANDLERS[node_id] = fn
        return fn
    return decorator


# ---------------------------------------------------------------------------
# Callback Sender
# ---------------------------------------------------------------------------
def _send_callback(endpoint: str, body: dict) -> None:
    """
    POST the task result to the orchestrator's callback endpoint.
    Uses httpx (synchronous) with a retry on transient network errors.
    """
    url = f"{ORCHESTRATOR}/api/v1/callbacks/{endpoint}"
    for attempt in range(1, 4):  # 3 attempts
        try:
            resp = httpx.post(url, json=body, timeout=10)
            resp.raise_for_status()
            log.info(f"  Callback /{endpoint} → HTTP {resp.status_code}")
            return
        except httpx.HTTPStatusError as e:
            log.error(f"  Callback HTTP error (attempt {attempt}): {e.response.status_code}")
        except httpx.RequestError as e:
            log.error(f"  Callback network error (attempt {attempt}): {e}")
        if attempt < 3:
            time.sleep(1.5 * attempt)  # exponential-ish backoff

    log.critical(f"  FAILED to send callback after 3 attempts. task_id={body.get('task_id')}")


# ---------------------------------------------------------------------------
# Main Worker Loop
# ---------------------------------------------------------------------------
def run() -> None:
    """
    Connect to Redis and block forever, processing tasks as they arrive.
    Called from run_workers.py or from each individual worker's __main__.
    """
    r = redis.from_url(REDIS_URL, decode_responses=True)

    log.info("=" * 55)
    log.info("  Workflow Orchestrator — Mock Worker")
    log.info(f"  Queue     : {QUEUE_NAME}")
    log.info(f"  Orchestrator: {ORCHESTRATOR}")
    log.info(f"  Handlers  : {list(_HANDLERS.keys())}")
    log.info("=" * 55)
    log.info("Waiting for tasks...\n")

    while True:
        # ── 1. Block-read from Redis (5s timeout so we stay alive) ──────────
        try:
            result = r.brpop(QUEUE_NAME, timeout=5)
        except redis.exceptions.ConnectionError:
            log.warning("Redis connection lost. Retrying in 3s...")
            time.sleep(3)
            continue

        if result is None:
            continue  # timeout — loop again

        _, raw = result

        # ── 2. Parse payload ─────────────────────────────────────────────────
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            log.error(f"Invalid JSON received. Discarding: {raw[:80]}")
            continue

        task_id  = payload.get("task_id", "unknown")
        node_id  = payload.get("node_id", "unknown")

        log.info(f"Task received: '{node_id}' | task_id={task_id}")

        # ── 3. Route to handler ───────────────────────────────────────────────
        handler = _HANDLERS.get(node_id)

        if handler is None:
            # This worker doesn't handle this node_id.
            # Re-enqueue so another worker (or future handler) can pick it up.
            log.warning(f"  No handler for '{node_id}'. Re-enqueuing...")
            r.lpush(QUEUE_NAME, raw)
            time.sleep(0.3)  # Brief back-off to prevent busy-loop
            continue

        # ── 4. Execute handler ────────────────────────────────────────────────
        try:
            output = handler(payload)
            _send_callback("task-complete", {
                "task_id": task_id,
                "output":  output or {},
            })

        except Exception as exc:
            log.error(f"  Handler FAILED for '{node_id}': {exc}")
            _send_callback("task-failed", {
                "task_id":      task_id,
                "error_message": str(exc),
            })
