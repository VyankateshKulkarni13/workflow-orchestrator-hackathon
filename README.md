# Workflow Orchestrator
### E-Commerce Order Fulfillment System | NTAC:3NS-20

A centralized, DAG-based workflow orchestration engine built to coordinate distributed microservices for e-commerce order fulfillment.

## Quick Start (5 Minutes)

### Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Node.js 20+

### 1. Clone & Configure
```bash
git clone https://github.com/VyankateshKulkarni13/workflow-orchestrator-hackathon
cd workflow-orchestrator-hackathon
cp .env.example .env
```

### 2. Start Infrastructure
```bash
docker-compose up -d
```
Boots PostgreSQL on `:5432` and Redis on `:6379`.

### 3. Start the Orchestrator
```bash
cd orchestrator
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```
API Docs → http://localhost:8000/docs

### 4. Start the Workers (5 terminals)
```bash
cd workers
python order_validation_worker.py
python payment_worker.py
python inventory_worker.py
python shipping_worker.py
python notification_worker.py
```

### 5. Start the Dashboard
```bash
cd frontend
npm install && npm run dev
```
Dashboard → http://localhost:3000

---

## Documentation
All documentation lives in the `/docs` folder:
- [`PROJECT_DESCRIPTION.md`](docs/PROJECT_DESCRIPTION.md) — Complete project reference (single source of truth)
- [`IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) — Step-by-step development plan
- [`MICROSERVICES_REFERENCE.md`](docs/MICROSERVICES_REFERENCE.md) — Mock worker contracts & I/O specs
- [`system_architecture.md`](docs/system_architecture.md) — Architecture diagrams
- [`tech_stack_comparison.md`](docs/tech_stack_comparison.md) — Tech stack analysis

## Team
| Name | GitHub |
|---|---|
| Vyankatesh Kulkarni | [@VyankateshKulkarni13](https://github.com/VyankateshKulkarni13) |
| Aman J | [@AmanJ4588](https://github.com/AmanJ4588) |
| Surya | [@suryaroffical125-dev](https://github.com/suryaroffical125-dev) |
