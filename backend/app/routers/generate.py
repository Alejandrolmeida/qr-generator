"""
Router: /api/generate
Lanza la generación asíncrona de todas las acreditaciones,
comprime el resultado en ZIP, lo sube a Blob Storage
y devuelve una URL SAS de descarga.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.core.config import get_settings
from app.models.schemas import (
    GenerationJobResponse,
    GenerationRequest,
    JobStatus,
    TemplateRole,
)
from app.services import job_service, storage_service
from app.services.excel_service import iter_attendees, resolve_template_role
from app.services.pdf_service import generate_accreditation

router = APIRouter(prefix="/api", tags=["generate"])


@router.post("/generate", response_model=GenerationJobResponse, status_code=202)
async def start_generation(
    req: GenerationRequest,
    background_tasks: BackgroundTasks,
) -> GenerationJobResponse:
    """
    Inicia la generación en background. Devuelve el job_id para hacer polling.
    """
    s = get_settings()  # noqa: F841 — validar config antes de lanzar

    # Verificar que existe el Excel
    excel_blob = f"{req.session_id}/attendees.xlsx"
    if not storage_service.blob_exists(s.azure_storage_container_excels, excel_blob):
        raise HTTPException(
            status_code=404,
            detail="Excel de asistentes no encontrado. Sube el fichero con /api/upload/excel.",
        )

    # Contar asistentes para el job
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        storage_service.download_blob_to_file(
            s.azure_storage_container_excels, excel_blob, tmp.name
        )
        attendees = iter_attendees(tmp.name, req.column_map)
        tmp_excel = tmp.name

    job = job_service.create_job(
        session_id=req.session_id,
        total_attendees=len(attendees),
    )

    background_tasks.add_task(
        _run_generation,
        job_id=job.job_id,
        req=req,
        excel_path=tmp_excel,
        attendees=attendees,
    )

    return job


@router.get("/status/{job_id}", response_model=GenerationJobResponse)
async def get_job_status(job_id: str) -> GenerationJobResponse:
    """Consulta el estado y progreso de un job de generación."""
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} no encontrado.")
    return job


# ─── Tarea en background ─────────────────────────────────────────────────────

async def _run_generation(
    job_id: str,
    req: GenerationRequest,
    excel_path: str,
    attendees: list[dict],
) -> None:
    s = get_settings()
    job_service.mark_running(job_id)

    work_dir = tempfile.mkdtemp(prefix=f"qrgen_{req.session_id}_")
    templates: dict[str, str] = {}

    try:
        # Descargar plantillas
        for role in TemplateRole:
            blob = f"{req.session_id}/{role.value}.pdf"
            if storage_service.blob_exists(s.azure_storage_container_templates, blob):
                local = os.path.join(work_dir, f"{role.value}.pdf")
                storage_service.download_blob_to_file(
                    s.azure_storage_container_templates, blob, local
                )
                templates[role.value] = local

        if not templates:
            raise RuntimeError("No se encontraron plantillas. Sube al menos una con /api/upload/template.")

        # Fallback: si falta algún rol, usar la del asistente general
        fallback = templates.get("attendee") or next(iter(templates.values()))
        for role in TemplateRole:
            templates.setdefault(role.value, fallback)

        col = req.column_map
        types_staff = col.ticket_types_staff
        types_speaker = col.ticket_types_speaker

        generated = skipped = failed = 0
        stats: dict[str, int] = {"staff": 0, "speaker": 0, "attendee": 0}

        sem = asyncio.Semaphore(s.max_concurrent_pdf_jobs)

        async def _process_one(attendee: dict) -> None:
            nonlocal generated, skipped, failed
            async with sem:
                role_str = resolve_template_role(
                    attendee["ticket_type"], types_staff, types_speaker
                )
                template_path = templates[role_str]
                output_pdf = os.path.join(work_dir, f"attendee-{attendee['id']}.pdf")

                # Modo incremental: saltar si ya existe
                if req.incremental and os.path.exists(output_pdf):
                    skipped += 1
                    job_service.increment_progress(job_id, skipped=1)
                    return

                pos = req.positions.get(TemplateRole(role_str)) or req.positions.get(TemplateRole.attendee)
                if not pos:
                    failed += 1
                    job_service.increment_progress(job_id, failed=1)
                    return

                try:
                    await asyncio.to_thread(
                        generate_accreditation,
                        template_path=template_path,
                        output_path=output_pdf,
                        qr_data=attendee["id"],
                        qr_x=pos["qr_x"],
                        qr_y=pos["qr_y"],
                        qr_size=pos["qr_size"],
                        attendee_name=attendee["first_name"],
                        attendee_lastname=attendee["last_name"],
                        attendee_company=attendee.get("company", ""),
                        fonts_folder=s.fonts_folder,
                    )
                    generated += 1
                    stats[role_str] = stats.get(role_str, 0) + 1
                    job_service.increment_progress(job_id, generated=1)
                except Exception as exc:
                    failed += 1
                    job_service.increment_progress(job_id, failed=1)

        await asyncio.gather(*[_process_one(a) for a in attendees])

        # Comprimir PDFs en ZIP
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        zip_name = f"acreditaciones_{timestamp}.zip"
        zip_path = os.path.join(work_dir, zip_name)

        pdf_files = [f for f in Path(work_dir).glob("attendee-*.pdf")]
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for pdf in pdf_files:
                zf.write(pdf, pdf.name)

        # Subir ZIP a Blob Storage
        zip_blob = f"{req.session_id}/{zip_name}"
        with open(zip_path, "rb") as zf:
            storage_service.upload_blob(
                container=s.azure_storage_container_output,
                blob_name=zip_blob,
                data=zf,
            )

        download_url = storage_service.generate_sas_url(
            container=s.azure_storage_container_output,
            blob_name=zip_blob,
            ttl_hours=s.sas_token_ttl_hours,
        )

        job_service.mark_completed(
            job_id,
            generated=generated,
            skipped=skipped,
            failed=failed,
            download_url=download_url,
            stats=stats,
        )

    except Exception as exc:
        job_service.mark_failed(job_id, error=str(exc))
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        if os.path.exists(excel_path):
            os.unlink(excel_path)
