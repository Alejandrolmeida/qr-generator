"""
Router: /api/preview
Genera una acreditación de muestra (asistente ficticio) y devuelve
una URL SAS a un PNG para previsualización en el chat.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.models.schemas import PreviewRequest, PreviewResponse
from app.services import storage_service
from app.services.pdf_service import generate_accreditation, render_page_as_png

router = APIRouter(prefix="/api/preview", tags=["preview"])


@router.post("/", response_model=PreviewResponse)
async def generate_preview(req: PreviewRequest) -> PreviewResponse:
    """
    Genera un PDF de muestra con un asistente ficticio usando la posición
    indicada (o la detectada por IA si no se especifica ninguna).
    Devuelve una URL SAS a la imagen PNG del resultado.
    """
    s = get_settings()
    template_blob = f"{req.session_id}/{req.role.value}.pdf"

    if not storage_service.blob_exists(s.azure_storage_container_templates, template_blob):
        raise HTTPException(
            status_code=404,
            detail=f"Plantilla no encontrada: {template_blob}",
        )

    # La posición puede venir de la petición (ajuste manual) o de un análisis previo
    qr_x = req.qr_x
    qr_y = req.qr_y
    qr_size = req.qr_size

    if qr_x is None or qr_y is None or qr_size is None:
        raise HTTPException(
            status_code=422,
            detail="Se requieren qr_x, qr_y y qr_size. "
                   "Ejecuta /api/analyze/template primero para obtenerlos.",
        )

    # Descargar plantilla
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_tmpl:
        storage_service.download_blob_to_file(
            s.azure_storage_container_templates, template_blob, tmp_tmpl.name
        )
        template_path = tmp_tmpl.name

    # Generar PDF de muestra
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_out:
        output_pdf_path = tmp_out.name

    generate_accreditation(
        template_path=template_path,
        output_path=output_pdf_path,
        qr_data=req.sample_barcode,
        qr_x=qr_x,
        qr_y=qr_y,
        qr_size=qr_size,
        attendee_name=req.sample_name,
        attendee_lastname=req.sample_lastname,
        attendee_company=req.sample_company,
        fonts_folder=s.fonts_folder,
    )

    # Renderizar como PNG
    png_bytes = render_page_as_png(output_pdf_path, dpi=s.pdf_render_dpi)

    # Subir PNG a Blob Storage y generar SAS
    preview_blob = f"{req.session_id}/previews/{req.role.value}_preview.png"
    storage_service.upload_blob(
        container=s.azure_storage_container_output,
        blob_name=preview_blob,
        data=png_bytes,
    )
    preview_url = storage_service.generate_sas_url(
        container=s.azure_storage_container_output,
        blob_name=preview_blob,
        ttl_hours=2,
    )

    return PreviewResponse(
        session_id=req.session_id,
        role=req.role,
        preview_url=preview_url,
        qr_x=qr_x,
        qr_y=qr_y,
        qr_size=qr_size,
    )
