"""
Storage Service — Azure Blob Storage.
Gestiona subida, descarga y generación de SAS tokens para templates,
excels y ZIPs de salida.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO

from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.storage.blob import (
    BlobClient,
    BlobSasPermissions,
    BlobServiceClient,
    generate_blob_sas,
)

from app.core.config import get_settings


def _get_blob_service_client() -> BlobServiceClient:
    """
    En local/dev usa AZURE_STORAGE_CONNECTION_STRING.
    En producción (Container Apps) usa Managed Identity.
    """
    s = get_settings()
    conn_str = s.azure_storage_connection_string.get_secret_value()
    if conn_str:
        return BlobServiceClient.from_connection_string(conn_str)
    # Managed Identity (producción)
    credential = DefaultAzureCredential()
    account_url = f"https://{s.azure_storage_account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=credential)


def _ensure_container(client: BlobServiceClient, container: str) -> None:
    """Crea el contenedor si no existe (solo en entornos de desarrollo)."""
    try:
        client.create_container(container)
    except Exception:
        pass  # Already exists


def upload_blob(
    container: str,
    blob_name: str,
    data: bytes | BinaryIO,
    overwrite: bool = True,
) -> str:
    """Sube datos a Azure Blob Storage. Devuelve el nombre del blob."""
    client = _get_blob_service_client()
    _ensure_container(client, container)
    blob_client: BlobClient = client.get_blob_client(container=container, blob=blob_name)
    blob_client.upload_blob(data, overwrite=overwrite)
    return blob_name


def download_blob_to_file(container: str, blob_name: str, local_path: str | Path) -> None:
    """Descarga un blob a un fichero local."""
    client = _get_blob_service_client()
    blob_client = client.get_blob_client(container=container, blob=blob_name)
    with open(str(local_path), "wb") as f:
        f.write(blob_client.download_blob().readall())


def download_blob_bytes(container: str, blob_name: str) -> bytes:
    """Descarga un blob y devuelve sus bytes."""
    client = _get_blob_service_client()
    blob_client = client.get_blob_client(container=container, blob=blob_name)
    return blob_client.download_blob().readall()


def blob_exists(container: str, blob_name: str) -> bool:
    client = _get_blob_service_client()
    blob_client = client.get_blob_client(container=container, blob=blob_name)
    try:
        blob_client.get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False


def generate_sas_url(
    container: str,
    blob_name: str,
    ttl_hours: int | None = None,
    permission: BlobSasPermissions = BlobSasPermissions(read=True),
) -> str:
    """Genera una URL SAS de solo lectura para un blob."""
    s = get_settings()
    hours = ttl_hours or s.sas_token_ttl_hours
    expiry = datetime.now(timezone.utc) + timedelta(hours=hours)

    client = _get_blob_service_client()

    # Con Managed Identity necesitamos obtener una user delegation key
    conn_str = s.azure_storage_connection_string.get_secret_value()
    if conn_str:
        # Local / connection string: extraer account name y key
        parts = dict(
            p.split("=", 1)
            for p in conn_str.split(";")
            if "=" in p
        )
        account_name = parts.get("AccountName", "")
        account_key = parts.get("AccountKey", "")
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container,
            blob_name=blob_name,
            account_key=account_key,
            permission=permission,
            expiry=expiry,
        )
        return f"https://{account_name}.blob.core.windows.net/{container}/{blob_name}?{sas_token}"
    else:
        # Managed Identity: user delegation key
        udk = client.get_user_delegation_key(
            key_start_time=datetime.now(timezone.utc),
            key_expiry_time=expiry,
        )
        sas_token = generate_blob_sas(
            account_name=s.azure_storage_account_name,
            container_name=container,
            blob_name=blob_name,
            user_delegation_key=udk,
            permission=permission,
            expiry=expiry,
        )
        return (
            f"https://{s.azure_storage_account_name}.blob.core.windows.net"
            f"/{container}/{blob_name}?{sas_token}"
        )


def blob_md5(container: str, blob_name: str) -> str:
    """Devuelve el MD5 del blob (para caché de análisis IA)."""
    data = download_blob_bytes(container, blob_name)
    return hashlib.md5(data).hexdigest()
