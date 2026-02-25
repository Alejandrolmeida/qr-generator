"""Pydantic schemas para requests y responses de la API."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ─── Enums ────────────────────────────────────────────────────────────────────

class TemplateRole(str, Enum):
    attendee = "attendee"
    speaker = "speaker"
    staff = "staff"


class JobStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


# ─── Upload ───────────────────────────────────────────────────────────────────

class UploadedFile(BaseModel):
    session_id: str
    role: TemplateRole | None = None   # None para Excel
    blob_name: str
    original_filename: str
    size_bytes: int
    uploaded_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Análisis de plantilla ────────────────────────────────────────────────────

class TemplateAnalysisRequest(BaseModel):
    session_id: str
    role: TemplateRole = TemplateRole.attendee


class TemplatePositionResult(BaseModel):
    """Resultado del análisis IA de una plantilla."""
    qr_x: int = Field(description="Coord X esquina inferior-izquierda del QR (puntos ReportLab)")
    qr_y: int = Field(description="Coord Y esquina inferior-izquierda del QR (puntos ReportLab, y=0 abajo)")
    qr_size: int = Field(description="Tamaño recomendado del QR en puntos")
    page_width: int
    page_height: int
    confidence: float = Field(ge=0.0, le=1.0)
    notes: str = ""
    # Hash del blob analizado — para cacheado
    blob_hash: str = ""


class TemplateAnalysisResponse(BaseModel):
    session_id: str
    role: TemplateRole
    result: TemplatePositionResult
    needs_human_review: bool   # True si confidence < threshold


# ─── Preview ──────────────────────────────────────────────────────────────────

class PreviewRequest(BaseModel):
    session_id: str
    role: TemplateRole = TemplateRole.attendee
    # Posición y tamaño — pueden sobrescribir el resultado del análisis IA
    qr_x: int | None = None
    qr_y: int | None = None
    qr_size: int | None = None
    # Datos ficticiocs del asistente de ejemplo
    sample_name: str = "María"
    sample_lastname: str = "García Fernández"
    sample_company: str = "Contoso Ltd."
    sample_barcode: str = "99000000001"


class PreviewResponse(BaseModel):
    session_id: str
    role: TemplateRole
    preview_url: str          # URL SAS a una imagen PNG del preview
    qr_x: int
    qr_y: int
    qr_size: int


# ─── Mapeo de columnas Excel ──────────────────────────────────────────────────

class ExcelColumnMap(BaseModel):
    col_attendee_id: str = "Número de código de barras"
    col_first_name: str = "Nombre del asistente"
    col_last_name: str = "Apellidos del asistente"
    col_ticket_type: str = "Tipo de entrada"
    col_company: str = "Empresa"
    ticket_types_staff: list[str] = ["Helpers"]
    ticket_types_speaker: list[str] = ["Speakers"]


class ExcelHeadersResponse(BaseModel):
    session_id: str
    headers: list[str]
    suggested_map: ExcelColumnMap


# ─── Generación ───────────────────────────────────────────────────────────────

class GenerationRequest(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    # Posición final aprobada para cada rol (puede diferir entre roles)
    positions: dict[TemplateRole, dict[str, int]] = Field(
        description="Mapa rol → {qr_x, qr_y, qr_size}",
        default_factory=dict,
    )
    column_map: ExcelColumnMap = Field(default_factory=ExcelColumnMap)
    # Si True, omite asistentes cuyo PDF ya existe (modo incremental)
    incremental: bool = True


class GenerationJobResponse(BaseModel):
    job_id: str
    session_id: str
    status: JobStatus = JobStatus.pending
    total_attendees: int = 0
    generated: int = 0
    skipped: int = 0
    failed: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    download_url: str | None = None   # SAS link al ZIP final
    error: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
