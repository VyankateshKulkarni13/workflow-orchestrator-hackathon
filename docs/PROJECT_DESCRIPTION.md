# Workflow Orchestrator — Project Description
### E-Commerce Order Fulfillment System
**Version:** 1.0.0 | **Status:** Active Development | **Hackathon:** NTAC:3NS-20

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Problem Statement](#2-problem-statement)
3. [Our Solution](#3-our-solution)
4. [Technology Stack](#4-technology-stack)
5. [System Architecture](#5-system-architecture)
6. [Core Concepts](#6-core-concepts)
7. [Database Schema](#7-database-schema)
8. [REST API Reference](#8-rest-api-reference)
9. [Workflow Definition Format](#9-workflow-definition-format)
10. [Operational Controls](#10-operational-controls)
11. [Project Structure](#11-project-structure)
12. [Local Development Setup](#12-local-development-setup)
13. [Branching Strategy](#13-branching-strategy)
14. [Team & Contributions](#14-team--contributions)

---

## 1. Project Overview

The **Workflow Orchestrator** is a centralized, event-driven orchestration engine designed to coordinate complex, multi-step business processes across a distributed network of independent microservices. The system acts as the "central brain" of the operation — it does not execute business logic itself, but rather directs, tracks, monitors, and controls other services that do.

The reference implementation domain is an **E-Commerce Order Fulfillment Pipeline**, where a customer's order must traverse multiple independent services (payment, inventory, shipping, notification) in a reliable, observable, and fault-tolerant way from placement to delivery.

---

## 2. Problem Statement

Modern e-commerce systems are built on distributed microservices. Without a coordinator, these services either:

- **Become tightly coupled (Choreography Anti-Pattern):** Each service fires events at the next service in a peer-to-peer chain. This creates an unmaintainable "spaghetti" network where no single entity knows the global order status, making rollbacks, retries, and visibility nearly impossible.
- **Revert to monoliths:** All logic is embedded in one codebase, creating a single point of failure.

The problem demands a system that can:
- Define business workflows declaratively (without code deployments)
- Execute them reliably across multiple independent services
- Handle failures, retries, and conditional logic gracefully
- Provide real-time operational visibility and control

---

## 3. Our Solution

We implement the **Orchestration Pattern**: a centralized `Orchestrator Service` that is the **only** entity that knows and commands the entire flow. Individual microservices (workers) are stateless and "dumb" — they receive a task, execute it, and report back. They have no knowledge of the broader workflow.

### Key Capabilities

| Capability | Description |
|---|---|
| **Workflow-as-Code** | Business processes are defined as JSON/YAML files uploaded by admins. No code redeployment needed. |
| **DAG-Based Execution** | Workflows are Directed Acyclic Graphs allowing parallel branching and conditional logic. |
| **Async Orchestration** | Non-blocking execution; the engine can manage thousands of concurrent workflows. |
| **Built-in Task Types** | `MOCK_HTTP`, `MESSAGE_QUEUE`, and `HUMAN_APPROVAL` task types supported out of the box. |
| **Fault Tolerance** | Per-task retry policies with configurable backoff. |
| **Operational Controls** | Pause, Resume, Retry, and Terminate workflows at runtime via the UI. |
| **Real-Time Dashboard** | A live React Flow-powered graph that animates the workflow execution in real-time. |
| **Human-in-the-Loop** | Specific tasks can require admin approval before the workflow continues. |

---

## 4. Technology Stack

### Backend — Orchestrator Engine
| Component | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | Fastest development speed; ideal for DAG/graph algorithm implementation |
| **Web Framework** | FastAPI | Native `async/await` for non-blocking I/O; auto-generates OpenAPI/Swagger docs |
| **ORM** | SQLAlchemy (async) | Async-compatible ORM with full PostgreSQL JSONB support |
| **DB Driver** | `asyncpg` | High-performance async PostgreSQL driver |
| **Data Validation** | Pydantic v2 | Strict schema validation for all incoming workflow JSON/YAML definitions |
| **YAML Parsing** | `PyYAML` | Parses uploaded YAML workflow definitions into Python dictionaries |

### Infrastructure
| Component | Technology | Rationale |
|---|---|---|
| **Database** | PostgreSQL 15 | ACID-compliant relational DB with native JSONB for storing flexible DAG blueprints |
| **Message Broker** | Redis 7 | Ultra-fast in-memory queue for decoupling the orchestrator from task worker execution |
| **Containerization** | Docker + Docker Compose | Single-command local environment setup for Postgres, Redis, and all services |

### Frontend — Monitoring Dashboard
| Component | Technology | Rationale |
|---|---|---|
| **Framework** | Next.js 14 (React) | Industry standard; enables server-side rendering and fast client-side state management |
| **DAG Visualization** | React Flow | Purpose-built library for rendering interactive, animated node-based graphs |
| **Styling** | Tailwind CSS | Rapid, utility-first styling enabling a premium glassmorphism dark-mode UI |
| **HTTP Client** | Axios | Clean async HTTP client for communicating with the FastAPI backend |

---

## 5. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FRONTEND (Next.js)                              │
│   ┌──────────────────┐       ┌───────────────────────────────┐      │
│   │ Template Uploader│       │   Monitoring / Approval        │      │
│   │ (JSON/YAML form) │       │   Dashboard (React Flow DAG)   │      │
│   └────────┬─────────┘       └──────────────┬────────────────┘      │
└────────────│──────────────────────────────────|────────────────────-─┘
             │ POST /templates                  │ GET /executions/{id}
             │                                  │ POST /tasks/{id}/approve
             ▼                                  ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR ENGINE (FastAPI)                       │
│  ┌──────────────┐  ┌────────────────┐  ┌───────────────────────────┐ │
│  │ Template      │  │ DAG Traversal  │  │ Webhook Listener          │ │
│  │ Manager       │  │ Engine         │  │ /callbacks/task-complete   │ │
│  │               │  │ (Topological   │  │                           │ │
│  │ Parses JSON/  │  │  Sort)         │  │ Receives success/failure   │ │
│  │ YAML & stores │  │                │  │ from workers & re-evaluates│ │
│  │ in Postgres   │  │ Dispatches to  │  │ the DAG                   │ │
│  └──────┬────────┘  │ Redis or holds │  └──────────────┬────────────┘ │
│         │            │ for HUMAN      │                 │              │
│         │            │ APPROVAL       │                 │              │
│         ▼            └───────┬────────┘                 │              │
│  ┌──────────────────────────────────────────────────────▼──────────┐  │
│  │                     State Manager                               │  │
│  │           (ACID Read/Write to PostgreSQL)                       │  │
│  └────────────────────────────────┬─────────────────────────────────┘ │
└───────────────────────────────────│────────────────────────────────────┘
                                    │
                ┌───────────────────┼──────────────────────┐
                ▼                   ▼                       ▼
        ┌──────────────┐   ┌──────────────┐       ┌──────────────────┐
        │  PostgreSQL  │   │   Redis      │       │  Task Workers    │
        │              │   │   Queue      │       │ (Python Scripts) │
        │ workflow_    │   │              │       │                  │
        │  templates   │   │ Publish →    │       │ payment_worker   │
        │ workflow_    │   │  Workers     │       │ inventory_worker │
        │  executions  │   │  consume     │       │ shipping_worker  │
        │ task_        │   │  from queue  │       │ notification_    │
        │  executions  │   │              │       │   worker         │
        └──────────────┘   └──────────────┘       └────────┬─────────┘
                                                           │
                                              POST /callbacks/task-complete
```

---

## 6. Core Concepts

### 6.1 Directed Acyclic Graph (DAG)
A workflow is represented as a DAG where:
- **Nodes** = individual tasks (e.g., `charge_payment`, `update_inventory`)
- **Edges** = dependency relationships (e.g., `update_inventory` depends on `charge_payment`)
- **Acyclic** = there can be no loops; the workflow must always progress forward to completion

### 6.2 Topological Sorting (The Algorithm)
The core engine uses **topological sort with in-degree tracking** to determine which tasks can run:

1. Parse the workflow JSON into an adjacency list (dependency graph)
2. Calculate the **in-degree** of each node (number of unresolved dependencies)
3. All nodes with `in-degree = 0` are immediately dispatched (in parallel)
4. When a task completes → decrement in-degree of all dependent nodes
5. Any node whose in-degree drops to `0` is immediately queued
6. Repeat until all nodes are `COMPLETED` or one is `FAILED`

This naturally enables **parallel branch execution** — the e-commerce pipeline sends inventory and notification emails simultaneously as soon as payment completes.

### 6.3 Task Types

| Type | Behavior |
|---|---|
| `MOCK_HTTP` | The orchestrator pushes a JSON payload to Redis; the target worker picks it up, executes, and calls back the webhook |
| `MESSAGE_QUEUE` | The orchestrator publishes a message to a named Redis channel for event-driven consumption |
| `HUMAN_APPROVAL` | The orchestrator marks the task as `AWAITING_APPROVAL` and suspends that branch; resumes only after an admin approves via the dashboard |

### 6.4 Retry Policy
Each task can define a `retry_policy` in its JSON definition:
```json
"retry_policy": {
  "max_attempts": 3,
  "backoff_ms": 1000
}
```
If a worker fails, the engine re-queues the task with an exponential backoff before marking it permanently `FAILED`.

---

## 7. Database Schema

### Table: `workflow_templates`
Stores the raw JSON/YAML workflow blueprints uploaded by admins.

| Column | Type | Description |
|---|---|---|
| `template_id` | UUID (PK) | Unique identifier |
| `name` | VARCHAR | Human-readable workflow name |
| `description` | TEXT | Optional description |
| `definition` | JSONB | The complete workflow DAG structure |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last modification timestamp |

### Table: `workflow_executions`
Tracks every live/completed instance of a workflow being run.

| Column | Type | Description |
|---|---|---|
| `execution_id` | UUID (PK) | Unique runtime identifier |
| `template_id` | UUID (FK) | References `workflow_templates` |
| `status` | ENUM | `PENDING`, `RUNNING`, `PAUSED`, `COMPLETED`, `FAILED`, `TERMINATED` |
| `global_context` | JSONB | Runtime payload (order details, customer info, etc.) |
| `created_at` | TIMESTAMP | Start timestamp |
| `updated_at` | TIMESTAMP | Last state change timestamp |

### Table: `task_executions`
Tracks the state of every individual node within a given workflow run.

| Column | Type | Description |
|---|---|---|
| `task_id` | UUID (PK) | Unique task identifier |
| `execution_id` | UUID (FK) | References `workflow_executions` |
| `node_id` | VARCHAR | The task key from the JSON (e.g., `charge_payment`) |
| `status` | ENUM | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `AWAITING_APPROVAL`, `TERMINATED` |
| `retry_count` | INTEGER | Number of retries attempted |
| `output` | JSONB | Task result output from the worker |
| `logs` | TEXT | Any error messages or execution logs |
| `started_at` | TIMESTAMP | Task start time |
| `completed_at` | TIMESTAMP | Task completion time |

---

## 8. REST API Reference

### Templates
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/templates` | Upload a new JSON/YAML workflow blueprint |
| `GET` | `/api/v1/templates` | List all registered workflow templates |
| `GET` | `/api/v1/templates/{template_id}` | Fetch a specific template |

### Executions
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/executions` | Trigger a new workflow execution |
| `GET` | `/api/v1/executions` | List all workflow executions |
| `GET` | `/api/v1/executions/{execution_id}` | Fetch real-time status + all task states |
| `POST` | `/api/v1/executions/{execution_id}/pause` | Pause a running workflow |
| `POST` | `/api/v1/executions/{execution_id}/resume` | Resume a paused workflow |
| `POST` | `/api/v1/executions/{execution_id}/terminate` | Terminate a running workflow |

### Tasks
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/tasks/{task_id}/approve` | Approve a `HUMAN_APPROVAL` task |
| `POST` | `/api/v1/tasks/{task_id}/retry` | Manually retry a failed task |

### Webhooks (Internal — used by Workers)
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/callbacks/task-complete` | Worker reports successful task completion |
| `POST` | `/api/v1/callbacks/task-failed` | Worker reports task failure |

---

## 9. Workflow Definition Format

A workflow is defined as a JSON or YAML file. The following is the **canonical e-commerce order fulfillment workflow**:

```json
{
  "workflow_id": "ecommerce_standard_v1",
  "name": "Standard E-Commerce Order Fulfillment",
  "description": "Orchestrates the complete lifecycle of an online order from placement to delivery.",
  "tasks": [
    {
      "id": "validate_order",
      "type": "MOCK_HTTP",
      "name": "Validate Order Details",
      "target": "order-worker/validate",
      "dependencies": []
    },
    {
      "id": "charge_payment",
      "type": "MOCK_HTTP",
      "name": "Process Payment",
      "target": "payment-worker/charge",
      "dependencies": ["validate_order"],
      "retry_policy": { "max_attempts": 3, "backoff_ms": 1000 }
    },
    {
      "id": "fraud_check",
      "type": "HUMAN_APPROVAL",
      "name": "Manual Fraud Review (High-Value Orders)",
      "dependencies": ["validate_order"]
    },
    {
      "id": "update_inventory",
      "type": "MESSAGE_QUEUE",
      "name": "Reserve Inventory",
      "topic": "inventory_updates",
      "dependencies": ["charge_payment", "fraud_check"]
    },
    {
      "id": "dispatch_shipping",
      "type": "MESSAGE_QUEUE",
      "name": "Dispatch to Courier",
      "topic": "shipping_dispatch",
      "dependencies": ["update_inventory"]
    },
    {
      "id": "send_receipt",
      "type": "MOCK_HTTP",
      "name": "Send Order Confirmation Email",
      "target": "notification-worker/email",
      "dependencies": ["charge_payment"]
    }
  ]
}
```

**Execution Flow for the Above Workflow:**
```
validate_order
     ├────────────► charge_payment ──────────────► send_receipt
     │                     │
     │                     └──────┐
     │                            ▼
     └──────► fraud_check ──► update_inventory ──► dispatch_shipping
```

Note: `send_receipt` and `update_inventory` both unblock after `charge_payment` — they run **in parallel**.

---

## 10. Operational Controls

### Pause / Resume
- **Pause:** The engine sets `workflow_executions.status = PAUSED`. The engine stops fetching eligible nodes from the graph.  In-flight existing tasks on Redis are allowed to finish, but no new nodes are dispatched.
- **Resume:** Status reverts to `RUNNING`. The engine re-evaluates the DAG and dispatches all nodes whose in-degree is now `0`.

### Terminate
- The engine immediately sets all `PENDING` task nodes to `TERMINATED` and the global execution to `TERMINATED`.
- In-flight Redis tasks are abandoned (workers will attempt to call back but the Orchestrator will discard the event).

### Human Approval
- When the engine encounters a `HUMAN_APPROVAL` node, it marks the task as `AWAITING_APPROVAL` and parks that branch.
- The dashboard surfaces a prominent "Approve" button for that task.
- Upon admin approval via `POST /api/v1/tasks/{task_id}/approve`, the engine marks it `COMPLETED` and continues the DAG.

### Retry
- Automatic: Governed by the `retry_policy` in the task definition.
- Manual: Admin can force a retry of a `FAILED` task via `POST /api/v1/tasks/{task_id}/retry`.

---

## 11. Project Structure

```
workflow-orchestrator-hackathon/
│
├── docker-compose.yml              # Boots PostgreSQL and Redis
├── .env.example                    # Environment variable template
├── README.md                       # Quick start guide
│
├── docs/                           # Documentation
│   ├── system_architecture.md      # Architecture diagrams
│   ├── tech_stack_comparison.md    # Tech stack analysis
│   └── PROJECT_DESCRIPTION.md     # This file (Single Source of Truth)
│
├── orchestrator/                   # Backend: FastAPI Engine
│   ├── main.py                     # App entrypoint + server config
│   ├── database.py                 # Async SQLAlchemy connection pool
│   ├── models.py                   # ORM models for all 3 DB tables
│   ├── engine.py                   # Core DAG traversal algorithm
│   ├── redis_client.py             # Redis connection wrapper
│   ├── requirements.txt            # Python dependencies
│   └── routers/
│       ├── templates.py            # /api/v1/templates endpoints
│       ├── executions.py           # /api/v1/executions endpoints
│       ├── tasks.py                # /api/v1/tasks endpoints
│       └── callbacks.py            # /api/v1/callbacks (webhooks)
│
├── workers/                        # Distributed Task Workers
│   ├── base_worker.py              # Shared Redis listener logic
│   ├── payment_worker.py           # Simulates payment processing
│   ├── inventory_worker.py         # Simulates inventory reservation
│   ├── shipping_worker.py          # Simulates shipping dispatch
│   └── notification_worker.py     # Simulates email confirmation
│
├── workflows/                      # Sample Workflow Definitions (YAML/JSON)
│   └── ecommerce_standard_v1.json  # The canonical e-commerce workflow
│
└── frontend/                       # Next.js Dashboard
    ├── src/
    │   ├── app/                    # Next.js App Router pages
    │   │   ├── page.tsx            # Dashboard home (execution list)
    │   │   ├── executions/
    │   │   │   └── [id]/page.tsx   # Execution detail + React Flow graph
    │   │   └── templates/
    │   │       └── page.tsx        # Template upload form
    │   ├── components/
    │   │   ├── WorkflowGraph.tsx   # React Flow DAG visualization
    │   │   ├── TaskNode.tsx        # Custom node component (color-coded)
    │   │   └── ControlPanel.tsx    # Pause/Resume/Terminate buttons
    │   └── lib/
    │       └── api.ts              # Axios API client (all endpoints)
    └── package.json
```

---

## 12. Local Development Setup

### Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Node.js 20+

### Step 1: Start Infrastructure
```bash
docker-compose up -d
```
This boots PostgreSQL on port `5432` and Redis on port `6379`.

### Step 2: Start the Orchestrator Backend
```bash
cd orchestrator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API docs available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### Step 3: Start the Worker Services
```bash
# In separate terminal windows
cd workers
python payment_worker.py
python inventory_worker.py
python shipping_worker.py
python notification_worker.py
```

### Step 4: Start the Frontend Dashboard
```bash
cd frontend
npm install
npm run dev
```
Dashboard available at: [http://localhost:3000](http://localhost:3000)

---

## 13. Branching Strategy

| Branch | Who Can Push | Purpose |
|---|---|---|
| `main` | `VyankateshKulkarni13` (Admin) only | Production-ready, error-free code only |
| `feature/*` | All contributors | Active development branches |

**Contributor Workflow:**
```bash
git checkout -b feature/my-feature
# ... write code ...
git push origin feature/my-feature
# Open a Pull Request → Admin reviews → merges to main
```

---

## 14. Team & Contributors

| Name | GitHub | Role |
|---|---|---|
| Vyankatesh Kulkarni | `VyankateshKulkarni13` | Lead / Admin |
| Aman J | `AmanJ4588` | Contributor |
| Surya | `suryaroffical125-dev` | Contributor |

**Repository:** [https://github.com/VyankateshKulkarni13/workflow-orchestrator-hackathon](https://github.com/VyankateshKulkarni13/workflow-orchestrator-hackathon)
