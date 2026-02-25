"""
Router: /api/upload
Sube plantillas PDF y el Excel de asistentes a Azure Blob Storage.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.models.schemas import TemplateRole, UploadedFile
from app.services import storage_service

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/template", response_model=UploadedFile)
async def upload_template(
    session_id: str = Form(...),
    role: TemplateRole = Form(...),
    file: UploadFile = File(...),
) -> UploadedFile:
    """
    Sube una plantilla PDF para el rol indicado (attendee / speaker / staff).
    El blob queda almacenado en el contenedor 'templates' con el path:
      {session_id}/{role}.pdf
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Se requiere un fichero PDF.")

    s = get_settings()
    blob_name = f"{session_id}/{role.value}.pdf"
    content = await file.read()

    storage_service.upload_blob(
        container=s.azure_storage_container_templates,
        blob_name=blob_name,
        data=content,
    )

    return UploadedFile(
        session_id=session_id,
        role=role,
        blob_name=blob_name,
        original_filename=file.filename,
        size_bytes=len(content),
    )


@router.post("/excel", response_model=UploadedFile)
async def upload_excel(
    session_id: str = Form(...),
    file: UploadFile = File(...),
) -> UploadedFile:
    """
    Sube el Excel de asistentes (exportado de Eventbrite u otro sistema).
    El blob queda almacenado en el contenedor 'excels' con el path:
      {session_id}/attendees.xlsx
    """
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Se requiere un fichero Excel (.xlsx / .xls).")

    s = get_settings()
    blob_name = f"{session_id}/attendees.xlsx"
    content = await file.read()

    storage_service.upload_blob(
        container=s.azure_storage_container_excels,
        blob_name=blob_name,
        data=content,
    )

    return UploadedFile(
        session_id=session_id,
        role=None,
        blob_name=blob_name,
        original_filename=file.filename,
        size_bytes=len(content),
    )
