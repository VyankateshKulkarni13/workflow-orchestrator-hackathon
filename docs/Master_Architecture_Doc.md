# EC Orchestrator: System Architecture & Technical Overview

## 1. Executive Summary
The **EC Orchestrator** is an enterprise-grade, highly scalable workflow orchestration engine designed to manage and coordinate distributed tasks across multiple microservices. Built primarily for complex business processes like E-Commerce Order Fulfillment, it allows organizations to define workflows as code (Directed Acyclic Graphs), execute them reliably in parallel, and monitor them in real-time. 

The system relies on a fully decoupled, event-driven architecture, ensuring that the central orchestrator never directly executes business logic. Instead, it acts as the "brain," delegating tasks to independent microservices and managing state, retries, and operational controls.

---

## 2. High-Level Architecture
The architecture follows a microservice-driven design pattern, completely containerized using Docker. It consists of five primary layers:

### A. The Engine (Orchestrator API)
- **Technology:** Python, FastAPI, SQLAlchemy (AsyncPG)
- **Role:** The core brain of the system. It exposes RESTful APIs for template management, execution triggering, and operational controls (pause/resume). It evaluates the DAG (Directed Acyclic Graph) at runtime to determine which tasks are ready to run, ensuring parallel execution where dependencies allow.

### B. The State Store (Database)
- **Technology:** PostgreSQL
- **Role:** Maintains ACID-compliant persistence for Workflow Templates, Execution States, and Task Audit Logs. It acts as the single source of truth for the system, allowing the engine to be entirely stateless and horizontally scalable.

### C. The Message Broker
- **Technology:** Redis
- **Role:** The decoupled communication layer. When the engine determines a task is ready to run, it publishes a JSON payload to a Redis queue. This prevents the orchestrator from blocking and allows infinite horizontal scaling of workers.

### D. The Task Workers (Microservices)
- **Technology:** Python (or any language capable of reading Redis and making HTTP calls)
- **Role:** Independent microservices (e.g., Payment Service, Inventory Service, Notification Service) that listen to the Redis queue. They execute the actual business logic and then communicate back to the Orchestrator via standard HTTP Webhooks.

### E. The Control Plane (Frontend UI)
- **Technology:** Next.js (React), Tailwind CSS, React Flow
- **Role:** A modern, real-time web dashboard providing full visibility into the system. It visualizes the DAGs in real-time, monitors execution progress, and provides an interface for Human-in-the-Loop approvals.

---

## 3. Core Features & Capabilities

### Workflow-as-Code (DAG Engine)
Workflows are defined as declarative JSON files outlining tasks and their dependencies (`depends_on`). The engine parses this JSON and utilizes **Kahn's Algorithm** for cycle detection prior to database insertion. At runtime, it dynamically calculates in-degrees to dispatch independent tasks simultaneously, enabling true **Parallel Execution**.

### Decoupled Extensibility
Because the system uses Redis for outbound messaging and HTTP Webhooks (`POST /callbacks/task-complete`) for inbound status updates, integrating a 3rd-party external system (like Stripe or an external ERP) requires zero proprietary SDKs. Any system that can receive an event and make a REST call can participate in a workflow.

### Advanced Operational Controls
The system provides deep runtime manipulation capabilities:
- **Pause/Resume:** Workflows can be halted mid-flight. The engine intelligently starves the pipeline, ensuring no new tasks are dispatched until resumed.
- **Terminate:** Hard-kills a runaway execution, sweeping all pending tasks to a terminal state to prevent ghost executions.
- **Automated Retries:** Fault tolerance is built-in. If a microservice fails (simulated in our Payment Worker), the orchestrator automatically intercepts the failure and re-queues the task based on defined retry limits.

### Human-in-the-Loop (HITL)
Workflows natively support manual interventions. A `HUMAN_APPROVAL` task pauses its specific branch of the DAG until an authorized user explicitly approves the action via the UI or API (e.g., a manager approving a high-risk fraud check), while parallel automated branches continue unhindered.

---

## 4. Execution Lifecycle & Data Flow
1. **Definition:** An administrator uploads a JSON template. The engine validates the DAG and stores it.
2. **Trigger:** An execution is initialized. The engine creates an Execution record and unrolls the DAG into individual Task records in the database.
3. **Evaluation:** The engine identifies tasks with zero pending dependencies and publishes them to Redis.
4. **Processing:** Workers consume the Redis messages, process the business logic, and POST a success/failure callback back to the Orchestrator's API.
5. **Progression:** The engine updates the database, re-evaluates the DAG, and dispatches the next wave of tasks. This loop continues until all nodes reach a terminal state.

---

## 5. Deployment & Scalability
The entire platform is defined via Infrastructure-as-Code using `docker-compose.yml`. 
- **Containerization:** Every component (Database, Redis, Engine, Workers, Frontend) runs in isolated Docker containers with internal DNS networking.
- **Scalability:** Because the Engine is stateless, an organization can spin up multiple Orchestrator API containers behind a load balancer to handle millions of requests, while scaling the Task Workers independently based on queue length.
