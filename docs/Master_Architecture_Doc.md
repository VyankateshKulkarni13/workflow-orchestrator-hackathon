# EC Orchestrator: System Architecture & Technical Overview

## 1. Executive Summary
The **EC Orchestrator** is an enterprise-grade, highly scalable workflow orchestration engine designed to coordinate complex, distributed tasks across multiple microservices. Modern business processes—such as E-Commerce Order Fulfillment—often require coordinating payments, inventory, fraud checks, and shipping across disparate systems. 

The EC Orchestrator solves this by acting as a centralized "brain" that defines workflows as code using Directed Acyclic Graphs (DAGs). It relies on a fully decoupled, event-driven architecture, ensuring that the central orchestrator never directly executes business logic. Instead, it delegates tasks to independent microservices, manages strict state transitions, handles fault-tolerant retries, and exposes runtime operational controls.

---

## 2. Comprehensive System Architecture
The platform is built using a modern microservice-driven design pattern, entirely containerized via Docker. It consists of five distinct architectural layers:

### A. The Orchestration Engine (API Layer)
- **Technology:** Python 3.10, FastAPI, SQLAlchemy (AsyncPG)
- **Role:** The core controller of the system. It exposes highly performant, asynchronous RESTful APIs. 
- **Mechanism:** The Engine is strictly responsible for DAG evaluation and state management. It receives webhook callbacks from workers (`/api/v1/callbacks/task-complete`), updates the database, and dynamically evaluates the DAG at runtime to determine the next executable nodes. It ensures maximum throughput via asynchronous I/O (AsyncPG) rather than thread-blocking database calls.

### B. The State Store (Database Layer)
- **Technology:** PostgreSQL 15
- **Role:** The single source of truth. By utilizing a relational database, the engine guarantees ACID-compliant state transitions.
- **Schema Design:** 
  - `workflow_templates`: Stores the validated JSON DAG blueprints.
  - `workflow_executions`: Tracks the global state of a workflow run (`RUNNING`, `PAUSED`, `TERMINATED`).
  - `task_executions`: Unrolled individual nodes of a DAG run, tracking granular state, retry counts, and execution logs.
- **Stateless Engine:** Because all state is strictly normalized in PostgreSQL, the FastAPI engine itself is completely stateless, allowing infinite horizontal scaling of the API behind a load balancer.

### C. The Message Broker (Event Layer)
- **Technology:** Redis 7
- **Role:** The decoupled communication layer. 
- **Mechanism:** When the engine determines a task has zero pending dependencies, it does not invoke the worker directly via HTTP. Instead, it pushes a JSON payload onto a Redis queue (e.g., `queue:MOCK_HTTP`). This completely decouples the orchestrator from the workers, preventing network-blocking issues and allowing the queue to absorb massive spikes in traffic seamlessly.

### D. Distributed Task Workers (Execution Layer)
- **Technology:** Python (or any language capable of reading Redis and making HTTP calls)
- **Role:** Independent microservices representing domain boundaries (e.g., Payment Service, Inventory Service, Notification Service).
- **Mechanism:** Workers operate on a pull-based model. They continuously poll the Redis queue. Upon receiving a payload, they execute the domain-specific business logic, and then communicate the result back to the Orchestrator via standard HTTP Webhooks (`POST /callbacks/task-complete` or `task-failed`).

### E. The Control Plane (Frontend UI)
- **Technology:** Next.js (React 18), Tailwind CSS, `@xyflow/react`
- **Role:** A modern, real-time web dashboard providing operational visibility.
- **Mechanism:** It utilizes client-side polling to fetch real-time state from the FastAPI backend. It features interactive DAG visualization using React Flow, where nodes dynamically animate and change color based on database state transitions (Grey for Pending, Pulsing Blue for In-Progress, Green for Completed, Red for Failed, Yellow for Human Approval).

---

## 3. Core Features & Technical Implementation

### Workflow-as-Code (DAG Engine & Kahn's Algorithm)
Workflows are defined declaratively via JSON files outlining tasks and their `depends_on` relationships. 
- **Upload Validation:** During template upload, the engine parses the JSON and executes **Kahn's Algorithm** (Topological Sorting) to detect cyclic dependencies (e.g., A -> B -> A). If a cycle is detected, the API rejects the upload with a `422 Unprocessable Entity`.
- **Parallel Execution:** At runtime, the engine calculates the "in-degree" of every pending node. If a node's dependencies are met (in-degree = 0), it is instantly dispatched to Redis. If multiple nodes hit an in-degree of 0 simultaneously, they are dispatched in parallel.

### Decoupled Extensibility & 3rd Party Integration
The architecture natively supports extending to proprietary or external systems (e.g., Stripe, Azure Service Bus, external ERPs). Because the outbound push uses Redis and the inbound pull uses generic HTTP Webhooks, an external system requires zero proprietary SDKs to participate in a workflow. Furthermore, workflows support a `global_context` JSON payload, allowing dynamic API keys or customer IDs to be passed downstream to external workers.

### Fault Tolerance & Automated Retries
The system is built to expect failure in distributed microservices. If a worker encounters an error (simulated in our architecture via a random 10% failure rate in the Payment Worker), it triggers a `task-failed` webhook. The orchestrator intercepts this, checks the node's maximum retry configuration, increments the `retry_count`, and re-queues the message to Redis without failing the entire workflow.

### Advanced Operational Controls
The system provides deep runtime manipulation via strictly synchronized database updates:
- **Pause/Resume:** Invoking the `/pause` endpoint flags the execution in PostgreSQL. When the current in-flight workers finish and send their callbacks, the engine detects the `PAUSED` state and intentionally "starves" the pipeline, dispatching no further nodes.
- **Terminate:** Hard-kills a runaway execution, sweeping all `PENDING` or `IN_PROGRESS` tasks to a `TERMINATED` state to prevent ghost executions and maintain audit trail integrity.

### Human-in-the-Loop (HITL)
The engine natively supports manual interventions via the `HUMAN_APPROVAL` task type. When encountered, the engine updates the task state to `AWAITING_APPROVAL` and pauses that specific branch of the DAG. Parallel automated branches continue unhindered. The branch resumes only when an authorized administrator explicitly hits the `/approve` API endpoint.

---

## 4. E-Commerce Order Processing Scenario
To demonstrate the engine's capabilities, we implemented a robust `ecommerce_standard_v1.json` workflow mapping to a real-world scenario:

1. **`validate_order`**: Verifies stock availability and customer data.
2. **Parallel Split**: 
   - **`charge_payment`**: Automated microservice that charges the customer (includes auto-retry logic).
   - **`fraud_check`**: A `HUMAN_APPROVAL` task requiring an admin to manually verify the transaction in the dashboard.
3. **`update_inventory`**: A synchronization node that explicitly waits for *both* the payment to clear and the fraud check to be approved before continuing.
4. **`prepare_shipping`**: Triggers warehouse logistics.
5. **`send_confirmation`**: Dispatches the final email receipt to the customer.

---

## 5. Deployment & Containerization Strategy
The entire platform is defined via Infrastructure-as-Code using `docker-compose.yml`.
- Every component runs in isolated Docker containers utilizing Docker's internal DNS resolver for networking.
- **`orchestrator_postgres`**: Bound to internal port 5432.
- **`orchestrator_redis`**: Bound to internal port 6379.
- **`ec_orchestrator_api`**: Connects via `postgresql+asyncpg://` to the database.
- **`ec_orchestrator_workers`**: Shares the Redis network to pull jobs.
- **`ec_orchestrator_frontend`**: Next.js multi-stage build exposing port 3000 to the host.

This containerized approach allows the application to be deployed identically across local development machines, AWS EC2 instances, or Kubernetes clusters, guaranteeing identical behavior across environments.
