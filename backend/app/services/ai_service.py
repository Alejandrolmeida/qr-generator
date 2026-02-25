"""
AI Service — análisis de plantillas PDF con GPT-4o Vision.
Detecta automáticamente la zona de colocación del QR y el texto del asistente.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from app.core.config import get_settings
from app.models.schemas import TemplatePositionResult

# ─── Prompt ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Eres un asistente especializado en analizar diseños de acreditaciones de eventos.
Tu tarea es identificar con precisión el área reservada para el código QR
y el nombre del asistente en el diseño proporcionado.
Responde SIEMPRE en JSON válido, sin texto adicional."""

_USER_PROMPT = """\
Analiza este diseño de acreditación de evento.

Identifica el rectángulo blanco, caja clara o área reservada donde se debe colocar:
  1. El código QR del asistente
  2. El nombre y apellidos del asistente (encima del QR)

IMPORTANTE sobre el sistema de coordenadas:
  - El PDF usa el sistema ReportLab donde Y=0 está en el borde INFERIOR de la página.
  - qr_x y qr_y son las coordenadas de la esquina INFERIOR-IZQUIERDA del QR.
  - page_width y page_height son las dimensiones totales de la página en puntos (pt).
  - 1 pulgada = 72 puntos. Un A4 apaisado tiene ~842×595 pt.

Devuelve SOLO este JSON (sin markdown, sin explicaciones):
{
  "qr_x": <int: coordenada X esquina inferior-izquierda del QR en pt>,
  "qr_y": <int: coordenada Y esquina inferior-izquierda del QR en pt (y=0 abajo)>,
  "qr_size": <int: tamaño recomendado del QR en pt, normalmente entre 80 y 180>,
  "page_width": <int: ancho de la página en pt>,
  "page_height": <int: alto de la página en pt>,
  "confidence": <float: confianza de 0.0 a 1.0>,
  "notes": "<descripción breve en español de lo que has identificado>"
}"""


# ─── Cache en memoria (por hash de blob) ─────────────────────────────────────
_analysis_cache: dict[str, TemplatePositionResult] = {}


def _get_client() -> AzureOpenAI:
    """Crea el cliente Azure OpenAI.

    - Producción (Container Apps + UAMI): env var AZURE_OPENAI_API_KEY vacía
      → autenticación keyless mediante DefaultAzureCredential.
    - Desarrollo local (.env con AZURE_OPENAI_API_KEY definida)
      → usa la API key directamente.
    """
    s = get_settings()
    api_key = s.azure_openai_api_key.get_secret_value()
    if api_key:
        return AzureOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=api_key,
            api_version=s.azure_openai_api_version,
        )
    # Sin API key — la UAMI tiene el rol 'Cognitive Services OpenAI User'
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=s.azure_openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version=s.azure_openai_api_version,
    )


def analyze_template_image(
    png_bytes: bytes,
    blob_hash: str = "",
) -> TemplatePositionResult:
    """
    Envía una imagen PNG de la plantilla a GPT-4o Vision y devuelve
    las coordenadas de colocación del QR.

    Args:
        png_bytes:  PNG renderizado de la primera página del PDF.
        blob_hash:  MD5 del blob original — se usa para cachear resultados.

    Returns:
        TemplatePositionResult con las coordenadas detectadas.
    """
    # Caché: si ya analizamos este blob, devolvemos el resultado guardado
    if blob_hash and blob_hash in _analysis_cache:
        return _analysis_cache[blob_hash]

    s = get_settings()
    client = _get_client()

    b64_image = base64.b64encode(png_bytes).decode("utf-8")

    response = client.chat.completions.create(
        model=s.azure_openai_deployment_gpt4o,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _USER_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        temperature=0,
        max_tokens=512,
    )

    raw = response.choices[0].message.content or ""

    # Extraer JSON aunque haya texto envolvente
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not json_match:
        raise ValueError(f"GPT-4o no devolvió JSON válido: {raw[:200]}")

    data = json.loads(json_match.group())
    result = TemplatePositionResult(
        qr_x=int(data["qr_x"]),
        qr_y=int(data["qr_y"]),
        qr_size=int(data["qr_size"]),
        page_width=int(data["page_width"]),
        page_height=int(data["page_height"]),
        confidence=float(data["confidence"]),
        notes=str(data.get("notes", "")),
        blob_hash=blob_hash,
    )

    # Guardar en caché
    if blob_hash:
        _analysis_cache[blob_hash] = result

    return result


def invalidate_cache(blob_hash: str) -> None:
    """Borra la entrada de caché para un hash concreto (tras re-subir la plantilla)."""
    _analysis_cache.pop(blob_hash, None)
