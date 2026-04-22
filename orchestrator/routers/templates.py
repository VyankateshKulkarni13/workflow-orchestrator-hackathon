"""
routers/templates.py
---------------------
Endpoints for managing workflow blueprints (DAG definitions).

Routes:
  POST /api/v1/templates              - Upload a new DAG blueprint
  GET  /api/v1/templates              - List all workflow templates
  GET  /api/v1/templates/{template_id} - Get a specific template
"""

import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal
from engine import parse_dag
from models import WorkflowTemplate
from schemas import MessageResponse, TemplateResponse, TemplateUploadRequest

router = APIRouter(prefix="/api/v1/templates", tags=["Templates"])


# ---------------------------------------------------------------------------
# FastAPI Dependency Injection — provides a DB session per request
# ---------------------------------------------------------------------------
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


# ---------------------------------------------------------------------------
# POST /api/v1/templates
# ---------------------------------------------------------------------------
@router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def upload_template(
    payload: TemplateUploadRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Upload and register a new workflow blueprint.

    - Validates that the JSON contains a 'tasks' list.
    - Runs Kahn's Algorithm for cycle detection BEFORE saving to DB.
    - Returns the saved template with its generated UUID.
    """
    try:
        # Validate & detect cycles — raises ValueError on bad input
        parse_dag(payload.definition)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid DAG definition: {str(e)}"
        )

    try:
        template = WorkflowTemplate(
            name=payload.name,
            description=payload.description,
            definition=payload.definition,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save template to database."
        )

    return TemplateResponse(
        template_id=str(template.template_id),
        name=template.name,
        description=template.description,
        definition=template.definition,
        created_at=template.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/templates
# ---------------------------------------------------------------------------
@router.get("", response_model=list[TemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    """
    List all registered workflow blueprints.
    Used by the frontend to populate the template selection dropdown.
    """
    result = await db.execute(select(WorkflowTemplate).order_by(WorkflowTemplate.created_at.desc()))
    templates = result.scalars().all()

    return [
        TemplateResponse(
            template_id=str(t.template_id),
            name=t.name,
            description=t.description,
            definition=t.definition,
            created_at=t.created_at.isoformat(),
        )
        for t in templates
    ]


# ---------------------------------------------------------------------------
# GET /api/v1/templates/{template_id}
# ---------------------------------------------------------------------------
@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(template_id: str, db: AsyncSession = Depends(get_db)):
    """
    Fetch a single template by its UUID.
    Used by the frontend to render the visual DAG graph before execution.
    """
    result = await db.execute(
        select(WorkflowTemplate).where(WorkflowTemplate.template_id == template_id)
    )
    template = result.scalar_one_or_none()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_id}' not found."
        )

    return TemplateResponse(
        template_id=str(template.template_id),
        name=template.name,
        description=template.description,
        definition=template.definition,
        created_at=template.created_at.isoformat(),
    )
