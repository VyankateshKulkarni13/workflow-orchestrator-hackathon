"""
Phase 1 Validation Script
Run this once to confirm DB connection works and tables are created.
"""
import asyncio
from database import create_tables, engine
from models import WorkflowTemplate, WorkflowExecution, TaskExecution
from sqlalchemy import text

async def validate():
    print("Step 1: Creating tables in PostgreSQL...")
    await create_tables()
    print("        Tables created successfully.\n")

    print("Step 2: Verifying tables exist in the database...")
    async with engine.connect() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ))
        tables = [row[0] for row in result]
        print(f"        Tables found in DB: {tables}\n")

    expected = {"workflow_templates", "workflow_executions", "task_executions"}
    if expected.issubset(set(tables)):
        print("[PASS] Phase 1 PASSED -- All 3 tables exist in PostgreSQL. Database layer is fully operational.")
    else:
        print("[FAIL] Phase 1 FAILED -- Some tables are missing.")

    await engine.dispose()

asyncio.run(validate())
