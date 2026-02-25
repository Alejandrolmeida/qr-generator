"""
Excel Service — lectura del export de Eventbrite y detección de columnas.
Refactorización de la lógica de init.py para uso como librería.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models.schemas import ExcelColumnMap


# ─── Cabeceras conocidas de Eventbrite (ES e EN) ─────────────────────────────

_KNOWN_ID_HEADERS = [
    "Número de código de barras",
    "Attendee #",
    "Order #",
    "Barcode",
]
_KNOWN_FIRST_NAME = [
    "Nombre del asistente",
    "Final Attendee First Name",
    "First Name",
    "Nombre",
]
_KNOWN_LAST_NAME = [
    "Apellidos del asistente",
    "Final Attendee Last Name",
    "Last Name",
    "Apellidos",
]
_KNOWN_TICKET_TYPE = [
    "Tipo de entrada",
    "Ticket Type",
    "Ticket Class Name",
]
_KNOWN_COMPANY = [
    "Empresa",
    "Company",
    "Organization",
]


def read_headers(excel_path: str | Path) -> list[str]:
    """Devuelve la lista de nombres de columna del Excel."""
    df = pd.read_excel(str(excel_path), nrows=0)
    return list(df.columns)


def suggest_column_map(headers: list[str]) -> ExcelColumnMap:
    """
    Intenta mapear automáticamente las columnas del Excel a los campos
    requeridos, usando listas de nombres conocidos de Eventbrite.
    Devuelve un ExcelColumnMap con los mejores candidatos.
    """

    def _best(candidates: list[str]) -> str:
        for c in candidates:
            if c in headers:
                return c
        # Búsqueda parcial insensible a mayúsculas como fallback
        for c in candidates:
            for h in headers:
                if c.lower() in h.lower():
                    return h
        return candidates[0]  # devolver el nombre por defecto si no hay match

    return ExcelColumnMap(
        col_attendee_id=_best(_KNOWN_ID_HEADERS),
        col_first_name=_best(_KNOWN_FIRST_NAME),
        col_last_name=_best(_KNOWN_LAST_NAME),
        col_ticket_type=_best(_KNOWN_TICKET_TYPE),
        col_company=_best(_KNOWN_COMPANY),
    )


def iter_attendees(
    excel_path: str | Path,
    col_map: ExcelColumnMap,
) -> list[dict]:
    """
    Itera el Excel y devuelve una lista de dicts con los campos normalizados:
      id, first_name, last_name, ticket_type, company
    Filtra filas vacías/inválidas.
    """
    df = pd.read_excel(str(excel_path))
    records: list[dict] = []

    for _, row in df.iterrows():
        attendee_id = str(row.get(col_map.col_attendee_id, "")).strip()
        first_name = str(row.get(col_map.col_first_name, "")).strip()
        last_name = str(row.get(col_map.col_last_name, "")).strip()
        ticket_type = str(row.get(col_map.col_ticket_type, "")).strip() if col_map.col_ticket_type in df.columns else ""
        company_raw = row.get(col_map.col_company) if col_map.col_company in df.columns else None
        company = str(company_raw).strip() if company_raw and str(company_raw).lower() not in ("nan", "none", "") else ""

        # Filtrar filas vacías
        if not attendee_id or attendee_id.lower() in ("nan", "none") or not first_name or not last_name:
            continue

        records.append({
            "id": attendee_id,
            "first_name": first_name,
            "last_name": last_name,
            "ticket_type": ticket_type,
            "company": company,
        })

    return records


def resolve_template_role(
    ticket_type: str,
    types_staff: list[str],
    types_speaker: list[str],
) -> str:
    """
    Devuelve el rol ('staff', 'speaker', 'attendee') según el tipo de entrada.
    """
    if ticket_type in types_staff:
        return "staff"
    if ticket_type in types_speaker:
        return "speaker"
    return "attendee"
