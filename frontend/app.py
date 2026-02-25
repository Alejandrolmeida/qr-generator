"""
Chainlit entry point — QR Accreditation Agent.

Autenticación: OAuth con Azure AD (Entra ID).
Solo el conjunto de emails definido en ALLOWED_EMAILS puede acceder.
Si ALLOWED_EMAILS está vacío, cualquier usuario del tenant tiene acceso.
"""
import os

import chainlit as cl

from agent.accreditation_agent import on_chat_start, on_message

# ── Lista blanca de usuarios autorizados ─────────────────────────────────────────────────
ALLOWED_EMAILS: set[str] = {
    e.strip()
    for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
    if e.strip()
}


# ── OAuth callback — autenticación AAD ───────────────────────────────────────────────
@cl.oauth_callback
def oauth_callback(
    provider_id: str,
    token: str,
    raw_user_data: dict,
    default_user: cl.User,
) -> cl.User | None:
    """
    Invocado por Chainlit tras la autenticación con AAD.
    Devuelve cl.User si el email está autorizado, None si se deniega.
    """
    # AAD puede devolver el email en distintos campos según el tipo de cuenta.
    email: str = (
        raw_user_data.get("mail")                # Graph API → cuenta normal
        or raw_user_data.get("email")            # token OAuth directo
        or raw_user_data.get("preferred_username")  # MSAL
        or raw_user_data.get("userPrincipalName")   # Graph API → cuenta externa (#EXT#)
        or raw_user_data.get("upn")
        or raw_user_data.get("unique_name")
        or ""
    )
    name: str = (
        raw_user_data.get("displayName")
        or raw_user_data.get("name")
        or email
    )

    print(f"[Auth] Email identificado: '{email}'")

    # Si ALLOWED_EMAILS está vacío, cualquier usuario del tenant puede entrar.
    if ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        print(f"[Auth] Acceso denegado: '{email}' no está en ALLOWED_EMAILS")
        return None

    print(f"[Auth] Acceso concedido: {email}")
    return cl.User(
        identifier=email,
        metadata={"name": name, "email": email},
    )


# ── Eventos de chat ─────────────────────────────────────────────────────────────

@cl.on_chat_start
async def start():
    await on_chat_start()


@cl.on_message
async def message(msg: cl.Message):
    await on_message(msg)
