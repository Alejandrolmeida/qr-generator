"""
PDF Service — refactorización de create_card.py para uso como librería.
Genera acreditaciones PDF con QR y texto del asistente superpuesto sobre
una plantilla PDF existente.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter  # noqa: F401
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.services.qr_service import generate_styled_qr_png_bytes

# Registrar fuente al importar el módulo
_FONTS_REGISTERED = False


def _ensure_fonts(fonts_folder: str) -> None:
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    font_path = os.path.join(fonts_folder, "DejaVuSans-Bold.ttf")
    if not os.path.exists(font_path):
        raise FileNotFoundError(f"Font not found: {font_path}")
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", font_path))
    _FONTS_REGISTERED = True


# ─── QR helpers ───────────────────────────────────────────────────────────────

def generate_qr_code_png(
    data: str,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    eye_color: str | None = None,
    module_roundness: float = 0.85,
    logo_path: str | None = None,
    logo_scale: float = 0.22,
) -> BytesIO:
    """
    Genera un QR estilizado (rounded premium) como PNG en memoria.
    Sustituye a la antigua implementación SVG básica.
    """
    png_bytes = generate_styled_qr_png_bytes(
        data=data,
        logo_path=logo_path,
        fg_color=fg_color,
        bg_color=bg_color,
        eye_color=eye_color,
        module_roundness=module_roundness,
        logo_scale=logo_scale,
        cell_px=40,
        border_cells=4,
        dpi=300,
    )
    buf = BytesIO(png_bytes)
    buf.seek(0)
    return buf


def _adjust_font_size(
    c: canvas.Canvas,
    text: str,
    max_width: float,
    initial: int = 30,
    minimum: int = 8,
) -> int:
    size = initial
    while size >= minimum:
        c.setFont("DejaVuSans-Bold", size)
        if c.stringWidth(text, "DejaVuSans-Bold", size) <= max_width:
            return size
        size -= 1
    return minimum


# ─── Core generation ──────────────────────────────────────────────────────────

def generate_accreditation(
    *,
    template_path: str | Path,
    output_path: str | Path,
    qr_data: str,
    qr_x: int,
    qr_y: int,
    qr_size: int,
    attendee_name: str,
    attendee_lastname: str,
    attendee_company: str = "",
    fonts_folder: str = "fonts",
    keep_temp: bool = False,
    # ── Opciones de estilo QR ─────────────────────────────────────────────
    qr_fg_color: str = "#000000",
    qr_bg_color: str = "#FFFFFF",
    qr_eye_color: str | None = None,
    qr_module_roundness: float = 0.85,
    qr_logo_path: str | None = None,
    qr_logo_scale: float = 0.22,
) -> None:
    """
    Genera una acreditación PDF para un asistente.

    Args:
        template_path:      PDF de plantilla base.
        output_path:        Ruta de salida del PDF final.
        qr_data:            Datos codificados en el QR (número de código de barras).
        qr_x / qr_y:       Coordenadas ReportLab (y=0 en borde inferior) del QR.
        qr_size:            Tamaño del QR en puntos.
        attendee_name:      Nombre del asistente.
        attendee_lastname:  Apellidos del asistente.
        attendee_company:   Empresa (opcional).
        fonts_folder:       Carpeta con DejaVuSans-Bold.ttf.
        keep_temp:          Si True, no borra ficheros temporales (debug).
    """
    _ensure_fonts(fonts_folder)

    template_path = str(template_path)
    output_path = str(output_path)

    # Copiar plantilla → destino (preserva recursos embebidos)
    shutil.copyfile(template_path, output_path)

    # Dimensiones reales de la plantilla (sin asunciones de tamaño de página)
    with fitz.open(template_path) as tmpl:
        tmpl_w = tmpl[0].rect.width
        tmpl_h = tmpl[0].rect.height

    # ── Generar PNG del QR (estilo rounded premium) ─────────────────────────
    qr_png_buf = generate_qr_code_png(
        data=qr_data,
        fg_color=qr_fg_color,
        bg_color=qr_bg_color,
        eye_color=qr_eye_color,
        module_roundness=qr_module_roundness,
        logo_path=qr_logo_path,
        logo_scale=qr_logo_scale,
    )
    tmp_png = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    tmp_png.write(qr_png_buf.read())
    tmp_png.close()

    # ── Crear overlay PDF al mismo tamaño que plantilla ───────────────────────
    tmp_overlay = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_overlay.close()

    c = canvas.Canvas(tmp_overlay.name, pagesize=(tmpl_w, tmpl_h))

    # QR (insertar PNG directamente — preserva todos los detalles redondeados)
    c.drawImage(tmp_png.name, qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")

    # TextZone: centrado horizontal, encima del QR
    page_cx = tmpl_w / 2
    max_text_w = tmpl_w - (qr_x * 2) - 4
    qr_top = qr_y + qr_size

    # Apellido
    last_upper = attendee_lastname.upper()
    font_last = _adjust_font_size(c, last_upper, max_text_w, initial=22)
    c.setFont("DejaVuSans-Bold", font_last)
    y_last = qr_top + 10
    c.drawCentredString(page_cx, y_last, last_upper)

    # Nombre
    first_upper = attendee_name.upper()
    font_first = _adjust_font_size(c, first_upper, max_text_w, initial=22)
    c.setFont("DejaVuSans-Bold", font_first)
    y_first = y_last + font_last + 6
    c.drawCentredString(page_cx, y_first, first_upper)

    # Empresa (opcional, en azul corporativo)
    if attendee_company and attendee_company.lower() not in ("nan", "none", ""):
        company_upper = attendee_company.upper()
        font_company = _adjust_font_size(c, company_upper, max_text_w, initial=18)
        c.setFont("DejaVuSans-Bold", font_company)
        c.setFillColor(colors.HexColor("#005BAB"))
        y_company = y_first + font_first + 4
        c.drawCentredString(page_cx, y_company, company_upper)
        c.setFillColor(colors.black)

    c.save()

    # ── Fundir overlay sobre la plantilla ─────────────────────────────────────
    doc = fitz.open(output_path)
    page = doc.load_page(0)
    overlay_doc = fitz.open(tmp_overlay.name)
    page.show_pdf_page(page.rect, overlay_doc, 0)
    overlay_doc.close()

    tmp_final = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp_final.close()
    doc.save(tmp_final.name, deflate=True)
    doc.close()

    shutil.move(tmp_final.name, output_path)

    if not keep_temp:
        os.unlink(tmp_png.name)
        os.unlink(tmp_overlay.name)


def render_page_as_png(pdf_path: str | Path, dpi: int = 150) -> bytes:
    """Renderiza la primera página de un PDF como PNG (bytes)."""
    with fitz.open(str(pdf_path)) as doc:
        page = doc.load_page(0)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix.tobytes("png")
