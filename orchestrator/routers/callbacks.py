"""
Webhook endpoints used EXCLUSIVELY by worker microservices to report results.
These should NEVER be called by the frontend or end users.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from engine import mark_task_completed, mark_task_failed
from schemas import MessageResponse, TaskCompleteRequest, TaskFailedRequest

router = APIRouter(prefix="/api/v1/callbacks", tags=["Callbacks (Workers)"])


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session



@router.post("/task-complete", response_model=MessageResponse)
async def callback_task_complete(
    payload: TaskCompleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook called by a Redis worker to report a SUCCESSFUL task completion.

    Payload sent by the worker:
      {
        "task_id": "<uuid>",
        "output": { "payment_ref": "pay_abc123", "amount": 99.99 }
      }

    The engine:
    1. Marks the task as COMPLETED.
    2. Stores the output JSON and calculates execution duration.
    3. Immediately calls run_next_tasks() to keep the DAG moving.
    """
    try:
        await mark_task_completed(
            task_id=payload.task_id,
            output=payload.output or {},
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Engine error processing completion: {str(e)}"
        )

    return MessageResponse(
        message=f"Task '{payload.task_id}' marked as COMPLETED. Next wave of tasks dispatched.",
        details={"task_id": payload.task_id}
    )



@router.post("/task-failed", response_model=MessageResponse)
async def callback_task_failed(
    payload: TaskFailedRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Webhook called by a Redis worker to report a task FAILURE.

    Payload sent by the worker:
      {
        "task_id": "<uuid>",
        "error_message": "Payment gateway timed out after 30s."
      }

    The engine:
    1. Marks task as FAILED and increments retry_count.
    2. Appends the error message to the task's logs column.
    3. Calls run_next_tasks() — the engine detects the failure and
       blocks all downstream dependent nodes from firing.
    """
    try:
        await mark_task_failed(
            task_id=payload.task_id,
            error_message=payload.error_message,
            db=db,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Engine error processing failure: {str(e)}"
        )

    return MessageResponse(
        message=f"Task '{payload.task_id}' marked as FAILED. Downstream nodes have been blocked.",
        details={"task_id": payload.task_id}
    )
