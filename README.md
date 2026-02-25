# QR Code PDF Generator — AgentCamp

Genera **credenciales PDF personalizadas** para asistentes a eventos, insertando un código QR y el nombre del asistente sobre una plantilla PDF base. El caso de uso real es el evento **AgentCamp 2026** registrado en Eventbrite.

---

## Estructura del proyecto

```
qr-generator/
├── init.py              # Punto de entrada batch (procesa Excel completo)
├── label.py             # Punto de entrada individual (un asistente)
├── create_card.py       # Motor: genera QR, lo fusiona con la plantilla PDF
├── .env                 # Configuración (rutas, columnas, mapeo de plantillas)
├── requirements.txt     # Dependencias Python
├── dockerfile           # Empaqueta label.py como .exe Windows con PyInstaller
├── mcp.json             # Configuración MCP servers para GitHub Copilot
├── fonts/               # Familia tipográfica DejaVu (TTF)
├── templates/           # Plantillas PDF base (una por rol)
├── input/               # Ficheros Excel de Eventbrite (.xlsx)
└── output/              # PDFs generados + ZIP final
```

---

## Plantillas PDF por tipo de entrada

Hay tres plantillas en `templates/`, cada una con diseño diferente según el rol:

| Fichero | Rol | Tipos de entrada Eventbrite |
|---|---|---|
| `templates/staff.pdf` | Staff / Organización | `Helpers` |
| `templates/speaker.pdf` | Ponentes | `Speakers` |
| `templates/atendee.pdf` | Resto de asistentes | `General Admission`, `Donación (desde 1 euro)`, `Estudiantes`, `Patrocinadores`, `Sponsor` |

La selección de plantilla es **automática** según el valor de la columna `Tipo de entrada` del Excel.  
Se configura en `.env` mediante `TICKET_TYPES_STAFF` y `TICKET_TYPES_SPEAKER`.

---

## Fuente de datos — Export Eventbrite

El fichero de entrada es el **informe de asistentes exportado desde Eventbrite** en formato `.xlsx`.

### Cómo descargar el Excel desde Eventbrite

La lista de asistentes se obtiene desde el panel de administración del evento:

**Ruta de navegación:**  
`Panel de control del evento` → `Informes` → `Informes del evento` → `Asistentes`

**URL directa** (sustituir el ID del evento):
```
https://www.eventbrite.es/myevent/<EVENT_ID>/reports/attendees?reportingTab=preview
```
> Para AgentCamp 2026: `https://www.eventbrite.es/myevent/1980480271806/reports/attendees?reportingTab=preview`

**Pasos para exportar:**

1. Abrir la URL anterior en el navegador (sesión de organizador requerida)
2. En la parte superior, hacer clic en la pestaña **Exportaciones**
3. Seleccionar el formato **XLS** (Excel)
4. Descargar el fichero y guardarlo en la carpeta `input/` del proyecto

### Columnas requeridas

El proyecto está configurado para el export en **español**. Columnas que usa el script:

| Variable `.env` | Columna Eventbrite (ES) | Columna Eventbrite (EN) |
|---|---|---|
| `COL_ATTENDEE_ID` | `Número de código de barras` | `Attendee #` |
| `COL_FIRST_NAME` | `Nombre del asistente` | `Final Attendee First Name` |
| `COL_LAST_NAME` | `Apellidos del asistente` | `Final Attendee Last Name` |
| `COL_TICKET_TYPE` | `Tipo de entrada` | `Ticket Type` |

> Si el export viene en inglés, descomentar el bloque inglés del `.env` y comentar el español.

### Distribución real de entradas — AgentCamp 2026 (367 asistentes)

| Tipo de entrada | Cantidad | Plantilla usada |
|---|---|---|
| General Admission | 150 | `atendee.pdf` |
| Donación (desde 1 euro) | 97 | `atendee.pdf` |
| Speakers | 39 | `speaker.pdf` |
| Sponsor | 31 | `atendee.pdf` |
| Helpers | 19 | `staff.pdf` |
| Estudiantes | 17 | `atendee.pdf` |
| Patrocinadores | 13 | `atendee.pdf` |

---

## Instalación

```bash
git clone https://github.com/Alejandrolmeida/qr-generator.git
cd qr-generator

python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### Dependencias principales

| Librería | Uso |
|---|---|
| `PyMuPDF (fitz)` | Fusionar QR sobre la plantilla PDF |
| `qrcode` | Generar el código QR en formato SVG |
| `svglib` + `reportlab` | Renderizar SVG y texto sobre PDF temporal |
| `Pillow` | Procesado de imágenes |
| `pandas` + `openpyxl` | Leer el Excel de Eventbrite |
| `python-dotenv` | Cargar configuración desde `.env` |

---

## Configuración — `.env`

```dotenv
# Carpetas
INPUT_FOLDER=./input
OUTPUT_FOLDER=./output

# Plantillas PDF por rol
TEMPLATE_STAFF=./templates/staff.pdf          # → Helpers
TEMPLATE_SPEAKER=./templates/speaker.pdf      # → Speakers
TEMPLATE_ATTENDEE=./templates/atendee.pdf     # → todo lo demás

# Valores de "Tipo de entrada" que activan cada plantilla (separados por coma)
TICKET_TYPES_STAFF=Helpers
TICKET_TYPES_SPEAKER=Speakers
# El resto usa TEMPLATE_ATTENDEE automáticamente

# Posición (x,y) y tamaño del QR en el PDF (en puntos PDF)
POSITION=50,335
QR_SIZE=200

# Columnas del Excel de Eventbrite (export en ESPAÑOL)
COL_ATTENDEE_ID=Número de código de barras
COL_FIRST_NAME=Nombre del asistente
COL_LAST_NAME=Apellidos del asistente
COL_TICKET_TYPE=Tipo de entrada

# Columnas para export en INGLÉS (descomentar si procede)
# COL_ATTENDEE_ID=Attendee #
# COL_FIRST_NAME=Final Attendee First Name
# COL_LAST_NAME=Final Attendee Last Name
# COL_TICKET_TYPE=Ticket Type
```

---

## Uso

### Modo batch — procesar todos los asistentes del Excel

```bash
# Procesa el .xlsx más reciente en INPUT_FOLDER
python init.py

# O indica la ruta explícitamente
python init.py ./input/Attendees_64398446537_20260224_223935_805.xlsx
```

**Salida:**
- Un PDF por asistente en `output/attendee-{codigo_barras}.pdf`
- Al terminar, todos los PDFs quedan comprimidos en `output/attendees_YYYYMMDD_HHMMSS.zip`
- Los PDFs individuales se eliminan tras comprimir

**Log de ejemplo:**
```
[1/367] Miguel Ángel Cantero Víllora | General Admission → atendee.pdf
[2/367] Armando Felipe Fuentes Denis | Speakers → speaker.pdf
...
Summary — Staff: 19 | Speakers: 39 | Attendees: 309
```

### Modo individual — generar una sola credencial

```bash
# Con número de código de barras manual
python label.py 1405443386322575492966001

# Con número aleatorio (para pruebas)
python label.py -r
```

Se pedirá nombre y apellidos por consola.

---

## Flujo interno del motor (`create_card.py`)

```
1. Copiar plantilla PDF base → output/attendee-{id}.pdf
2. Generar QR en SVG (qrcode, ERROR_CORRECT_H)
3. Escalar SVG a QR_SIZE × QR_SIZE puntos
4. Crear PDF temporal (ReportLab):
   - Dibujar QR en coordenadas POSITION (x, y)
   - Escribir NOMBRE en mayúsculas a la derecha del QR
   - Escribir APELLIDOS en mayúsculas debajo del nombre
   - Auto-ajuste de fuente (máx. 30pt → mín. 10pt) para que quepa en 300pt de ancho
   - Fuente: DejaVuSans-Bold (fonts/DejaVuSans-Bold.ttf)
5. Fusionar PDF temporal sobre la copia de la plantilla (PyMuPDF)
6. Guardar resultado final, eliminar temporales
```

---

## Empaquetado como .exe Windows

El `dockerfile` genera un ejecutable Windows portable usando `cdrx/pyinstaller-windows`:

```bash
docker build -t qr-generator-windows .
# El .exe queda en dist/label.exe
```

Incluye en el bundle: `.env`, `templates/visitor_template_05.pdf`, `fonts/DejaVuSans-Bold.ttf`

---

## API de Eventbrite (referencia)

La API REST v3 de Eventbrite permite obtener asistentes programáticamente sin exportar el Excel:

```bash
# Todos los asistentes de un evento
curl -X GET https://www.eventbriteapi.com/v3/events/{EVENT_ID}/attendees/ \
  -H 'Authorization: Bearer PERSONAL_OAUTH_TOKEN'
```

Campos relevantes en la respuesta JSON:

| Campo JSON | Equivalente columna Excel (ES) |
|---|---|
| `attendees[].barcodes[0].barcode` | `Número de código de barras` |
| `attendees[].profile.first_name` | `Nombre del asistente` |
| `attendees[].profile.last_name` | `Apellidos del asistente` |
| `attendees[].ticket_class_name` | `Tipo de entrada` |

La respuesta es paginada (50 por página por defecto). El export Excel sigue siendo la opción más directa para procesado masivo.

---

## Licencia

MIT — ver [LICENSE](LICENSE)
