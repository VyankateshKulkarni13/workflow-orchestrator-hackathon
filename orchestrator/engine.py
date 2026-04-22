"""
Core DAG orchestration engine.
Implements Kahn's Algorithm for cycle detection and async task dispatch.
"""

import asyncio
import traceback
from collections import defaultdict, deque
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from models import (
    WorkflowExecution,
    WorkflowTemplate,
    TaskExecution,
    ExecutionStatus,
    TaskStatus,
)
from redis_client import enqueue_task


def parse_dag(definition: dict) -> dict:
    """
    Validates a workflow definition dict and detects cycles using Kahn's Algorithm.
    Raises ValueError if cycle detected.
    """
    # Extract tasks (supports both flat and Airflow-style wrapper formats)
    if "dag" in definition and "tasks" in definition["dag"]:
        tasks = definition["dag"]["tasks"]
    else:
        tasks = definition.get("tasks")

    if not tasks or not isinstance(tasks, list):
        raise ValueError(
            "Workflow definition must have a 'tasks' list "
            "(at top level or inside a 'dag' key)."
        )

    # Build a map of task_id → task definition for quick lookup.
    # Supports both 'id' (our format) and 'task_id' (Airflow-style).
    task_map = {}
    for task in tasks:
        task_id = task.get("id") or task.get("task_id")
        if not task_id:
            raise ValueError(f"Every task must have an 'id' or 'task_id' field. Found: {task}")
        if task_id in task_map:
            raise ValueError(f"Duplicate task id found: '{task_id}'")
        task_map[task_id] = task

    node_ids = list(task_map.keys())

    # Build adjacency list and in-degree count
    # in_degree[node] = number of parents that must finish before this node runs
    in_degree = {node_id: 0 for node_id in node_ids}

    # adjacency[node] = list of children that depend on 'node'
    adjacency = defaultdict(list)

    for task in tasks:
        task_id = task.get("id") or task.get("task_id")
        # Support both 'depends_on' (our format) and 'dependencies' (Airflow/Surya's format)
        depends_on = task.get("depends_on") or task.get("dependencies") or []

        for parent_id in depends_on:
            if parent_id not in task_map:
                raise ValueError(
                    f"Task '{task_id}' depends on '{parent_id}', "
                    f"but '{parent_id}' is not defined in the workflow."
                )
            # Parent → Child edge
            adjacency[parent_id].append(task_id)
            in_degree[task_id] += 1

    # BFS Cycle Detection
    # TODO: consider recursive DFS for smaller DAGs if queue overhead becomes an issue
    queue = deque([node for node in node_ids if in_degree[node] == 0])
    processed_count = 0

    while queue:
        current = queue.popleft()
        processed_count += 1

        for child in adjacency[current]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    # If we couldn't process all nodes, there is a cycle
    if processed_count != len(node_ids):
        raise ValueError(
            f"Cycle detected in the workflow DAG! "
            f"Processed {processed_count}/{len(node_ids)} nodes. "
            f"Circular dependency found."
        )


    return {
        "nodes": node_ids,
        "adjacency": dict(adjacency),
        "task_map": task_map,
    }


async def run_next_tasks(execution_id: str, db: AsyncSession) -> None:
    """
    Evaluates the DAG based on current DB state and dispatches ready tasks.
    Called on initial trigger and subsequent webhook callbacks.
    """
    try:

        result = await db.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.execution_id == execution_id)
        )
        execution = result.scalar_one_or_none()

        if not execution:
            raise ValueError(f"WorkflowExecution '{execution_id}' not found in DB.")

        # If the workflow has been paused or terminated, do nothing
        if execution.status in (ExecutionStatus.PAUSED, ExecutionStatus.TERMINATED):
            return

        # Load the workflow template to get the original DAG definition
        template_result = await db.execute(
            select(WorkflowTemplate)
            .where(WorkflowTemplate.template_id == execution.template_id)
        )
        template = template_result.scalar_one_or_none()

        if not template:
            raise ValueError(f"WorkflowTemplate for execution '{execution_id}' not found.")

        # The full DAG definition (the parsed JSON the admin uploaded)
        definition = template.definition
        # Extract tasks from definition, supporting both flat and 'dag'-wrapped formats
        if "dag" in definition and "tasks" in definition["dag"]:
            raw_tasks = definition["dag"]["tasks"]
        else:
            raw_tasks = definition.get("tasks", [])
        # Build lookup using either 'id' or 'task_id' key
        tasks_definition = {(t.get("id") or t.get("task_id")): t for t in raw_tasks}


        task_result = await db.execute(
            select(TaskExecution)
            .where(TaskExecution.execution_id == execution_id)
        )
        all_task_execs = task_result.scalars().all()

        # Build a look-up: node_id -> TaskExecution row
        task_exec_map = {te.node_id: te for te in all_task_execs}
        
        print(f"[DEBUG] run_next_tasks: fetched {len(all_task_execs)} tasks for {execution_id}")
        for t in all_task_execs:
            print(f"[DEBUG] {t.node_id}: {t.status}")

        # Calculate runtime in-degrees
        # FIXME: querying all tasks on every tick is expensive. Need to optimize this with a 
        # dedicated materialized view or Redis cache state for massive DAGs.
        ready_nodes = []   # Nodes with runtime in-degree == 0

        for task_exec in all_task_execs:
            # Only consider tasks that are still waiting to run
            if task_exec.status != TaskStatus.PENDING:
                continue

            node_id = task_exec.node_id
            task_def = tasks_definition.get(node_id, {})
            # Support both 'depends_on' and 'dependencies' key names
            depends_on = task_def.get("depends_on") or task_def.get("dependencies") or []

            # Count how many parents are NOT yet COMPLETED
            blocking_parents = 0
            for parent_id in depends_on:
                parent_exec = task_exec_map.get(parent_id)
                if parent_exec is None or parent_exec.status != TaskStatus.COMPLETED:
                    blocking_parents += 1

            # If no parents are blocking this node, it is ready to run
            if blocking_parents == 0:
                ready_nodes.append((node_id, task_def, task_exec))


        if not ready_nodes:
            all_statuses = {te.status for te in all_task_execs}
            still_running = {TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_APPROVAL}

            if not all_statuses.intersection(still_running):
                final_status = (
                    ExecutionStatus.FAILED
                    if TaskStatus.FAILED in all_statuses
                    else ExecutionStatus.COMPLETED
                )
                await db.execute(
                    update(WorkflowExecution)
                    .where(WorkflowExecution.execution_id == execution_id)
                    .values(status=final_status, updated_at=datetime.utcnow())
                )
                await db.commit()
            return

        # Dispatch sequentially (asyncpg session lock limitation)
        for node_id, task_def, task_exec in ready_nodes:
            await _dispatch_single_task(
                node_id=node_id,
                task_def=task_def,
                task_exec=task_exec,
                global_context=execution.global_context or {},
                db=db,
            )
        await db.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.execution_id == execution_id)
            .values(status=ExecutionStatus.RUNNING, updated_at=datetime.utcnow())
        )
        await db.commit()

    except Exception as exc:
        err_detail = traceback.format_exc()
        print(f"[ENGINE ERROR] run_next_tasks crashed for execution {execution_id}:\n{err_detail}")

        try:
            await db.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.execution_id == execution_id)
                .values(status=ExecutionStatus.FAILED, updated_at=datetime.utcnow())
            )
            await db.commit()
        except Exception:
            pass 


async def _dispatch_single_task(
    node_id: str,
    task_def: dict,
    task_exec: TaskExecution,
    global_context: dict,
    db: AsyncSession,
) -> None:
    started_at = datetime.utcnow()

    task_input = {
        "global_context": global_context,
        "task_config": task_def.get("config", {}),
    }

    try:
        await db.execute(
            update(TaskExecution)
            .where(TaskExecution.task_id == task_exec.task_id)
            .values(
                status=TaskStatus.IN_PROGRESS,
                started_at=started_at,
                output={
                    "input_received": task_input,
                    "dispatched_at": started_at.isoformat(),
                },
                logs=f"[{started_at.isoformat()}] Task dispatched to worker queue."
            )
        )
        await db.commit()

        task_type = task_def.get("type", "MOCK_HTTP")

        if task_type == "HUMAN_APPROVAL":
            await db.execute(
                update(TaskExecution)
                .where(TaskExecution.task_id == task_exec.task_id)
                .values(
                    status=TaskStatus.AWAITING_APPROVAL,
                    logs=(
                        f"[{started_at.isoformat()}] Task dispatched to worker queue.\n"
                        f"[{datetime.utcnow().isoformat()}] Waiting for human approval."
                    )
                )
            )
            await db.commit()
            return  

        redis_payload = {
            "task_id": str(task_exec.task_id),
            "execution_id": str(task_exec.execution_id),
            "node_id": node_id,
            "task_type": task_type,
            "target": task_def.get("target", ""),
            "config": task_def.get("config", {}),
            "global_context": global_context,
        }

        queue_name = f"queue:{task_type}"
        await enqueue_task(queue_name, redis_payload)

        print(
            f"[ENGINE] Dispatched task '{node_id}' "
            f"(task_id={task_exec.task_id}) â†’ {queue_name}"
        )

    except Exception as exc:
        err_detail = traceback.format_exc()
        failed_at = datetime.utcnow()

        duration_seconds = (failed_at - started_at).total_seconds()

        print(f"[ENGINE ERROR] Failed to dispatch task '{node_id}':\n{err_detail}")

        try:
            await db.execute(
                update(TaskExecution)
                .where(TaskExecution.task_id == task_exec.task_id)
                .values(
                    status=TaskStatus.FAILED,
                    completed_at=failed_at,
                    logs=(
                        f"[{started_at.isoformat()}] Task dispatch attempted.\n"
                        f"[{failed_at.isoformat()}] FAILED after {duration_seconds:.3f}s.\n"
                        f"Error:\n{err_detail}"
                    ),
                )
            )
            await db.commit()
        except Exception:
            pass  


async def mark_task_completed(
    task_id: str,
    output: dict,
    db: AsyncSession,
) -> None:
    completed_at = datetime.utcnow()

    try:
        result = await db.execute(
            select(TaskExecution).where(TaskExecution.task_id == task_id)
        )
        task_exec = result.scalar_one_or_none()

        if not task_exec:
            raise ValueError(f"TaskExecution '{task_id}' not found in DB.")

        duration_seconds = None
        if task_exec.started_at:
            duration_seconds = (completed_at - task_exec.started_at).total_seconds()

        await db.execute(
            update(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .values(
                status=TaskStatus.COMPLETED,
                completed_at=completed_at,
                output=output,
                logs=(
                    f"{task_exec.logs or ''}\n"
                    f"[{completed_at.isoformat()}] Task COMPLETED successfully. "
                    f"Duration: {duration_seconds:.3f}s."
                ).strip(),
            )
        )
        await db.commit()

        # Open a fresh session to avoid SQLAlchemy identity map staleness
        # TODO: Refactor engine loop to use raw SQL returning clauses instead of ORM for these state transitions
        async with AsyncSessionLocal() as fresh_db:
            await run_next_tasks(str(task_exec.execution_id), fresh_db)

    except Exception as exc:
        err_detail = traceback.format_exc()
        print(f"[ENGINE ERROR] mark_task_completed failed for task {task_id}:\n{err_detail}")
        raise


async def mark_task_failed(
    task_id: str,
    error_message: str,
    db: AsyncSession,
) -> None:
    failed_at = datetime.utcnow()

    try:
        result = await db.execute(
            select(TaskExecution).where(TaskExecution.task_id == task_id)
        )
        task_exec = result.scalar_one_or_none()

        if not task_exec:
            raise ValueError(f"TaskExecution '{task_id}' not found.")

        duration_seconds = None
        if task_exec.started_at:
            duration_seconds = (failed_at - task_exec.started_at).total_seconds()

        await db.execute(
            update(TaskExecution)
            .where(TaskExecution.task_id == task_id)
            .values(
                status=TaskStatus.FAILED,
                completed_at=failed_at,
                retry_count=task_exec.retry_count + 1,
                logs=(
                    f"{task_exec.logs or ''}\n"
                    f"[{failed_at.isoformat()}] Task FAILED. "
                    f"Duration: {duration_seconds:.3f}s.\n"
                    f"Error: {error_message}"
                ).strip(),
            )
        )
        await db.commit()

        # Open a fresh session so engine reads the newly committed FAILED status
        async with AsyncSessionLocal() as fresh_db:
            await run_next_tasks(str(task_exec.execution_id), fresh_db)

    except Exception as exc:
        err_detail = traceback.format_exc()
        print(f"[ENGINE ERROR] mark_task_failed failed for task {task_id}:\n{err_detail}")
        raise

