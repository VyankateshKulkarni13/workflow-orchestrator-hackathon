import uuid
import enum
from datetime import datetime

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from database import Base


# ---------------------------------------------------------------------------
# Enums — Postgres enforces these. Only valid values can ever be stored.
# ---------------------------------------------------------------------------

class ExecutionStatus(str, enum.Enum):
    PENDING    = "PENDING"
    RUNNING    = "RUNNING"
    PAUSED     = "PAUSED"
    COMPLETED  = "COMPLETED"
    FAILED     = "FAILED"
    TERMINATED = "TERMINATED"


class TaskStatus(str, enum.Enum):
    PENDING           = "PENDING"
    IN_PROGRESS       = "IN_PROGRESS"
    COMPLETED         = "COMPLETED"
    FAILED            = "FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    TERMINATED        = "TERMINATED"


# ---------------------------------------------------------------------------
# Table 1: workflow_templates
# Stores the raw JSON/YAML blueprint uploaded by the admin.
# One template can be used to trigger many executions.
# ---------------------------------------------------------------------------

class WorkflowTemplate(Base):
    __tablename__ = "workflow_templates"

    template_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this workflow blueprint"
    )
    name = Column(
        String(255),
        nullable=False,
        comment="Human-readable name, e.g. 'Standard E-Commerce Order'"
    )
    description = Column(
        Text,
        nullable=True,
        comment="Optional description of what the workflow does"
    )
    definition = Column(
        JSONB,
        nullable=False,
        comment="The full DAG structure parsed from the uploaded JSON/YAML file"
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # One template → many executions
    executions = relationship(
        "WorkflowExecution",
        back_populates="template",
        cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Table 2: workflow_executions
# One row per live/completed run of a workflow.
# e.g. Each customer order = one WorkflowExecution row.
# ---------------------------------------------------------------------------

class WorkflowExecution(Base):
    __tablename__ = "workflow_executions"

    execution_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this specific workflow run"
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_templates.template_id"),
        nullable=False,
        comment="Which blueprint this execution is based on"
    )
    status = Column(
        Enum(ExecutionStatus),
        default=ExecutionStatus.PENDING,
        nullable=False,
        comment="Overall status of this workflow run"
    )
    global_context = Column(
        JSONB,
        nullable=True,
        comment="The runtime payload — order details, customer info, etc. Passed to every worker."
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    template = relationship("WorkflowTemplate", back_populates="executions")
    task_executions = relationship(
        "TaskExecution",
        back_populates="execution",
        cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# Table 3: task_executions
# One row per DAG node per execution run.
# e.g. 6 nodes × 3 runs = 18 rows in this table.
# This is the table the engine reads to do topo-sort
# and what the frontend polls every second to color the graph.
# ---------------------------------------------------------------------------

class TaskExecution(Base):
    __tablename__ = "task_executions"

    task_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this task instance"
    )
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_executions.execution_id"),
        nullable=False,
        comment="Which workflow run this task belongs to"
    )
    node_id = Column(
        String(255),
        nullable=False,
        comment="The task 'id' key from the workflow JSON, e.g. 'charge_payment'"
    )
    status = Column(
        Enum(TaskStatus),
        default=TaskStatus.PENDING,
        nullable=False,
        comment="Current state of this individual task node"
    )
    retry_count = Column(
        Integer,
        default=0,
        comment="How many times this task has been retried after failure"
    )
    output = Column(
        JSONB,
        nullable=True,
        comment="The JSON response returned by the worker on success"
    )
    logs = Column(
        Text,
        nullable=True,
        comment="Error messages or debug logs from the worker on failure"
    )
    started_at  = Column(DateTime, nullable=True, comment="When the worker picked up this task")
    completed_at = Column(DateTime, nullable=True, comment="When the worker finished this task")

    # Relationship
    execution = relationship("WorkflowExecution", back_populates="task_executions")
