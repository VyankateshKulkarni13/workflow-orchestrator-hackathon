# System Architecture: Workflow Orchestrator

This document outlines the system architecture for the DAG-based Workflow Orchestrator, specifically tailored for an E-Commerce Order Fulfillment process.

## 1. High-Level System Architecture Diagram

```mermaid
flowchart TB
    %% Actors
    Admin([Admin / Operations])
    Store([E-Commerce Storefront])

    %% UI and Gateway
    subgraph Frontend ["Frontend UI (Next.js)"]
        Dashboard[Monitoring & Approval Dashboard]
        Builder[Template Uploader]
    end

    %% Central Brain
    subgraph CoreEngine ["Central Orchestrator (FastAPI + Asyncio)"]
        API[REST API Gateway]
        TempMan[Template Manager]
        Engine[DAG Traversal Engine\n(Topological Sort)]
        StateMan[State Manager]
        Webhook[Webhook Listener]
    end

    %% Persistence
    subgraph DataLayer ["Persistence Layer"]
        DB[(PostgreSQL)]
        %% Details: workflow_templates, workflow_executions, task_executions
    end
    
    %% Message Bus
    subgraph Broker ["Message Broker"]
        Redis([Redis Queue])
    end

    %% Distributed Workers
    subgraph Workers ["Task Workers (Python Microservices)"]
        W1[Payment Worker]
        W2[Inventory Worker]
        W3[Shipping Worker]
        W4[Notification Worker]
    end

    %% Relations
    Admin -->|Uploads JSON/YAML| Builder
    Admin -->|Pauses/Resumes/Terminates| Dashboard
    Admin -.->|Manual Approval (Human-in-loop)| Dashboard
    
    Builder -->|POST /templates| API
    
    Dashboard -->|GET status \n POST /tasks/{id}/approve| API
    Store -->|POST /executions| API

    API --> TempMan
    TempMan -->|Save JSONB Blueprint| DB

    API --> Engine
    Engine -->|Read/Write State| StateMan
    StateMan <-->|ACID Transactions| DB
    
    Engine -->|Publish Task (Async)| Redis
    Engine -.->|Suspend for HUMAN_APPROVAL| StateMan
    
    Redis -->|Consume Task| W1
    Redis -->|Consume Task| W2
    Redis -->|Consume Task| W3
    Redis -->|Consume Task| W4

    W1 -.->|Task Complete Hook| Webhook
    W2 -.->|Task Complete Hook| Webhook
    W3 -.->|Task Complete Hook| Webhook
    W4 -.->|Task Complete Hook| Webhook
    
    Webhook --> Engine
```

## 2. Complete Workflow Description

The system orchestrates a set of logical steps to fulfill an online order by utilizing a decoupled microservice architecture. 

**Step-by-Step Execution Workflow:**

1. **Workflow-as-Code Definition (The Setup):**
   An Administrator logs into the frontend to submit a JSON/YAML file detailing the workflow. The **Template Manager** parses and saves this blueprint into the `workflow_templates` table in PostgreSQL.

2. **Workflow Initiation:**
   The storefront sends a `POST /api/v1/executions` containing a `template_id` and context payload.

3. **Parsing & DB Initialization:**
   The State Manager pulls the template. It logs a new run in the `workflow_executions` table (`PENDING`) and registers all individual task nodes into the `task_executions` table. The DAG Engine maps out all dependencies.

4. **Task Dispatching (In-Degree Zero):**
   The Engine looks for tasks with an "in-degree" of 0 (no missing dependencies). Depending on the **Type**, it handles them differently:
   * **Worker-based Tasks (e.g., `MOCK_HTTP`, `MESSAGE_QUEUE`):** The Engine pushes a message to the **Redis Queue** addressed to the specific worker target and marks the task `IN_PROGRESS` in the database.
   * **Human-in-the-Loop (`HUMAN_APPROVAL`):** The Engine suspends this branch of the DAG. It pushes a notification to the dashboard and waits indefinitely without using Redis.

5. **Human Approval Intervention (Manual Step):**
   For nodes requiring a human (e.g., manual fraud check for high-value orders), an Admin reviews it on the dashboard and clicks "Approve". This sends a `POST /api/v1/tasks/{task_id}/approve` to the Orchestrator, which marks the task as `COMPLETED` and tells the Engine to continue.

6. **Task Execution (Workers):**
   For queued tasks, a specialized worker (e.g., Payment) picks up the Redis message, executes its logic, and sends a payload back to the **Webhook Listener** (`POST /api/v1/callbacks/task-complete`).

7. **DAG Resolution:**
   The Webhook tells the State Manager to mark the task as `COMPLETED`. The Engine re-evaluates the graph representing parallel execution gracefully.

8. **Edge Cases & Retries:**
   If a worker fails, the Engine checks the JSON's `retry_policy` and re-queues until exhausted.

9. **Visibility & Operational Controls:**
   Administrators can not only **Pause** and **Resume** but also instantly **Terminate** rogue executions via the dashboard, turning all pending nodes to `TERMINATED`.
