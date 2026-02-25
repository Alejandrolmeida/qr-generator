"""
Configuración central del backend (pydantic-settings).
Todos los valores se leen desde variables de entorno o fichero .env.
Los campos marcados SecretStr nunca se imprimen en logs ni en repr().
"""
from functools import lru_cache
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_name: str = "QR Accreditation API"
    app_version: str = "2.0.0"
    debug: bool = False
    cors_origins: list[str] = ["*"]

    # ── Azure Storage ─────────────────────────────────────────────────────────
    # Usar Managed Identity en producción (dejar vacío) o connection string local
    azure_storage_connection_string: SecretStr = SecretStr("")
    azure_storage_account_name: str = ""
    azure_storage_container_templates: str = "templates"
    azure_storage_container_excels: str = "excels"
    azure_storage_container_output: str = "output"
    # SAS token TTL en horas
    sas_token_ttl_hours: int = 24

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    # En producción NO se inyecta — la UAMI usa Cognitive Services OpenAI User para auth keyless.
    # En local dev: establecer AZURE_OPENAI_API_KEY en .env para bypass.
    azure_openai_endpoint: str = ""
    azure_openai_api_key: SecretStr = SecretStr("")
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment_gpt4o: str = "gpt-4o"
    # Umbral de confianza mínimo antes de pedir confirmación humana
    ai_confidence_threshold: float = 0.7

    # ── Generación de PDFs ────────────────────────────────────────────────────
    output_folder: str = "/tmp/qr-output"
    fonts_folder: str = "/app/fonts"
    # Resolución para renderizar páginas PDF como PNG (análisis IA + preview)
    pdf_render_dpi: int = 150
    # Máximo PDFs procesados en paralelo
    max_concurrent_pdf_jobs: int = 4

    # ── Columnas Excel por defecto (Eventbrite en español) ───────────────────
    col_attendee_id: str = "Número de código de barras"
    col_first_name: str = "Nombre del asistente"
    col_last_name: str = "Apellidos del asistente"
    col_ticket_type: str = "Tipo de entrada"
    col_company: str = "Empresa"

    # ── Tipos de entrada por plantilla ───────────────────────────────────────
    ticket_types_staff: str = "Helpers"
    ticket_types_speaker: str = "Speakers"

    # ── Job storage (en memoria para desarrollo; Redis para producción) ───────
    use_redis_jobs: bool = False
    redis_url: str = "redis://localhost:6379"


@lru_cache
def get_settings() -> Settings:
    return Settings()
