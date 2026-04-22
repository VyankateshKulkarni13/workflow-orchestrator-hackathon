"""
routers/tasks.py
-----------------
Endpoints for human-in-the-loop interactions and manual task management.

Routes:
  POST /api/v1/tasks/{task_id}/approve - Approve a HUMAN_APPROVAL task
  POST /api/v1/tasks/{task_id}/reject  - Reject a HUMAN_APPROVAL task
  POST /api/v1/tasks/{task_id}/retry   - Manually retry a FAILED task
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from engine import mark_task_completed, mark_task_failed, run_next_tasks
from models import TaskExecution, TaskStatus
from schemas import ApprovalRequest, MessageResponse, RetryRequest

router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


def _get_task_or_404(task_exec, task_id: str):
    if not task_exec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found."
        )


# POST /api/v1/tasks/{task_id}/approve
@router.post("/{task_id}/approve", response_model=MessageResponse)
async def approve_task(
    task_id: str,
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Approve a HUMAN_APPROVAL task node.

    Called by a manager/admin via the UI dashboard when they review
    a pending human-in-the-loop task. Marks the task as COMPLETED
    and re-triggers the DAG engine so downstream tasks can proceed.
    """
    result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id)
    )
    task_exec = result.scalar_one_or_none()
    _get_task_or_404(task_exec, task_id)

    if task_exec.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is not awaiting approval. Current status: '{task_exec.status.value}'."
        )

    # Build approval output with reviewer comments for the audit log
    approval_output = {
        "decision": "APPROVED",
        "approved_at": datetime.utcnow().isoformat(),
        "reviewer_comments": payload.comments or "Approved via admin dashboard.",
    }

    # Reuse the engine's completion handler — keeps logic in one place
    await mark_task_completed(task_id=task_id, output=approval_output, db=db)

    return MessageResponse(
        message=f"Task '{task_id}' approved successfully. Downstream tasks have been triggered."
    )


# POST /api/v1/tasks/{task_id}/reject
@router.post("/{task_id}/reject", response_model=MessageResponse)
async def reject_task(
    task_id: str,
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a HUMAN_APPROVAL task node.

    Marks the task as FAILED, logs the rejection reason, and triggers the
    engine which will then detect the failure and halt all downstream nodes.
    """
    result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id)
    )
    task_exec = result.scalar_one_or_none()
    _get_task_or_404(task_exec, task_id)

    if task_exec.status != TaskStatus.AWAITING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is not awaiting approval. Current status: '{task_exec.status.value}'."
        )

    rejection_reason = payload.comments or "Rejected by admin via dashboard."
    error_msg = f"HUMAN_APPROVAL REJECTED at {datetime.utcnow().isoformat()}. Reason: {rejection_reason}"

    await mark_task_failed(task_id=task_id, error_message=error_msg, db=db)

    return MessageResponse(
        message=f"Task '{task_id}' rejected. Downstream nodes have been halted.",
        details={"reason": rejection_reason}
    )


# POST /api/v1/tasks/{task_id}/retry
@router.post("/{task_id}/retry", response_model=MessageResponse)
async def retry_task(
    task_id: str,
    payload: RetryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually retry a FAILED task node.

    Resets the task status back to PENDING and re-calls the engine.
    The engine will pick it up in the next run_next_tasks() cycle
    and dispatch it back to Redis for the worker to retry.
    """
    result = await db.execute(
        select(TaskExecution).where(TaskExecution.task_id == task_id)
    )
    task_exec = result.scalar_one_or_none()
    _get_task_or_404(task_exec, task_id)

    if task_exec.status != TaskStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only FAILED tasks can be retried. Current status: '{task_exec.status.value}'."
        )

    retry_log_entry = (
        f"\n[{datetime.utcnow().isoformat()}] Manual retry triggered by admin. "
        f"Reason: {payload.reason or 'No reason provided.'}"
    )

    # Reset the task to PENDING so the engine redispatches it
    await db.execute(
        update(TaskExecution)
        .where(TaskExecution.task_id == task_id)
        .values(
            status=TaskStatus.PENDING,
            started_at=None,
            completed_at=None,
            logs=(task_exec.logs or "") + retry_log_entry,
        )
    )
    await db.commit()

    # Trigger the engine — it will find this node has in-degree 0 and fire it
    await run_next_tasks(str(task_exec.execution_id), db)

    return MessageResponse(
        message=f"Task '{task_id}' has been queued for retry.",
        details={"execution_id": str(task_exec.execution_id)}
    )
