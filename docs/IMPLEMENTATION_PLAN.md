# End-to-End Implementation Plan
### Workflow Orchestrator — E-Commerce Order Fulfillment
**Author:** Lead Developer | **Version:** 1.0.0

---

## Pre-Development Checklist

Before writing a single line of application code, the following must be in place:

- [x] GitHub repository created and access configured
- [x] Branch protection rules enforced on `main`
- [x] All documentation written (PROJECT_DESCRIPTION, MICROSERVICES_REFERENCE, ARCHITECTURE)
- [ ] Docker Desktop installed and running
- [ ] Python 3.11+ installed (`python --version`)
- [ ] Node.js 20+ installed (`node --version`)
- [ ] VS Code with Python + ESLint extensions installed

---

## Phase 0 — Repository Scaffolding
> **Goal:** Create the complete folder structure and base config files before any logic is written. This prevents merge conflicts and lets teammates work in parallel in separate directories.

### Step 0.1 — Create Project Folder Structure
```
workflow-orchestrator-hackathon/
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
├── README.md
├── docs/
├── orchestrator/
│   ├── routers/
│   └── requirements.txt
├── workers/
├── workflows/
└── frontend/
```

### Step 0.2 — Write `.gitignore`
Must ignore: `__pycache__/`, `*.pyc`, `.env`, `node_modules/`, `.next/`, `venv/`

### Step 0.3 — Write `docker-compose.yml`
Define two services:
- `postgres`: Image `postgres:15-alpine`, port `5432:5432`, env vars for DB name/user/password, a named volume for data persistence
- `redis`: Image `redis:7-alpine`, port `6379:6379`

### Step 0.4 — Write `.env` and `.env.example`
```env
# Database
DATABASE_URL=postgresql+asyncpg://orchestrator:password@localhost:5432/orchestrator_db

# Redis
REDIS_URL=redis://localhost:6379

# Orchestrator
ORCHESTRATOR_HOST=http://localhost:8000
```

**Deliverable:** `docker-compose up -d` runs successfully. Postgres and Redis containers are healthy.

---

## Phase 1 — Orchestrator: Database Layer
> **Goal:** Establish a rock-solid, async database connection and define all three ORM models. No business logic yet — just the data foundation.

### Step 1.1 — Create Python Virtual Environment
```bash
cd orchestrator
python -m venv venv
venv\Scripts\activate   # Windows
pip install fastapi uvicorn sqlalchemy asyncpg pydantic pyyaml python-multipart redis python-dotenv
pip freeze > requirements.txt
```

### Step 1.2 — Write `database.py`
- Create an `async_engine` using SQLAlchemy with `create_async_engine(DATABASE_URL)`
- Create an `AsyncSessionLocal` session factory
- Create a `Base = declarative_base()` for ORM models
- Write a `get_db()` async dependency function that yields a session per request (used by FastAPI routers)
- Write a `create_tables()` async function that calls `Base.metadata.create_all(engine)` — called once on app startup

### Step 1.3 — Write `models.py`
Define three SQLAlchemy ORM classes:

**`WorkflowTemplate`**
- `template_id` → UUID, primary key, default `uuid4()`
- `name` → String(255), not null
- `description` → Text, nullable
- `definition` → JSON (JSONB in Postgres), not null — stores the raw parsed DAG
- `created_at` → DateTime, default `utcnow()`
- `updated_at` → DateTime, onupdate `utcnow()`

**`WorkflowExecution`**
- `execution_id` → UUID, primary key
- `template_id` → UUID, ForeignKey to `workflow_templates`
- `status` → Enum(`PENDING`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`, `TERMINATED`)
- `global_context` → JSON — the runtime order payload
- `created_at`, `updated_at` → DateTime

**`TaskExecution`**
- `task_id` → UUID, primary key
- `execution_id` → UUID, ForeignKey to `workflow_executions`
- `node_id` → String(255) — matches the `id` key in the workflow JSON
- `status` → Enum(`PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `AWAITING_APPROVAL`, `TERMINATED`)
- `retry_count` → Integer, default `0`
- `output` → JSON, nullable — stores worker response
- `logs` → Text, nullable
- `started_at`, `completed_at` → DateTime, nullable

**Deliverable:** Running `python -c "from models import *; print('OK')"` exits cleanly with no errors.

---

## Phase 2 — Orchestrator: The Core Engine (DAG Logic)
> **Goal:** Build the pure algorithmic brain of the system. This is the most critical file in the entire project. No FastAPI, no Redis yet — just the graph logic in isolation.

### Step 2.1 — Write `engine.py` — DAG Parser

**Function: `parse_dag(definition: dict) → dict`**
- Input: raw workflow JSON as a Python dict
- Build an `adjacency_list`: `{ node_id: [list of nodes that depend on it] }`
- Build an `in_degree` map: `{ node_id: count of unresolved dependencies }`
- Build a `nodes` map: `{ node_id: full task object }` for quick lookup
- Return all three structures packaged as a dict
- **Validation:** If a task references a dependency that doesn't exist as a node → raise `ValueError`. Cyclic dependency detection using DFS is a bonus.

### Step 2.2 — Write `engine.py` — Task Dispatcher

**Function: `get_ready_tasks(task_executions: list, nodes: dict, in_degree: dict) → list`**
- Takes the current list of task execution states from DB
- Filters for tasks where status is `PENDING` AND in-degree is `0`
- Returns the list of task node objects that are ready to be dispatched right now

### Step 2.3 — Write `engine.py` — Completion Handler

**Function: `on_task_completed(node_id: str, adjacency_list: dict, in_degree: dict) → list`**
- Called when a worker reports success via webhook
- Decrements the in-degree of every node in `adjacency_list[node_id]`
- Returns the list of nodes whose in-degree just dropped to `0` (newly unblocked tasks)

### Step 2.4 — Write `engine.py` — Execution Orchestrator

**Async Function: `run_next_tasks(execution_id: str, db: AsyncSession)`**
- Loads the workflow execution from DB → gets the template definition
- Re-parses the DAG from the JSON stored in `workflow_templates`
- Calculates the current in-degree of all nodes based on the `COMPLETED` tasks already in `task_executions`
- Dispatches all nodes with `in-degree = 0` that are still `PENDING`
- For `MOCK_HTTP` and `MESSAGE_QUEUE` tasks → push to Redis
- For `HUMAN_APPROVAL` tasks → update status to `AWAITING_APPROVAL` in DB, do NOT push to Redis
- Checks if all tasks are `COMPLETED` → if yes, mark the global workflow as `COMPLETED`

**Deliverable:** Write a standalone test script `test_engine.py` that creates a mock DAG dict and calls these functions. Verify the output prints the correct execution order: `validate_order` first, then `charge_payment` and `fraud_check` in parallel, etc.

---

## Phase 3 — Orchestrator: Redis Integration
> **Goal:** Connect the engine to Redis so tasks can actually be dispatched to worker processes.

### Step 3.1 — Write `redis_client.py`
- Create an async Redis connection using `redis.asyncio.from_url(REDIS_URL)`
- Write an `enqueue_task(channel: str, payload: dict)` helper that pushes a JSON-serialized message to a Redis List (using `LPUSH`)
- Write a `dequeue_task(channel: str)` helper that blocking-pops from the list (using `BRPOP`) — used by worker scripts

### Step 3.2 — Update `engine.py` to Use Redis
- In `run_next_tasks()`, when a task type is `MOCK_HTTP` or `MESSAGE_QUEUE`, call `enqueue_task()` with:
  - The task's `target` or `topic` as the channel name
  - A payload containing: `task_id`, `execution_id`, and the `global_context` data

**Deliverable:** Start Redis via Docker. Run `test_engine.py`. Verify via `redis-cli LRANGE queue:validate_order 0 -1` that the task payload appears in Redis.

---

## Phase 4 — Orchestrator: FastAPI REST API
> **Goal:** Expose the engine and database via HTTP endpoints so the frontend and workers can communicate with the orchestrator.

### Step 4.1 — Write `main.py`
- Initialize FastAPI app with title, version, and CORS middleware (allow `localhost:3000`)
- On startup event: call `create_tables()` to auto-create DB schema
- Include all four routers under the `/api/v1` prefix
- Root endpoint `GET /` returns a health check JSON

### Step 4.2 — Write `routers/templates.py`

**`POST /api/v1/templates`**
- Accept a file upload (`UploadFile`) supporting both `.json` and `.yaml` extensions
- Parse the file using `json.loads()` or `yaml.safe_load()` based on extension
- Validate that a `tasks` key exists and each task has an `id` and `dependencies` field
- Call `parse_dag()` to validate the graph has no broken dependency references
- Save to `workflow_templates` table, return the created `template_id`

**`GET /api/v1/templates`**
- Return a list of all templates (id, name, description, created_at)

**`GET /api/v1/templates/{template_id}`**
- Return the full template including the `definition` JSONB

### Step 4.3 — Write `routers/executions.py`

**`POST /api/v1/executions`**
- Accept: `{ template_id: UUID, context: dict }`
- Load the template from DB (404 if not found)
- Create a new `WorkflowExecution` row with status `RUNNING`
- Parse the DAG, create a `TaskExecution` row for every node with status `PENDING`
- Call `run_next_tasks()` → this fires the first wave of nodes to Redis
- Return the `execution_id`

**`GET /api/v1/executions`**
- Return paginated list of all executions with their current status and task counts

**`GET /api/v1/executions/{execution_id}`**
- Return: execution metadata + a full list of all `TaskExecution` rows for that run
- This is the primary endpoint polled by the dashboard every second

**`POST /api/v1/executions/{execution_id}/pause`**
- Set `workflow_executions.status = PAUSED`

**`POST /api/v1/executions/{execution_id}/resume`**
- Set status back to `RUNNING`
- Call `run_next_tasks()` to dispatch any tasks that became eligible while paused

**`POST /api/v1/executions/{execution_id}/terminate`**
- Set all `PENDING` task_executions to `TERMINATED`
- Set global execution to `TERMINATED`

### Step 4.4 — Write `routers/tasks.py`

**`POST /api/v1/tasks/{task_id}/approve`**
- Find the `TaskExecution` by `task_id`, ensure status is `AWAITING_APPROVAL`
- Set status to `COMPLETED`, store approval metadata in `output`
- Call `run_next_tasks(execution_id)` to continue the DAG

**`POST /api/v1/tasks/{task_id}/retry`**
- Ensure status is `FAILED`
- Increment `retry_count`, set status back to `PENDING`
- Re-enqueue the task to Redis

### Step 4.5 — Write `routers/callbacks.py`

**`POST /api/v1/callbacks/task-complete`**
- Accept: `{ task_id: UUID, status: "success"|"failure", output: dict, error: str }`
- If `status == "success"`: mark task as `COMPLETED`, store output, call `run_next_tasks()`
- If `status == "failure"`: check `retry_count` vs `retry_policy.max_attempts`
  - If retries remain: increment `retry_count`, re-enqueue to Redis after backoff delay
  - If exhausted: mark task as `FAILED`, optionally mark global execution as `FAILED`

**Deliverable:** Start the FastAPI server. Open `http://localhost:8000/docs`. Manually test `POST /templates` by uploading `ecommerce_standard_v1.json`. Verify the template appears in the DB.

---

## Phase 5 — Worker Scripts
> **Goal:** Write the 5 mock worker scripts that simulate external microservices. Each script is a standalone, continuously running Python process.

### Step 5.1 — Write `workers/base_worker.py`
A shared base class / utility that:
- Connects to Redis using the same `REDIS_URL` from `.env`
- Implements a `listen(channel: str, handler_fn: callable)` loop:
  ```python
  while True:
      message = redis.brpop(channel, timeout=0)  # blocking pop
      payload = json.loads(message)
      result = handler_fn(payload)
      requests.post(ORCHESTRATOR_CALLBACK_URL, json=result)
  ```
- Posts the result back to `POST /api/v1/callbacks/task-complete`

### Step 5.2 — Write Each Worker (5 files)

Each worker follows the same pattern:
```python
# payment_worker.py
import time, random
from base_worker import listen

def handle_payment(payload):
    time.sleep(2)                          # simulate processing
    if random.random() < 0.1:             # 10% failure rate
        return { "task_id": payload["task_id"], "status": "failure",
                 "error": "Payment gateway timeout" }
    return {
        "task_id": payload["task_id"], "status": "success",
        "output": { "transaction_id": f"TXN-{uuid4()}", "payment_status": "CAPTURED" }
    }

listen("queue:charge_payment", handle_payment)
```

Workers to implement:
- `order_validation_worker.py` → delay 1.0s, 0% failure
- `payment_worker.py` → delay 2.0s, 10% failure (for retry demo)
- `inventory_worker.py` → delay 1.5s, 0% failure
- `shipping_worker.py` → delay 2.0s, 0% failure
- `notification_worker.py` → delay 0.5s, 0% failure

**Deliverable:** With Orchestrator running, trigger `POST /executions`. Open 5 terminals, run all 5 workers. Watch the terminal logs — each worker should print "received task" and "callback sent". Query `GET /executions/{id}` and verify tasks are moving from `PENDING` → `IN_PROGRESS` → `COMPLETED`.

---

## Phase 6 — Workflow JSON Definitions
> **Goal:** Author all workflow definition files that will be uploaded via the UI.

### Step 6.1 — Create `workflows/` directory with 3 definitions:
- `ecommerce_standard_v1.json` — Full flow with all 5 workers + Human Approval
- `flash_sale_express.json` — Simple 3-step flow (validate → pay → notify)
- `high_value_order.json` — Payment blocked behind sequential fraud gate

**Deliverable:** All 3 files are valid JSON. Running `parse_dag()` on each returns no errors.

---

## Phase 7 — Frontend: Next.js Dashboard
> **Goal:** Build a premium, dark-mode glassmorphism dashboard that visualizes workflow execution in real-time.

### Step 7.1 — Bootstrap Next.js App
```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --eslint --app --no-src-dir
npm install reactflow axios
```

### Step 7.2 — Create API Client `lib/api.ts`
A centralized Axios instance pointed at `http://localhost:8000/api/v1` with helper functions:
- `uploadTemplate(file)` → `POST /templates` with FormData
- `triggerExecution(templateId, context)` → `POST /executions`
- `getExecution(executionId)` → `GET /executions/{id}`
- `getAllExecutions()` → `GET /executions`
- `approveTask(taskId)` → `POST /tasks/{task_id}/approve`
- `pauseExecution(id)` → `POST /executions/{id}/pause`
- `resumeExecution(id)` → `POST /executions/{id}/resume`
- `terminateExecution(id)` → `POST /executions/{id}/terminate`

### Step 7.3 — Build the Layout & Navigation
- Global dark background: `#0d0d0f`
- Glass-effect cards using `backdrop-filter: blur(12px)` with subtle `rgba` borders
- Left sidebar with navigation: Dashboard, Templates, Executions
- Top header showing system health status (Redis: ✅ / Postgres: ✅)

### Step 7.4 — Build Page: Template Manager (`/templates`)
- A file dropzone that accepts `.json` and `.yaml` files
- On drop/select: calls `uploadTemplate()`, shows success toast with the returned `template_id`
- A table below listing all uploaded templates with name, created date, and a "Trigger" button
- Clicking "Trigger" opens a modal to input the order context payload and calls `triggerExecution()`

### Step 7.5 — Build Page: Executions Dashboard (`/`)
- A live list of all workflow executions refreshing every 3 seconds
- Each row shows: execution ID (truncated), template name, status badge (color-coded), task progress bar (e.g., 3/6 tasks complete), elapsed time
- Status badge colors: Grey=PENDING, Blue=RUNNING, Yellow=PAUSED, Green=COMPLETED, Red=FAILED

### Step 7.6 — Build Component: `WorkflowGraph.tsx` (The Star Feature)
This is the most visually impressive component. Uses **React Flow** to render the DAG.

- **Input:** The list of task_executions for a given execution run
- **Node construction:** Convert each `TaskExecution` into a React Flow `Node` object with position, label, and a `data.status` field
- **Edge construction:** Read the `dependencies` from the workflow template and build React Flow `Edge` objects
- **Color mapping per status:**
  - `PENDING` → Grey node
  - `IN_PROGRESS` → Blue node with a pulsing animation
  - `COMPLETED` → Green node
  - `FAILED` → Red node
  - `AWAITING_APPROVAL` → Yellow node with a flashing "!" icon
  - `TERMINATED` → Dark node, strikethrough label

### Step 7.7 — Build Page: Execution Detail (`/executions/[id]`)
- `useEffect` + `setInterval` polling `getExecution(id)` every 1 second
- Renders `WorkflowGraph` with live data — nodes visually change color as the backend processes them
- Right panel shows raw task details: node_id, status, retry_count, output JSON, logs, timestamps
- **Control Panel:** Three buttons — Pause, Resume, Terminate — each calling the respective API and updating local state
- **Human Approval Panel:** If any task has status `AWAITING_APPROVAL`, render a prominent card with task details and an "Approve ✓" button

**Deliverable:** Open the dashboard. Upload `ecommerce_standard_v1.json`. Click Trigger. Watch the DAG graph animate in real-time as workers complete tasks. The `send_receipt` and `update_inventory` nodes should turn blue simultaneously (parallel execution). The fraud check node should turn yellow and wait for you to click Approve.

---

## Phase 8 — Integration Testing (End-to-End)

### Test Scenario 1 — Happy Path
1. Upload `ecommerce_standard_v1.json`
2. Trigger execution with `total_amount: 4497` (below fraud threshold)
3. Approve the `fraud_check` within 30 seconds
4. Verify all 6 nodes turn green
5. Verify `workflow_executions.status = COMPLETED` in the DB

### Test Scenario 2 — Payment Retry
1. Trigger a new execution
2. Watch the `charge_payment` node — it will turn red, then blue again (retry), then green
3. Verify `task_executions.retry_count = 1` or `2` in the DB

### Test Scenario 3 — Pause & Resume
1. Trigger an execution
2. Click Pause immediately after `validate_order` completes
3. Verify no further nodes turn blue
4. Click Resume — verify execution continues correctly

### Test Scenario 4 — Parallel Execution Proof
1. Trigger execution, let it run past `charge_payment`
2. Verify in the logs that `update_inventory` and `send_receipt` both go `IN_PROGRESS` within milliseconds of each other

### Test Scenario 5 — Terminate
1. Trigger execution
2. Click Terminate while `IN_PROGRESS`
3. Verify all `PENDING` nodes turn grey/terminated, global status = `TERMINATED`

---

## Phase 9 — Final Polish & Demo Prep

### Step 9.1 — Write `README.md`
A clean, 1-page quick start guide. Any judge or reviewer should be able to clone the repo and run the system in under 5 minutes.

### Step 9.2 — Ensure Docker Compose Covers Everything
Ideally, add the orchestrator and workers to `docker-compose.yml` as services so the entire system boots with a single command.

### Step 9.3 — Demo Script (Practice This)
1. Open the dashboard → show the empty executions list
2. Go to Templates → upload the JSON file → explain "Workflow-as-Code"
3. Trigger the Standard workflow → open the Execution Detail
4. Watch the DAG graph animate live → explain parallel execution
5. Approve the fraud check → explain Human-in-the-Loop
6. Show the completed green graph → explain fault tolerance
7. Trigger Flash Sale workflow simultaneously → show two workflows running at once

---

## Parallel Development Split (Team Assignment)

| Task | Owner | Can Start |
|---|---|---|
| Phase 0 (Scaffolding) | Lead | Day 1 Morning |
| Phase 1-2 (DB + Engine) | Lead | After Phase 0 |
| Phase 3-4 (Redis + API) | Lead | After Phase 2 |
| Phase 5 (Workers) | Teammate 1 | After Phase 3 is started |
| Phase 6 (Workflow JSONs) | Teammate 2 | After Phase 0 |
| Phase 7 (Frontend) | Teammate 2 | After Phase 4 API is stable |
| Phase 8 (Testing) | All | After Phase 7 |
