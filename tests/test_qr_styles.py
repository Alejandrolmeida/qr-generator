#!/usr/bin/env python3
"""
test_qr_styles.py — Script de demostración del nuevo generador QR premium.

Genera 4 variantes de QR para verificar visualmente el resultado antes
de integrar en producción. Los archivos se guardan en output/qr_test/.

Uso:
    # Desde la raíz del proyecto
    PYTHONPATH=backend python3 tests/test_qr_styles.py
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Asegurar que el módulo backend sea importable (tests/ está un nivel por debajo de la raíz)
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.services.qr_service import generate_styled_qr  # noqa: E402

OUTPUT_DIR = Path("output/qr_test")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEST_URL = "https://globalai.es/agentcamp"
LOGO = "logo.png" if Path("logo.png").exists() else None


def _print_ok(name: str, png: str, svg: str) -> None:
    print(f"  ✅  {name}")
    print(f"      PNG → {png}")
    print(f"      SVG → {svg}")


print("\n🎨 Generando variantes QR premium...\n")


# ─── Variante 1: Estilo por defecto (negro sobre blanco) ─────────────────────
generate_styled_qr(
    data=TEST_URL,
    output_png=str(OUTPUT_DIR / "v1_default.png"),
    output_svg=str(OUTPUT_DIR / "v1_default.svg"),
    logo_path=LOGO,
    fg_color="#000000",
    bg_color="#FFFFFF",
    eye_color="#000000",
    module_roundness=0.85,
    logo_scale=0.20,
)
_print_ok("Variante 1 — Default (negro/blanco)", "v1_default.png", "v1_default.svg")


# ─── Variante 2: Aspecto ORGÁNICO máximo ─────────────────────────────────────
# module_roundness=0.95 → módulos casi circulares
# Mayor separación visual entre celdas
generate_styled_qr(
    data=TEST_URL,
    output_png=str(OUTPUT_DIR / "v2_organic.png"),
    output_svg=str(OUTPUT_DIR / "v2_organic.svg"),
    logo_path=LOGO,
    fg_color="#1a1a2e",
    bg_color="#F8F8FF",
    eye_color="#16213e",
    module_roundness=0.95,
    logo_scale=0.22,
    cell_px=44,   # módulos ligeramente más grandes = más espacio entre ellos
)
_print_ok("Variante 2 — Orgánico máximo (círculos)", "v2_organic.png", "v2_organic.svg")


# ─── Variante 3: Aspecto MINIMALISTA ─────────────────────────────────────────
# Menos redondeo, colores sobrios
generate_styled_qr(
    data=TEST_URL,
    output_png=str(OUTPUT_DIR / "v3_minimal.png"),
    output_svg=str(OUTPUT_DIR / "v3_minimal.svg"),
    logo_path=LOGO,
    fg_color="#2d2d2d",
    bg_color="#FAFAFA",
    eye_color="#2d2d2d",
    module_roundness=0.50,
    logo_scale=0.18,
)
_print_ok("Variante 3 — Minimalista (semiredondeado)", "v3_minimal.png", "v3_minimal.svg")


# ─── Variante 4: OJOS con acento de color ────────────────────────────────────
# Finder patterns en color de acento (azul Global AI)
generate_styled_qr(
    data=TEST_URL,
    output_png=str(OUTPUT_DIR / "v4_accent_eyes.png"),
    output_svg=str(OUTPUT_DIR / "v4_accent_eyes.svg"),
    logo_path=LOGO,
    fg_color="#222222",
    bg_color="#FFFFFF",
    eye_color="#005BAB",   # azul corporativo en los ojos
    module_roundness=0.88,
    logo_scale=0.22,
)
_print_ok(
    "Variante 4 — Ojos con acento (#005BAB)",
    "v4_accent_eyes.png",
    "v4_accent_eyes.svg",
)


print(f"\n📁 Todos los archivos guardados en: {OUTPUT_DIR.resolve()}\n")
print("💡 Tweaking rápido:")
print("   · Más orgánico   → module_roundness=0.95, cell_px=44")
print("   · Más minimalista → module_roundness=0.40-0.55")
print("   · Ojos oscuros   → eye_color='#1a1a2e', fg_color='#3a3a5a'")
print("   · Logo mayor     → logo_scale=0.26 (máximo seguro con ERROR_CORRECT_H)\n")
