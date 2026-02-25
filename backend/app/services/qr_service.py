"""
QR Service — Generador de QR estilo "rounded premium" (inspirado en Eventbrite).

Características:
- Módulos redondeados (squircle) con separación suave entre celdas
- Finder patterns (3 ojos de esquina) con estilo squircle premium:
    · Anillo exterior redondeado grueso
    · Punto interior redondeado
- Overlay de logo central con soporte de transparencia alfa
- Corrección de errores ERROR_CORRECT_H (máxima)
- Exportación PNG de alta resolución y SVG vectorial
- 100% configurable: colores, radio de esquinas, tamaño de logo

Dependencias (ya en requirements.txt):
    qrcode[pil]>=8.2
    Pillow>=12.0.0
"""

from __future__ import annotations

import math
import os
from io import BytesIO
from pathlib import Path
from typing import Sequence

import qrcode
import qrcode.constants
from PIL import Image, ImageDraw


# ─────────────────────────────────────────────────────────────────────────────
# Configuración interna
# ─────────────────────────────────────────────────────────────────────────────

_CELL_PX: int = 40          # píxeles por módulo (resolución base)
_BORDER_CELLS: int = 4      # quiet zone en número de módulos
_GAP_RATIO: float = 0.12    # separación entre módulos como fracción del tamaño de celda
_DPI: int = 300             # DPI del PNG exportado


# ─────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _parse_color(color: str) -> tuple[int, int, int]:
    """Convierte un color hex (#RRGGBB o #RGB) a tupla RGB."""
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def _get_qr_matrix(data: str) -> list[list[bool]]:
    """Genera y devuelve la matriz booleana del QR."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=1,
        border=0,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()   # type: ignore[return-value]


def _finder_zones(n: int) -> set[tuple[int, int]]:
    """
    Retorna el conjunto de (row, col) que pertenecen a los tres
    finder patterns + separadores (7×7 + 1 celda de margen).
    Estas celdas se renderizan con el estilo de ojo especial.
    """
    zones: set[tuple[int, int]] = set()
    corners = [(0, 0), (0, n - 7), (n - 7, 0)]
    for br, bc in corners:
        for r in range(br - 1, br + 8):          # +1 celda de separador
            for c in range(bc - 1, bc + 8):
                if 0 <= r < n and 0 <= c < n:
                    zones.add((r, c))
    return zones


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    radius: float,
    fill: tuple[int, int, int] | tuple[int, int, int, int],
) -> None:
    """Dibuja un rectángulo con esquinas redondeadas usando Pillow."""
    draw.rounded_rectangle(
        [(int(x0), int(y0)), (int(x1), int(y1))],
        radius=int(radius),
        fill=fill,
    )


def _draw_finder_pattern(
    draw: ImageDraw.ImageDraw,
    origin_r: int,
    origin_c: int,
    cell: int,
    gap: int,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    eye: tuple[int, int, int],
    roundness: float,
) -> None:
    """
    Renderiza un finder pattern 7×7 con estilo squircle premium:
    1. Rectángulo exterior 7×7 redondeado (color fg o eye)
    2. Relleno interior blanco 5×5 redondeado
    3. Punto 3×3 relleno redondeado (color eye)
    """
    px = origin_c * cell  # x en píxeles
    py = origin_r * cell  # y en píxeles

    outer_w = 7 * cell
    outer_r = outer_w * roundness * 0.22      # radio esquina exterior

    # ① Bloque exterior 7×7
    _draw_rounded_rect(draw, px, py, px + outer_w, py + outer_w, outer_r, eye)

    # ② Hueco interior 5×5 (fondo)
    inner_offset = cell
    inner_w = 5 * cell
    inner_r = inner_w * roundness * 0.18
    _draw_rounded_rect(
        draw,
        px + inner_offset,
        py + inner_offset,
        px + inner_offset + inner_w,
        py + inner_offset + inner_w,
        inner_r,
        bg,
    )

    # ③ Punto central 3×3
    dot_offset = cell * 2
    dot_w = 3 * cell
    dot_r = dot_w * roundness * 0.35
    _draw_rounded_rect(
        draw,
        px + dot_offset,
        py + dot_offset,
        px + dot_offset + dot_w,
        py + dot_offset + dot_w,
        dot_r,
        eye,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Generación PNG
# ─────────────────────────────────────────────────────────────────────────────

def _render_png(
    matrix: list[list[bool]],
    logo_path: str | None,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
    eye: tuple[int, int, int],
    module_roundness: float,
    logo_scale: float,
    cell_px: int = _CELL_PX,
    border_cells: int = _BORDER_CELLS,
    gap_ratio: float = _GAP_RATIO,
    dpi: int = _DPI,
) -> Image.Image:
    n = len(matrix)
    total_cells = n + 2 * border_cells
    img_size = total_cells * cell_px

    img = Image.new("RGB", (img_size, img_size), bg)
    draw = ImageDraw.Draw(img)

    gap = int(cell_px * gap_ratio)
    mod_r = int((cell_px - 2 * gap) / 2 * module_roundness)

    finders = _finder_zones(n)
    finder_origins = [(0, 0), (0, n - 7), (n - 7, 0)]

    # Celdas de finder ya pintadas (para no redibujar módulos individuales)
    painted_finders: set[tuple[int, int]] = set()
    for br, bc in finder_origins:
        for r in range(br, br + 7):
            for c in range(bc, bc + 7):
                painted_finders.add((r, c))

    # ── Módulos de datos ──────────────────────────────────────────────────────
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if (r, c) in finders:
                continue
            if not val:
                continue
            # Posición en píxeles con offset de quiet zone
            px = (c + border_cells) * cell_px + gap
            py = (r + border_cells) * cell_px + gap
            pw = cell_px - 2 * gap
            _draw_rounded_rect(draw, px, py, px + pw, py + pw, mod_r, fg)

    # ── Finder patterns ───────────────────────────────────────────────────────
    for br, bc in finder_origins:
        _draw_finder_pattern(
            draw=draw,
            origin_r=br + border_cells,
            origin_c=bc + border_cells,
            cell=cell_px,
            gap=gap,
            fg=fg,
            bg=bg,
            eye=eye,
            roundness=module_roundness,
        )

    # ── Logo central ──────────────────────────────────────────────────────────
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")

        # Tamaño máximo seguro del logo (la librería qrcode ya garantiza
        # que con ERROR_CORRECT_H se puede cubrir hasta 30% del área)
        max_logo_cells = n * logo_scale
        max_logo_px = int(max_logo_cells * cell_px)
        max_logo_px = min(max_logo_px, int(img_size * 0.28))  # hard cap 28%

        # Escalar preservando relación de aspecto
        lw, lh = logo.size
        ratio = min(max_logo_px / lw, max_logo_px / lh)
        new_lw = int(lw * ratio)
        new_lh = int(lh * ratio)
        logo = logo.resize((new_lw, new_lh), Image.LANCZOS)

        # Centrar
        lx = (img_size - new_lw) // 2
        ly = (img_size - new_lh) // 2

        # Fondo blanco cuadrado/redondeado detrás del logo
        pad = int(cell_px * 0.3)
        bg_logo = Image.new("RGB", (new_lw + 2 * pad, new_lh + 2 * pad), bg)
        bg_draw = ImageDraw.Draw(bg_logo)
        bg_logo_r = int(cell_px * 0.4)
        bg_draw.rounded_rectangle(
            [(0, 0), (new_lw + 2 * pad - 1, new_lh + 2 * pad - 1)],
            radius=bg_logo_r,
            fill=bg,
        )
        img.paste(bg_logo, (lx - pad, ly - pad))

        # Pegar logo con canal alfa
        img.paste(logo, (lx, ly), mask=logo.split()[3])

    return img


# ─────────────────────────────────────────────────────────────────────────────
# Generación SVG
# ─────────────────────────────────────────────────────────────────────────────

def _svg_rounded_rect(
    x: float, y: float, w: float, h: float, r: float, fill: str
) -> str:
    """Genera un elemento SVG <rect> con esquinas redondeadas."""
    return (
        f'<rect x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" '
        f'rx="{r:.3f}" ry="{r:.3f}" fill="{fill}"/>\n'
    )


def _svg_finder(
    origin_r: int,
    origin_c: int,
    cell: float,
    eye_hex: str,
    bg_hex: str,
    roundness: float,
) -> str:
    """Genera el SVG de un finder pattern con estilo squircle."""
    px = origin_c * cell
    py = origin_r * cell

    outer_w = 7 * cell
    outer_r = outer_w * roundness * 0.22

    inner_offset = cell
    inner_w = 5 * cell
    inner_r = inner_w * roundness * 0.18

    dot_offset = 2 * cell
    dot_w = 3 * cell
    dot_r = dot_w * roundness * 0.35

    svg = ""
    svg += _svg_rounded_rect(px, py, outer_w, outer_w, outer_r, eye_hex)
    svg += _svg_rounded_rect(
        px + inner_offset, py + inner_offset, inner_w, inner_w, inner_r, bg_hex
    )
    svg += _svg_rounded_rect(
        px + dot_offset, py + dot_offset, dot_w, dot_w, dot_r, eye_hex
    )
    return svg


def _render_svg(
    matrix: list[list[bool]],
    fg_hex: str,
    bg_hex: str,
    eye_hex: str,
    module_roundness: float,
    cell_svg: float = 10.0,
    border_cells: int = _BORDER_CELLS,
    gap_ratio: float = _GAP_RATIO,
) -> str:
    """Genera el SVG completo del QR como string."""
    n = len(matrix)
    total_cells = n + 2 * border_cells
    size = total_cells * cell_svg

    gap = cell_svg * gap_ratio
    mod_w = cell_svg - 2 * gap
    mod_r = mod_w / 2 * module_roundness

    finders = _finder_zones(n)
    finder_origins = [(0, 0), (0, n - 7), (n - 7, 0)]

    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {size:.3f} {size:.3f}" '
        f'width="{size:.3f}" height="{size:.3f}" '
        f'shape-rendering="geometricPrecision">\n'
    )
    # Fondo
    lines.append(f'<rect width="{size:.3f}" height="{size:.3f}" fill="{bg_hex}"/>\n')

    # Módulos de datos
    for r, row in enumerate(matrix):
        for c, val in enumerate(row):
            if (r, c) in finders or not val:
                continue
            px = (c + border_cells) * cell_svg + gap
            py = (r + border_cells) * cell_svg + gap
            lines.append(_svg_rounded_rect(px, py, mod_w, mod_w, mod_r, fg_hex))

    # Finder patterns
    for br, bc in finder_origins:
        lines.append(
            _svg_finder(
                origin_r=br + border_cells,
                origin_c=bc + border_cells,
                cell=cell_svg,
                eye_hex=eye_hex,
                bg_hex=bg_hex,
                roundness=module_roundness,
            )
        )

    lines.append("</svg>\n")
    return "".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────────────────────

def generate_styled_qr(
    data: str,
    output_png: str | None = None,
    output_svg: str | None = None,
    logo_path: str | None = None,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    eye_color: str | None = None,
    module_roundness: float = 0.8,
    logo_scale: float = 0.22,
    cell_px: int = _CELL_PX,
    border_cells: int = _BORDER_CELLS,
    dpi: int = _DPI,
) -> tuple[Image.Image, str]:
    """
    Genera un QR estilo "rounded premium" con módulos redondeados,
    finder patterns squircle y overlay de logo opcional.

    Parámetros
    ----------
    data            : Texto o URL a codificar.
    output_png      : Ruta donde guardar el PNG. Si None, no se guarda.
    output_svg      : Ruta donde guardar el SVG. Si None, no se guarda.
    logo_path       : PNG con transparencia para centrar en el QR.
    fg_color        : Color de los módulos (#RRGGBB).
    bg_color        : Color de fondo (#RRGGBB).
    eye_color       : Color de los finder patterns. Usa fg_color si None.
    module_roundness: 0.0 = cuadrado, 1.0 = círculo completo.
                      Rango recomendado: 0.6 – 0.95.
    logo_scale      : Fracción del QR que puede ocupar el logo (0.15 – 0.28).
    cell_px         : Píxeles por módulo al exportar PNG.
    border_cells    : Módulos de quiet zone.
    dpi             : DPI de metadatos del PNG exportado.

    Retorna
    -------
    (img_pillow, svg_string)

    Tweaking rápido
    ---------------
    · Aspecto más orgánico    → module_roundness=0.95, cell_px=36, gap_ratio implícito 0.14
    · Aspecto minimalista     → module_roundness=0.5, fg_color="#1a1a2e"
    · Ojos con acento oscuro  → eye_color="#1a1a2e", fg_color="#4a4a6a"
    · Logo prominente         → logo_scale=0.26 (máximo seguro con H)
    """
    # Normalizar colores
    _fg = _parse_color(fg_color)
    _bg = _parse_color(bg_color)
    _eye = _parse_color(eye_color) if eye_color else _fg
    _eye_hex = eye_color if eye_color else fg_color

    # Generar matriz QR
    matrix = _get_qr_matrix(data)

    # ── PNG ───────────────────────────────────────────────────────────────────
    img = _render_png(
        matrix=matrix,
        logo_path=logo_path,
        fg=_fg,
        bg=_bg,
        eye=_eye,
        module_roundness=module_roundness,
        logo_scale=logo_scale,
        cell_px=cell_px,
        border_cells=border_cells,
        dpi=dpi,
    )

    if output_png:
        Path(output_png).parent.mkdir(parents=True, exist_ok=True)
        img.save(output_png, "PNG", dpi=(dpi, dpi), optimize=True)

    # ── SVG ───────────────────────────────────────────────────────────────────
    svg_string = _render_svg(
        matrix=matrix,
        fg_hex=fg_color,
        bg_hex=bg_color,
        eye_hex=_eye_hex,
        module_roundness=module_roundness,
        border_cells=border_cells,
    )

    if output_svg:
        Path(output_svg).parent.mkdir(parents=True, exist_ok=True)
        Path(output_svg).write_text(svg_string, encoding="utf-8")

    return img, svg_string


def generate_styled_qr_png_bytes(
    data: str,
    logo_path: str | None = None,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    eye_color: str | None = None,
    module_roundness: float = 0.8,
    logo_scale: float = 0.22,
    cell_px: int = _CELL_PX,
    border_cells: int = _BORDER_CELLS,
    dpi: int = _DPI,
) -> bytes:
    """
    Variante de ``generate_styled_qr`` que devuelve el PNG como bytes en
    memoria (útil para pipelines sin fichero temporal).
    """
    img, _ = generate_styled_qr(
        data=data,
        logo_path=logo_path,
        fg_color=fg_color,
        bg_color=bg_color,
        eye_color=eye_color,
        module_roundness=module_roundness,
        logo_scale=logo_scale,
        cell_px=cell_px,
        border_cells=border_cells,
        dpi=dpi,
    )
    buf = BytesIO()
    img.save(buf, "PNG", dpi=(dpi, dpi), optimize=True)
    return buf.getvalue()


def generate_styled_qr_svg_bytes(
    data: str,
    fg_color: str = "#000000",
    bg_color: str = "#FFFFFF",
    eye_color: str | None = None,
    module_roundness: float = 0.8,
    border_cells: int = _BORDER_CELLS,
) -> bytes:
    """
    Variante de ``generate_styled_qr`` que devuelve el SVG como bytes UTF-8
    (útil para embedding directo en HTTP responses o PDFs).
    """
    _, svg_string = generate_styled_qr(
        data=data,
        fg_color=fg_color,
        bg_color=bg_color,
        eye_color=eye_color,
        module_roundness=module_roundness,
        border_cells=border_cells,
    )
    return svg_string.encode("utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# Ejemplo de uso (ejecutar directamente como script)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    generate_styled_qr(
        data="https://globalai.es/agentcamp",
        output_png="agentcamp.png",
        output_svg="agentcamp.svg",
        logo_path="logo.png",  # opcional — elimina si no tienes logo
        fg_color="#000000",
        bg_color="#F3F3F3",
        eye_color="#000000",
        module_roundness=0.9,
        logo_scale=0.20,
        cell_px=40,
        dpi=300,
    )
    print("✅ QR generado: agentcamp.png / agentcamp.svg")
