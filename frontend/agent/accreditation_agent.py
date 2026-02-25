"""
Lógica del agente de acreditaciones.
Gestiona el estado de la conversación y las llamadas al backend.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

import chainlit as cl
from openai import AsyncAzureOpenAI

from agent.prompts import SYSTEM_PROMPT
from client import backend_client as api


# ─── Estado de sesión ─────────────────────────────────────────────────────────

def _init_state() -> dict:
    return {
        "session_id": str(uuid.uuid4()),
        "templates_uploaded": [],   # roles ya subidos: ["attendee", "speaker", "staff"]
        "excel_uploaded": False,
        "column_map": None,         # ExcelColumnMap dict
        "positions": {},            # {role: {qr_x, qr_y, qr_size}}
        "preview_approved": False,
        "active_role": "attendee",  # rol que se está configurando ahora
        "history": [],              # mensajes OpenAI
    }


def _state() -> dict:
    return cl.user_session.get("state")  # type: ignore[return-value]


def _save_state(s: dict) -> None:
    cl.user_session.set("state", s)


def _oai_client() -> AsyncAzureOpenAI:
    """Crea el cliente AsyncAzureOpenAI.

    - Producción (Container Apps + UAMI): AZURE_OPENAI_API_KEY no está definida
      → autenticación keyless mediante DefaultAzureCredential (Cognitive Services OpenAI User).
    - Desarrollo local (.env con AZURE_OPENAI_API_KEY definida) → usa la API key.
    """
    import os
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")

    if api_key:
        return AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
        )
    # Sin API key → UAMI con rol 'Cognitive Services OpenAI User'
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )
    return AsyncAzureOpenAI(
        azure_endpoint=endpoint,
        azure_ad_token_provider=token_provider,
        api_version=api_version,
    )


# ─── Chat start ───────────────────────────────────────────────────────────────

async def on_chat_start() -> None:
    state = _init_state()
    _save_state(state)

    await cl.Message(
        content=(
            "¡Hola! Soy tu asistente para generar acreditaciones de evento con QR 🎫\n\n"
            "Voy a guiarte paso a paso para que en pocos minutos tengas todas las "
            "acreditaciones listas para imprimir, sin necesidad de tocar ningún fichero de configuración.\n\n"
            "**Primera pregunta:** ¿utilizas plantillas distintas para diferentes tipos de entrada "
            "(por ejemplo, una plantilla para asistentes generales, otra para ponentes y otra para staff), "
            "o tienes una única plantilla para todos?"
        )
    ).send()


# ─── Mensaje con ficheros adjuntos ────────────────────────────────────────────

async def on_file_upload(files: list[cl.File], message_text: str) -> None:
    state = _state()

    for f in files:
        name_lower = f.name.lower()

        if name_lower.endswith(".pdf"):
            # Determinar rol por nombre del fichero o contexto
            role = _infer_role_from_filename(name_lower, state)
            content = f.content  # bytes

            msg = cl.Message(content=f"⏳ Subiendo plantilla **{f.name}** como `{role}`…")
            await msg.send()

            try:
                await api.upload_template(state["session_id"], role, f.name, content)
                state["templates_uploaded"].append(role)
                _save_state(state)
                msg.content = f"✅ Plantilla `{role}` subida correctamente."
                await msg.update()
            except Exception as e:
                msg.content = f"❌ Error al subir la plantilla: {e}"
                await msg.update()
                return

        elif name_lower.endswith((".xlsx", ".xls")):
            msg = cl.Message(content=f"⏳ Subiendo Excel **{f.name}**…")
            await msg.send()

            try:
                content = f.content
                await api.upload_excel(state["session_id"], f.name, content)
                state["excel_uploaded"] = True
                _save_state(state)
                msg.content = "✅ Excel subido correctamente."
                await msg.update()

                # Analizar columnas automáticamente
                await _analyze_and_confirm_columns(state)
            except Exception as e:
                msg.content = f"❌ Error al subir el Excel: {e}"
                await msg.update()
                return

    # Continuar el flujo si ya tenemos todo lo necesario
    await _advance_flow(state, message_text)


# ─── Mensaje de texto ─────────────────────────────────────────────────────────

async def on_message(message: cl.Message) -> None:
    state = _state()

    # Guard: si la sesión se perdió tras reinicio del servidor, reinicializar
    if state is None:
        state = _init_state()
        _save_state(state)
        # Reenviar saludo para que el usuario sepa que la sesión se reinició
        await cl.Message(
            content=(
                "_(La sesión expiró tras un reinicio del servidor — empezamos de nuevo)_\n\n"
                "¡Hola! Soy tu asistente para generar acreditaciones de evento con QR 🎫\n\n"
                "**Primera pregunta:** ¿utilizas plantillas distintas para diferentes tipos de entrada "
                "(por ejemplo, una plantilla para asistentes generales, otra para ponentes y otra para staff), "
                "o tienes una única plantilla para todos?"
            )
        ).send()
        return

    # Ficheros adjuntos en el mensaje
    if message.elements:
        files = [e for e in message.elements if hasattr(e, "content")]
        if files:
            await on_file_upload(files, message.content)
            return

    # Ajuste de posición en lenguaje natural
    if state.get("positions") and not state.get("preview_approved"):
        adjusted = _parse_position_adjustment(message.content, state)
        if adjusted:
            _save_state(state)
            await _show_preview(state)
            return

    # Confirmación de preview
    if _is_affirmative(message.content) and state.get("positions") and not state.get("preview_approved"):
        state["preview_approved"] = True
        _save_state(state)
        await _start_generation(state)
        return

    # Conversar con el agente GPT
    await _chat_with_agent(message.content, state)


# ─── Flujo principal ──────────────────────────────────────────────────────────

async def _advance_flow(state: dict, hint: str = "") -> None:
    """Avanza al siguiente paso del flujo según el estado actual."""
    if state["templates_uploaded"] and state["excel_uploaded"] and state["column_map"] and not state["positions"]:
        await _analyze_template_and_preview(state)


async def _analyze_and_confirm_columns(state: dict) -> None:
    msg = cl.Message(content="🔍 Analizando columnas del Excel…")
    await msg.send()
    try:
        result = await api.analyze_excel(state["session_id"])
        state["column_map"] = result["suggested_map"]
        _save_state(state)

        headers_list = "\n".join(f"  - `{h}`" for h in result["headers"])
        col = result["suggested_map"]
        msg.content = (
            f"He detectado las siguientes columnas en tu Excel:\n{headers_list}\n\n"
            f"**Mapeo sugerido:**\n"
            f"  - ID / código de barras → `{col['col_attendee_id']}`\n"
            f"  - Nombre → `{col['col_first_name']}`\n"
            f"  - Apellidos → `{col['col_last_name']}`\n"
            f"  - Tipo de entrada → `{col['col_ticket_type']}`\n"
            f"  - Empresa → `{col['col_company']}`\n\n"
            f"¿Es correcto este mapeo, o necesitas ajustar alguna columna?"
        )
        await msg.update()
    except Exception as e:
        msg.content = f"❌ Error al analizar el Excel: {e}"
        await msg.update()


async def _analyze_template_and_preview(state: dict) -> None:
    role = state.get("active_role", "attendee")
    msg = cl.Message(content=f"🔍 Analizando la plantilla `{role}` con IA para detectar la zona del QR…")
    await msg.send()

    try:
        result = await api.analyze_template(state["session_id"], role)
        pos = result["result"]
        state["positions"][role] = {
            "qr_x": pos["qr_x"],
            "qr_y": pos["qr_y"],
            "qr_size": pos["qr_size"],
        }
        _save_state(state)

        confidence_pct = int(pos["confidence"] * 100)
        note = f"\n\n> 💡 {pos['notes']}" if pos.get("notes") else ""
        warn = (
            "\n\n⚠️ **La detección tiene baja confianza** — revisa el preview con atención."
            if result.get("needs_human_review") else ""
        )
        msg.content = (
            f"✅ Zona detectada con **{confidence_pct}% de confianza**.{note}{warn}\n\n"
            f"Generando previsualización…"
        )
        await msg.update()

        await _show_preview(state)

    except Exception as e:
        msg.content = f"❌ Error al analizar la plantilla: {e}"
        await msg.update()


async def _show_preview(state: dict) -> None:
    role = state.get("active_role", "attendee")
    pos = state["positions"].get(role) or state["positions"].get("attendee")
    if not pos:
        await cl.Message(content="No tengo posición para generar el preview. Analiza la plantilla primero.").send()
        return

    try:
        result = await api.generate_preview(
            session_id=state["session_id"],
            role=role,
            qr_x=pos["qr_x"],
            qr_y=pos["qr_y"],
            qr_size=pos["qr_size"],
        )
        preview_url = result["preview_url"]

        # Mostrar imagen en el chat
        image = cl.Image(url=preview_url, name="preview.png", display="inline", size="large")
        await cl.Message(
            content=(
                "Esta es la previsualización de una acreditación de ejemplo:\n\n"
                "¿El QR y el nombre se ven correctamente, o quieres ajustar algo?\n"
                "_(Puedes decirme cosas como: \"sube el QR 15 puntos\", "
                "\"hazlo más grande\", \"bájalo un poco\")_"
            ),
            elements=[image],
        ).send()

    except Exception as e:
        await cl.Message(content=f"❌ Error al generar el preview: {e}").send()


async def _start_generation(state: dict) -> None:
    msg = cl.Message(content="🚀 Iniciando la generación de todas las acreditaciones…")
    await msg.send()

    try:
        job = await api.start_generation(
            session_id=state["session_id"],
            positions=state["positions"],
            column_map=state["column_map"],
        )
        job_id = job["job_id"]
        total = job["total_attendees"]

        msg.content = f"⏳ Job iniciado. Generando **{total}** acreditaciones…"
        await msg.update()

        # Polling cada 5 segundos
        last_generated = -1
        while True:
            await asyncio.sleep(5)
            status = await api.get_job_status(job_id)

            gen = status["generated"]
            skipped = status["skipped"]
            failed = status["failed"]
            pct = int((gen + skipped + failed) / max(total, 1) * 100)

            if gen != last_generated:
                msg.content = (
                    f"⏳ Progreso: {pct}% — "
                    f"✅ {gen} generadas · ⏭️ {skipped} omitidas · ❌ {failed} errores"
                )
                await msg.update()
                last_generated = gen

            if status["status"] in ("completed", "failed"):
                break

        if status["status"] == "completed":
            dl = status["download_url"]
            stats = status.get("stats", {})
            msg.content = (
                f"🎉 **¡Listo!** {status['generated']} acreditaciones generadas "
                f"({status['skipped']} omitidas · {status['failed']} errores).\n\n"
                f"📦 **[Descargar ZIP]({dl})** _(enlace válido 24 h)_\n\n"
                f"Desglose por tipo: {stats}"
            )
        else:
            msg.content = f"❌ La generación falló: {status.get('error', 'error desconocido')}"

        await msg.update()

    except Exception as e:
        msg.content = f"❌ Error al lanzar la generación: {e}"
        await msg.update()


# ─── Conversación fallback con GPT ────────────────────────────────────────────

async def _chat_with_agent(user_text: str, state: dict) -> None:
    import os

    try:
        client = _oai_client()
    except Exception as e:
        await cl.Message(content=f"❌ Error al conectar con Azure OpenAI: `{e}`").send()
        print(f"[ERROR] _oai_client() failed: {e}")
        return

    history: list[dict] = state.get("history", [])
    history.append({"role": "user", "content": user_text})

    try:
        response = await client.chat.completions.create(
            model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            messages=[{"role": "system", "content": SYSTEM_PROMPT}] + history,
            temperature=0.3,
            max_tokens=800,
            stream=True,
        )
    except Exception as e:
        await cl.Message(content=f"❌ Error al llamar a Azure OpenAI: `{e}`").send()
        print(f"[ERROR] chat.completions.create failed: {e}")
        history.pop()  # Revertir el mensaje del usuario
        return

    msg = cl.Message(content="")
    await msg.send()
    full = ""
    try:
        async for chunk in response:
            delta = chunk.choices[0].delta.content or "" if chunk.choices else ""
            await msg.stream_token(delta)
            full += delta
    except Exception as e:
        print(f"[ERROR] streaming failed: {e}")
        if not full:
            await cl.Message(content=f"❌ Error durante el streaming de respuesta: `{e}`").send()
            history.pop()
            return

    history.append({"role": "assistant", "content": full})
    state["history"] = history[-20:]  # ventana de 20 turnos
    _save_state(state)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _infer_role_from_filename(name: str, state: dict) -> str:
    if any(k in name for k in ("staff", "helper", "equipo")):
        return "staff"
    if any(k in name for k in ("speaker", "ponente", "ponentes")):
        return "speaker"
    # Si solo queda uno por subir, asignarlo
    remaining = [r for r in ("attendee", "speaker", "staff") if r not in state["templates_uploaded"]]
    return remaining[0] if remaining else "attendee"


_AFFIRMATIVE = re.compile(
    r"\b(sí|si|ok|vale|perfecto|correcto|adelante|generar|listo|confirmo|aprobado|apruebo)\b",
    re.IGNORECASE,
)


def _is_affirmative(text: str) -> bool:
    return bool(_AFFIRMATIVE.search(text))


_POSITION_PATTERNS = [
    (re.compile(r"(sube|arriba|subir).{0,15}(\d+)", re.IGNORECASE), "up"),
    (re.compile(r"(baja|abajo|bajar).{0,15}(\d+)", re.IGNORECASE), "down"),
    (re.compile(r"(izquierda|izquier).{0,15}(\d+)", re.IGNORECASE), "left"),
    (re.compile(r"(derecha|derechar).{0,15}(\d+)", re.IGNORECASE), "right"),
    (re.compile(r"(grande|grande|aumenta|más grande).{0,15}(\d*)", re.IGNORECASE), "bigger"),
    (re.compile(r"(pequeño|peque|reduce|más pequeño).{0,15}(\d*)", re.IGNORECASE), "smaller"),
]


def _parse_position_adjustment(text: str, state: dict) -> bool:
    """Ajusta la posición QR según petición en lenguaje natural. Devuelve True si se ajustó."""
    role = state.get("active_role", "attendee")
    pos = state["positions"].get(role) or state["positions"].get("attendee")
    if not pos:
        return False

    changed = False
    for pattern, direction in _POSITION_PATTERNS:
        m = pattern.search(text)
        if m:
            try:
                delta = int(m.group(2)) if m.group(2) else 15
            except (IndexError, ValueError):
                delta = 15

            if direction == "up":
                pos["qr_y"] += delta
            elif direction == "down":
                pos["qr_y"] = max(0, pos["qr_y"] - delta)
            elif direction == "left":
                pos["qr_x"] = max(0, pos["qr_x"] - delta)
            elif direction == "right":
                pos["qr_x"] += delta
            elif direction == "bigger":
                pos["qr_size"] = min(250, pos["qr_size"] + delta)
            elif direction == "smaller":
                pos["qr_size"] = max(50, pos["qr_size"] - delta)

            state["positions"][role] = pos
            changed = True

    return changed
