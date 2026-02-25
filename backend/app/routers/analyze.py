"""
Router: /api/analyze
Analiza la plantilla PDF con GPT-4o Vision y devuelve la posición del QR.
También devuelve las cabeceras del Excel con el mapeo de columnas sugerido.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import (
    ExcelHeadersResponse,
    TemplateAnalysisRequest,
    TemplateAnalysisResponse,
)
from app.services import ai_service, storage_service
from app.services.excel_service import read_headers, suggest_column_map
from app.services.pdf_service import render_page_as_png

router = APIRouter(prefix="/api/analyze", tags=["analyze"])


@router.post("/template", response_model=TemplateAnalysisResponse)
async def analyze_template(req: TemplateAnalysisRequest) -> TemplateAnalysisResponse:
    """
    Descarga la plantilla PDF desde Blob Storage, la renderiza como PNG
    y la envía a GPT-4o Vision para detectar la zona del QR.
    """
    s = get_settings()
    blob_name = f"{req.session_id}/{req.role.value}.pdf"

    if not storage_service.blob_exists(s.azure_storage_container_templates, blob_name):
        raise HTTPException(
            status_code=404,
            detail=f"Plantilla no encontrada para sesión={req.session_id}, rol={req.role.value}. "
                   f"Sube el PDF primero con /api/upload/template.",
        )

    # Descargar PDF a fichero temporal
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        storage_service.download_blob_to_file(
            s.azure_storage_container_templates, blob_name, tmp.name
        )
        tmp_path = tmp.name

    # MD5 para caché
    blob_hash = storage_service.blob_md5(s.azure_storage_container_templates, blob_name)

    # Renderizar primera página → PNG
    png_bytes = render_page_as_png(tmp_path, dpi=s.pdf_render_dpi)

    # Analizar con GPT-4o Vision (cacheado por hash)
    result = ai_service.analyze_template_image(png_bytes, blob_hash=blob_hash)

    needs_review = result.confidence < s.ai_confidence_threshold

    return TemplateAnalysisResponse(
        session_id=req.session_id,
        role=req.role,
        result=result,
        needs_human_review=needs_review,
    )


@router.post("/excel", response_model=ExcelHeadersResponse)
async def analyze_excel(session_id: str) -> ExcelHeadersResponse:
    """
    Descarga el Excel de la sesión, lee sus cabeceras y sugiere el mapeo
    de columnas automáticamente.
    """
    s = get_settings()
    blob_name = f"{session_id}/attendees.xlsx"

    if not storage_service.blob_exists(s.azure_storage_container_excels, blob_name):
        raise HTTPException(
            status_code=404,
            detail=f"Excel no encontrado para sesión={session_id}. "
                   f"Sube el fichero primero con /api/upload/excel.",
        )

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        storage_service.download_blob_to_file(
            s.azure_storage_container_excels, blob_name, tmp.name
        )
        headers = read_headers(tmp.name)

    suggested = suggest_column_map(headers)

    return ExcelHeadersResponse(
        session_id=session_id,
        headers=headers,
        suggested_map=suggested,
    )
