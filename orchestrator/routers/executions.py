"""
Endpoints for triggering and monitoring workflow executions.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from engine import run_next_tasks
from models import (
    ExecutionStatus,
    TaskExecution,
    TaskStatus,
    WorkflowExecution,
    WorkflowTemplate,
)
from schemas import (
    ExecutionCreateRequest,
    ExecutionDetailResponse,
    ExecutionSummaryResponse,
    MessageResponse,
    TaskStateResponse,
)

router = APIRouter(prefix="/api/v1/executions", tags=["Executions"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session



def _fmt(dt) -> str | None:
    return dt.isoformat() if dt else None


@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def trigger_execution(
    payload: ExecutionCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger a new workflow execution from a registered template.

    Steps:
    1. Verify the template exists.
    2. Create a WorkflowExecution row (status=PENDING).
    3. Create a TaskExecution row for every node in the DAG (status=PENDING).
    4. Call engine.run_next_tasks() — Kahn's Algorithm fires immediately.
    5. Return execution_id to the caller.
    """
    # Step 1: Verify the template exists
    template_result = await db.execute(
        select(WorkflowTemplate).where(WorkflowTemplate.template_id == payload.template_id)
    )
    template = template_result.scalar_one_or_none()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{payload.template_id}' not found."
        )

    # Step 2: Create the WorkflowExecution
    execution = WorkflowExecution(
        template_id=template.template_id,
        status=ExecutionStatus.PENDING,
        global_context=payload.global_context or {},
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    # Step 3: Create a TaskExecution for every node defined in the DAG
    # Extract task list — engine standard is a flat {"tasks": [...]} with "id" fields
    tasks_definition = template.definition.get("tasks", [])
    for task_def in tasks_definition:
        node_id = task_def.get("id") or task_def.get("task_id")
        if not node_id:
            continue
        task_exec = TaskExecution(
            execution_id=execution.execution_id,
            node_id=node_id,
            status=TaskStatus.PENDING,
        )
        db.add(task_exec)

    await db.commit()

    # Step 4: Fire the DAG engine — this call is non-blocking from the caller's perspective
    # It dispatches the first wave of ready tasks to Redis and returns.
    await run_next_tasks(str(execution.execution_id), db)

    return MessageResponse(
        message="Workflow execution triggered successfully.",
        details={"execution_id": str(execution.execution_id)}
    )


@router.get("", response_model=list[ExecutionSummaryResponse])
async def list_executions(db: AsyncSession = Depends(get_db)):
    """
    List all workflow executions ordered by most recent first.
    Used by the frontend to populate the main runs dashboard/history table.
    """
    result = await db.execute(
        select(WorkflowExecution).order_by(WorkflowExecution.created_at.desc())
    )
    executions = result.scalars().all()

    return [
        ExecutionSummaryResponse(
            execution_id=str(e.execution_id),
            template_id=str(e.template_id),
            status=e.status.value,
            created_at=_fmt(e.created_at),
            updated_at=_fmt(e.updated_at),
        )
        for e in executions
    ]


@router.get("/{execution_id}", response_model=ExecutionDetailResponse)
async def get_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch full real-time status of a single execution including all task states.
    THIS IS THE CRITICAL ENDPOINT FOR THE LIVE DASHBOARD UI.

    The frontend can poll this endpoint every 2 seconds to update the visual
    DAG graph, coloring nodes green (COMPLETED), red (FAILED), or yellow (IN_PROGRESS).
    """
    # Load execution
    ex_result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
    )
    execution = ex_result.scalar_one_or_none()

    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Execution '{execution_id}' not found."
        )

    # Load all task states for this execution
    task_result = await db.execute(
        select(TaskExecution).where(TaskExecution.execution_id == execution_id)
    )
    tasks = task_result.scalars().all()

    task_responses = [
        TaskStateResponse(
            task_id=str(t.task_id),
            node_id=t.node_id,
            status=t.status.value,
            retry_count=t.retry_count,
            output=t.output,
            logs=t.logs,
            started_at=_fmt(t.started_at),
            completed_at=_fmt(t.completed_at),
        )
        for t in tasks
    ]

    return ExecutionDetailResponse(
        execution_id=str(execution.execution_id),
        template_id=str(execution.template_id),
        status=execution.status.value,
        global_context=execution.global_context,
        created_at=_fmt(execution.created_at),
        updated_at=_fmt(execution.updated_at),
        tasks=task_responses,
    )


# POST /api/v1/executions/{execution_id}/pause
@router.post("/{execution_id}/pause", response_model=MessageResponse)
async def pause_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """
    Pause a running workflow execution.

    The engine checks for PAUSED status at the start of run_next_tasks()
    and returns immediately without dispatching new tasks. Currently IN_PROGRESS
    tasks will continue to completion naturally, but no NEW tasks will be fired.
    """
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    if execution.status != ExecutionStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pause execution with status '{execution.status.value}'. Must be RUNNING."
        )

    execution.status = ExecutionStatus.PAUSED
    execution.updated_at = datetime.utcnow()
    await db.commit()

    return MessageResponse(message=f"Execution '{execution_id}' paused successfully.")


# POST /api/v1/executions/{execution_id}/resume
@router.post("/{execution_id}/resume", response_model=MessageResponse)
async def resume_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """
    Resume a previously paused workflow execution.

    Sets the status back to RUNNING and immediately calls run_next_tasks()
    so the DAG engine picks up exactly where it left off.
    """
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    if execution.status != ExecutionStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot resume execution with status '{execution.status.value}'. Must be PAUSED."
        )

    execution.status = ExecutionStatus.RUNNING
    execution.updated_at = datetime.utcnow()
    await db.commit()

    # Re-trigger the engine from where it left off
    await run_next_tasks(execution_id, db)

    return MessageResponse(message=f"Execution '{execution_id}' resumed successfully.")


# POST /api/v1/executions/{execution_id}/terminate
@router.post("/{execution_id}/terminate", response_model=MessageResponse)
async def terminate_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    """
    Hard-terminate a workflow execution immediately.

    Sets the execution to TERMINATED and marks all currently IN_PROGRESS or
    PENDING tasks as TERMINATED so the audit trail is clean and complete.
    """
    result = await db.execute(
        select(WorkflowExecution).where(WorkflowExecution.execution_id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found.")

    if execution.status in (ExecutionStatus.COMPLETED, ExecutionStatus.TERMINATED, ExecutionStatus.FAILED):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Execution is already in a terminal state: '{execution.status.value}'."
        )

    execution.status = ExecutionStatus.TERMINATED
    execution.updated_at = datetime.utcnow()

    # Mark all non-terminal tasks as TERMINATED to keep the audit trail consistent
    await db.execute(
        update(TaskExecution)
        .where(
            TaskExecution.execution_id == execution_id,
            TaskExecution.status.in_([TaskStatus.PENDING, TaskStatus.IN_PROGRESS, TaskStatus.AWAITING_APPROVAL])
        )
        .values(
            status=TaskStatus.TERMINATED,
            logs=f"[{datetime.utcnow().isoformat()}] Task terminated by admin before completion.",
            completed_at=datetime.utcnow(),
        )
    )
    await db.commit()

    return MessageResponse(message=f"Execution '{execution_id}' terminated successfully.")
