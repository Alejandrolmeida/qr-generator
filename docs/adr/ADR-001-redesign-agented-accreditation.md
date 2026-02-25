# ADR-001: Rediseño completo — Generador de Acreditaciones con Agente IA

**Estado**: Propuesta  
**Fecha**: 2026-02-25  
**Autor**: Alejandro L. Meida  

---

## 1. Resumen Ejecutivo

El sistema actual genera acreditaciones PDF con QR a partir de plantillas y un Excel de Eventbrite, pero **requiere conocimiento técnico** (editar `.env`, instalar Python) cada vez que cambia el diseño de la plantilla.

La nueva arquitectura elimina esa fricción con dos capas desacopladas:

| Capa | Tecnología | Responsabilidad |
|------|------------|-----------------|
| **Backend API** | FastAPI + Azure Blob Storage | Recibir archivos, analizar plantillas con IA, generar PDFs, devolver ZIP |
| **Frontend Agente** | Chainlit + Azure OpenAI GPT-4o | Conversación guiada con el diseñador, previsualización, ajuste interactivo |

El diseñador **solo necesita un navegador**. Sube plantillas y Excel, habla con el agente, descarga el ZIP.

---

## 2. Context & Requirements

### 2.1 Estado actual (pain points)

```
▼ Diseñador crea nueva plantilla PDF para cada evento
▼ El POSITION y QR_SIZE del .env hay que recalcular a mano (pt por pt)
▼ El diseñador no puede ejecutar el script (no tiene Python)
▼ Requiere desarrollador para cada cambio de diseño
▼ No hay previsualización antes de generar los 500+ PDFs
▼ El proceso tarda, sin feedback de progreso
```

### 2.2 Requisitos funcionales

1. El usuario sube plantillas PDF (staff, speaker, asistente) y un Excel de Eventbrite.
2. El sistema detecta **automáticamente** la zona de colocación del QR leyendo la plantilla con IA.
3. El agente muestra una **previsualización** de una acreditación de ejemplo antes de lanzar el batch.
4. El usuario puede **ajustar** la posición y tamaño del QR conversacionalmente ("súbelo 20 puntos", "hazlo más grande").
5. El usuario puede **mapear columnas** del Excel si el export no sigue el formato Eventbrite estándar.
6. Tras aprobación, el backend genera todos los PDFs, los comprime en ZIP y lo sube a Azure Blob Storage.
7. El agente devuelve un **enlace SAS de 24 h** para descargar el ZIP.
8. El sistema soporta **múltiples tipos de entrada** (staff/speaker/asistente) con distintas plantillas.
9. Proceso **incremental**: si se añaden nuevos asistentes, solo genera los que faltan.

### 2.3 Requisitos no funcionales

| Requisito | Target |
|-----------|--------|
| Disponibilidad | Usuario final solo necesita navegador |
| Seguridad | SAS token con TTL 24 h; blobs privados |
| Escalabilidad | Generación asíncrona, no bloquea el chat |
| Portabilidad | Docker; desplegable en Azure Container Apps |
| Observabilidad | Logs estructurados + Application Insights |

---

## 3. Arquitectura Propuesta

### 3.1 Diagrama de componentes

```
┌─────────────────────────────────────────────────────────────────┐
│  USUARIO DISEÑADOR (navegador)                                  │
└───────────────────────┬─────────────────────────────────────────┘
                        │  HTTP (WebSocket)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  FRONTEND  ─  Chainlit App  (puerto 8000)                       │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Agente conversacional (Azure OpenAI GPT-4o)            │   │
│  │                                                         │   │
│  │  ① Recibe archivos (PDF templates + Excel)             │   │
│  │  ② Llama a Backend /api/analyze-template               │   │
│  │  ③ Muestra preview PNG en el chat                      │   │
│  │  ④ Acepta ajustes del usuario en lenguaje natural       │   │
│  │  ⑤ Llama a Backend /api/generate (async)               │   │
│  │  ⑥ Muestra progreso y devuelve enlace SAS              │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────┬─────────────────────────────────────────┘
                        │  REST API (HTTP)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│  BACKEND  ─  FastAPI App  (puerto 8080)                         │
│                                                                 │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────────┐  │
│  │  /upload     │  │  /analyze     │  │  /generate          │  │
│  │  (templates  │  │  (GPT-4o      │  │  (batch async,      │  │
│  │   + Excel)   │  │   Vision →    │  │   ZIP → Blob)       │  │
│  │              │  │   auto-pos)   │  │                     │  │
│  └──────────────┘  └───────────────┘  └─────────────────────┘  │
│                                                                 │
│  ┌──────────────────┐   ┌────────────────────────────────────┐  │
│  │  PDF Engine      │   │  Storage Service                   │  │
│  │  (PyMuPDF        │   │  (Azure Blob: templates/,          │  │
│  │   + ReportLab)   │   │   excels/, output/{job-id}/)       │  │
│  └──────────────────┘   └────────────────────────────────────┘  │
└───────────────────────┬─────────────────────────────────────────┘
                        │
          ┌─────────────┴──────────────┐
          ▼                            ▼
┌──────────────────┐       ┌───────────────────────┐
│  Azure Blob      │       │  Azure OpenAI         │
│  Storage         │       │  (GPT-4o Vision)      │
│  (private)       │       │  Análisis plantillas  │
└──────────────────┘       └───────────────────────┘
```

### 3.2 Flujo conversacional del agente

```
Agente: "¡Hola! Soy tu asistente de acreditaciones.
         Empecemos. ¿Tienes plantillas distintas para Staff, 
         Ponentes y Asistentes generales?"

  → Sí → "Perfecto, sube los 3 PDFs"      → [file upload x3]
  → No → "¿Solo una plantilla para todos?" → [file upload x1]

Agente: "Ahora sube el Excel de Eventbrite"   → [file upload x1]

[Backend analiza plantilla con GPT-4o Vision]
[Backend genera PDF de preview con asistente ficticio]

Agente: [muestra imagen PNG del preview]
        "He detectado la zona de colocación automáticamente.
         ¿El QR y el nombre se ven bien, o quieres ajustar algo?"

  → "Sube el QR 15 puntos"     → ajusta posición, nuevo preview
  → "El QR es muy pequeño"     → aumenta QR_SIZE, nuevo preview
  → "Perfecto, genera todo"    → lanza batch

[Barra de progreso en el chat]

Agente: "✅ Generadas 487 acreditaciones.
         Descarga tu ZIP aquí (enlace válido 24 h):
         https://storage.../output/job-abc123.zip?sas=..."
```

### 3.3 Análisis de plantilla con GPT-4o Vision

El backend convierte la primera página del PDF a PNG (300 dpi) y envía la imagen a GPT-4o con el siguiente prompt:

```
"Este es el diseño de una acreditación de evento. 
Identifica el rectángulo blanco o área reservada donde se debe colocar 
el código QR y el nombre del asistente.
Devuelve SOLO un JSON con estas claves:
  - qr_x (int): coordenada x inferior-izquierda del centro del área (en puntos PDF)
  - qr_y (int): coordenada y inferior-izquierda (sistema ReportLab, y=0 abajo)
  - qr_size (int): tamaño recomendado del QR en puntos (entre 80 y 200)
  - page_width (int): ancho total de la página en puntos
  - page_height (int): alto total de la página en puntos
  - confidence (float): confianza 0.0-1.0
  - notes (str): descripción breve de lo detectado (en español)"
```

Si la confianza es < 0.7, el agente avisa al usuario y le pide usar el modo manual ("haz clic en la esquina superior-izquierda del área blanca").

---

## 4. Estructura de directorios del nuevo proyecto

```
qr-generator/
│
├── backend/                          # ← NUEVO: FastAPI service
│   ├── app/
│   │   ├── main.py                   #   FastAPI app + CORS + middleware
│   │   ├── core/
│   │   │   ├── config.py             #   Settings (pydantic-settings)
│   │   │   └── logging.py            #   Structured logging
│   │   ├── routers/
│   │   │   ├── upload.py             #   POST /api/upload/template
│   │   │   │                         #         /api/upload/excel
│   │   │   ├── analyze.py            #   POST /api/analyze/{session_id}
│   │   │   ├── preview.py            #   POST /api/preview/{session_id}
│   │   │   └── generate.py           #   POST /api/generate/{session_id}
│   │   │                             #   GET  /api/status/{job_id}
│   │   ├── services/
│   │   │   ├── pdf_service.py        #   Lógica PDF (refactor de create_card.py)
│   │   │   ├── excel_service.py      #   Leer Excel, detectar columnas
│   │   │   ├── storage_service.py    #   Azure Blob Storage + SAS tokens
│   │   │   ├── ai_service.py         #   GPT-4o Vision → auto-posicionamiento
│   │   │   └── job_service.py        #   Cola de jobs, progress tracking
│   │   └── models/
│   │       └── schemas.py            #   Pydantic models (request/response)
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                         # ← NUEVO: Chainlit agent
│   ├── app.py                        #   Entry point Chainlit
│   ├── agent/
│   │   ├── accreditation_agent.py    #   Lógica de la conversación
│   │   ├── tools.py                  #   Tool calls (upload, preview, generate)
│   │   └── prompts.py                #   System prompts del agente
│   ├── client/
│   │   └── backend_client.py         #   HTTP client hacia el backend API
│   ├── .chainlit/
│   │   └── config.toml               #   Config de Chainlit (branding, auth)
│   ├── public/
│   │   └── logo.png                  #   Logo evento
│   ├── Dockerfile
│   └── requirements.txt
│
├── bicep/                            # IaC Azure
│   ├── main.bicep
│   ├── modules/
│   │   ├── container-app.bicep       #   Azure Container Apps
│   │   ├── storage.bicep             #   Azure Blob Storage (privado)
│   │   ├── openai.bicep              #   Azure OpenAI (GPT-4o)
│   │   ├── container-registry.bicep  #   ACR para imágenes Docker
│   │   └── monitoring.bicep          #   Log Analytics + App Insights
│   └── parameters/
│       ├── dev.bicepparam
│       └── prod.bicepparam
│
├── .github/
│   └── workflows/
│       ├── build-push.yml            #   Build + push Docker images → ACR
│       └── deploy.yml                #   Deploy Container Apps via Bicep
│
├── docker-compose.yml                # Desarrollo local
├── docker-compose.override.yml       # Overrides locales (secrets, hot-reload)
│
│
│   ── LEGADO (se mantiene para compatibilidad, sin cambios) ──────────────────
├── create_card.py
├── init.py
├── label.py
├── barcode-rest-api/
├── qr-listing-app/
│   ──────────────────────────────────────────────────────────────────────────
│
└── docs/
    └── adr/
        └── ADR-001-redesign-agented-accreditation.md  ← este fichero
```

---

## 5. Servicios Azure seleccionados

| Servicio | SKU | Justificación | Coste est./mes |
|----------|-----|---------------|----------------|
| Azure Container Apps | Consumption | Escala a 0 cuando no hay uso; perfecto para workloads intermitentes de eventos | ~$5–15 |
| Azure Blob Storage | LRS Standard | Templates, Excels y ZIPs de salida; privado + SAS | ~$2–5 |
| Azure OpenAI (GPT-4o) | S0 | Vision para análisis de plantillas; conversación del agente | ~$10–30 (según uso) |
| Azure Container Registry | Basic | Almacenar imágenes Docker del backend y frontend | ~$5 |
| Azure Log Analytics | Per GB | Logs de contenedores + Application Insights | ~$3–8 |
| **Total estimado** | | | **~$25–63/mes** |

> 💡 Todos los recursos dentro de un único Resource Group por entorno: `rg-qrgen-dev`, `rg-qrgen-prod`.

---

## 6. Seguridad

- Blobs privados; acceso solo mediante SAS tokens con expiración de 24 h.
- Managed Identity para Container Apps → acceso a Blob Storage y Azure OpenAI sin secretos.
- Chainlit puede configurarse con autenticación (OAuth con GitHub/Microsoft) para no ser público.
- Secretos (connection strings, API keys) en Azure Container Apps secrets o Azure Key Vault.
- HTTPS forzado en todos los endpoints (Azure Container Apps gestiona TLS automáticamente).

---

## 7. Plan de implementación

### Fase 1 — Backend API (Semana 1)
- [ ] Refactorizar `create_card.py` como `backend/app/services/pdf_service.py`
- [ ] Refactorizar `init.py` como `backend/app/services/excel_service.py`
- [ ] Implementar `storage_service.py` con Azure Blob Storage SDK
- [ ] Implementar `ai_service.py` con GPT-4o Vision para análisis de plantillas
- [ ] Endpoints: `/upload`, `/analyze`, `/preview`, `/generate`, `/status`
- [ ] Dockerfile backend
- [ ] Tests unitarios de servicios PDF y Excel

### Fase 2 — Frontend Chainlit (Semana 2)
- [ ] Implementar flujo conversacional completo en `frontend/app.py`
- [ ] Integrar file uploads de Chainlit con el backend
- [ ] Mostrar preview PNG en el chat
- [ ] Ajuste conversacional de posición y tamaño
- [ ] Mostrar progreso de generación en tiempo real (SSE/polling)
- [ ] Mostrar enlace SAS al finalizar
- [ ] Dockerfile frontend

### Fase 3 — Docker Compose local (Semana 2)
- [ ] `docker-compose.yml` con backend + frontend + variables de entorno
- [ ] Variables de entorno de ejemplo en `.env.example` actualizado

### Fase 4 — Azure IaC (Semana 3)
- [ ] Módulo Bicep Container Apps (backend + frontend)
- [ ] Módulo Bicep Storage privado
- [ ] Módulo Bicep Azure OpenAI
- [ ] Módulo Bicep ACR
- [ ] Módulo Bicep Monitoring
- [ ] Parámetros dev y prod

### Fase 5 — CI/CD GitHub Actions (Semana 3)
- [ ] Workflow `build-push.yml`: build imágenes → push ACR
- [ ] Workflow `deploy.yml`: deploy Bicep → Container Apps
- [ ] OIDC authentication (secretless)
- [ ] Environments: dev con auto-deploy, prod con approval manual

---

## 8. Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| GPT-4o detecta mal la zona de QR | Media | Alto | Preview obligatorio antes de batch; modo manual como fallback |
| El diseñador sube plantillas con áreas de texto superpuestas | Media | Medio | El agente pregunta por zona impactada antes de generar |
| Generación de 500+ PDFs es lenta en Container Apps | Baja | Medio | Jobs asíncronos + polling; posible escalado de réplicas |
| Coste de GPT-4o si se analizan muchas plantillas | Baja | Bajo | Cache de análisis por hash de PDF; solo se re-analiza si cambia |
| Enlace SAS expirado antes de descargar | Baja | Bajo | TTL 24 h; posibilidad de regenerar el link |

---

## 9. Decisión

Se acepta el rediseño con las tecnologías propuestas. El proyecto legado (`create_card.py`, `init.py`) se mantiene sin cambios como fallback para usuarios técnicos que prefieran la CLI.

---

## 10. Referencias

- [Chainlit Documentation](https://docs.chainlit.io)
- [FastAPI Documentation](https://fastapi.tiangolo.com)
- [Azure Container Apps](https://learn.microsoft.com/azure/container-apps/)
- [Azure Blob Storage SDK Python](https://learn.microsoft.com/azure/storage/blobs/storage-quickstart-blobs-python)
- [Azure OpenAI Vision](https://learn.microsoft.com/azure/ai-services/openai/how-to/gpt-with-vision)
- [PyMuPDF (fitz)](https://pymupdf.readthedocs.io)
