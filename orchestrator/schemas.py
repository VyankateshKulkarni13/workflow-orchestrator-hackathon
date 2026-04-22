"""
schemas.py
----------
All Pydantic request/response models for the API layer.
These define the exact shape of data flowing in and out of every endpoint.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ===========================================================================
# TEMPLATE SCHEMAS
# ===========================================================================

class TemplateUploadRequest(BaseModel):
    """Payload to upload a new DAG workflow blueprint."""
    name: str = Field(..., min_length=1, description="Human-readable name of the workflow.")
    description: Optional[str] = Field(None, description="Optional description of the workflow.")
    definition: Dict[str, Any] = Field(
        ...,
        description="The full DAG definition. Must contain a 'tasks' list.",
        example={
            "tasks": [
                {"id": "validate_order", "type": "MOCK_HTTP", "depends_on": []},
                {"id": "charge_payment", "type": "MOCK_HTTP", "depends_on": ["validate_order"]}
            ]
        }
    )


class TemplateResponse(BaseModel):
    """Response model returned after creating or fetching a template."""
    template_id: str
    name: str
    description: Optional[str]
    definition: Dict[str, Any]
    created_at: str

    class Config:
        from_attributes = True


# ===========================================================================
# EXECUTION SCHEMAS
# ===========================================================================

class ExecutionCreateRequest(BaseModel):
    """Payload to trigger a new workflow execution from a template."""
    template_id: str = Field(..., description="UUID of the WorkflowTemplate to execute.")
    global_context: Optional[Dict[str, Any]] = Field(
        default={},
        description="Runtime data injected into all tasks (e.g., order_id, customer details).",
        example={"order_id": "ORD-9876", "customer_email": "user@example.com"}
    )


class TaskStateResponse(BaseModel):
    """Represents the real-time status of a single task node."""
    task_id: str
    node_id: str
    status: str
    retry_count: int
    output: Optional[Dict[str, Any]]
    logs: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


class ExecutionDetailResponse(BaseModel):
    """Full detail of a workflow execution including all task states."""
    execution_id: str
    template_id: str
    status: str
    global_context: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    tasks: List[TaskStateResponse]


class ExecutionSummaryResponse(BaseModel):
    """Lightweight summary for listing executions."""
    execution_id: str
    template_id: str
    status: str
    created_at: str
    updated_at: str


# ===========================================================================
# TASK SCHEMAS (HUMAN-IN-THE-LOOP)
# ===========================================================================

class ApprovalRequest(BaseModel):
    """Payload for approving or rejecting a HUMAN_APPROVAL task."""
    comments: Optional[str] = Field(
        None,
        description="Optional reviewer comments logged to the task audit trail."
    )


class RetryRequest(BaseModel):
    """Payload for manually retrying a failed task."""
    reason: Optional[str] = Field(
        None,
        description="Optional reason for the manual retry, logged to the audit trail."
    )


# ===========================================================================
# CALLBACK SCHEMAS (USED BY WORKERS)
# ===========================================================================

class TaskCompleteRequest(BaseModel):
    """Payload sent by a worker to report successful task completion."""
    task_id: str = Field(..., description="UUID of the TaskExecution that finished.")
    output: Optional[Dict[str, Any]] = Field(
        default={},
        description="The structured JSON result produced by the worker.",
        example={"payment_ref": "pay_abc123", "amount_charged": 99.99}
    )


class TaskFailedRequest(BaseModel):
    """Payload sent by a worker to report a task failure."""
    task_id: str = Field(..., description="UUID of the TaskExecution that failed.")
    error_message: str = Field(
        ...,
        description="Human-readable error description from the worker.",
        example="Payment gateway timed out after 30s."
    )


# ===========================================================================
# GENERIC RESPONSE
# ===========================================================================

class MessageResponse(BaseModel):
    """Generic acknowledgement response."""
    message: str
    details: Optional[Dict[str, Any]] = None
