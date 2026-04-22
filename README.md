# Workflow Orchestrator
### Centralized DAG-based E-Commerce Fulfillment | NTAC:3NS-20

A robust, high-performance workflow orchestration engine designed to coordinate distributed microservices for complex e-commerce order fulfillment lifecycles.

## 🚀 Overview

This system allows administrators to define fulfillment logic as Directed Acyclic Graphs (DAGs). Each node in the graph represents a specific task (e.g., Payment, Inventory, Shipping) handled by distributed workers. The engine ensures tasks are executed in the correct order, manages state transitions, and supports human-in-the-loop approvals.

## 🛠 Tech Stack

- **Backend**: FastAPI (Python 3.10+)
- **Database**: PostgreSQL with SQLAlchemy (Async)
- **Queue**: Redis
- **Frontend**: Next.js 15+ (App Router) with Tailwind CSS
- **Containerization**: Docker & Docker Compose

## 📦 Quick Start

The entire stack is containerized for a seamless setup experience.

### 1. Start the System
```bash
docker compose up -d --build
```

This command initializes:
- **PostgreSQL**: Workflow state and history
- **Redis**: Task queue and messaging
- **Orchestrator API**: Core engine logic (Port 8000)
- **Workers**: Unified worker pool for fulfillment tasks
- **Frontend**: Real-time monitoring dashboard (Port 3000)

### 2. Access the Dashboard
Open [http://localhost:3000](http://localhost:3000) to monitor executions.

### 3. API Documentation
Interactive Swagger documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

## 📂 Project Structure

```text
├── orchestrator/      # Core DAG engine and FastAPI routers
├── workers/           # Task handlers and Redis listeners
├── frontend/          # Next.js monitoring dashboard
├── docs/              # Technical architecture documentation
└── workflows/         # Example DAG templates (JSON)
```

## 📖 Documentation

For a deep dive into the system design, event-driven architecture, and state machine logic, see the [Master Architecture Document](docs/Master_Architecture_Doc.md).

## 👥 Team
- **Vyankatesh Kulkarni** ([@VyankateshKulkarni13](https://github.com/VyankateshKulkarni13))
- **Aman J** ([@AmanJ4588](https://github.com/AmanJ4588))
- **Surya** ([@suryaroffical125-dev](https://github.com/suryaroffical125-dev))
