# QR Code PDF Generator

## Descripción del Proyecto

Este proyecto genera archivos PDF personalizados con códigos QR y nombres de asistentes a partir de un archivo de Excel. También incluye la funcionalidad para comprimir todos los archivos PDF generados en un archivo `.zip` y eliminar los archivos PDF originales.

## Requisitos

- Python 3.6 o superior
- Las siguientes bibliotecas de Python:
  - `fitz` (PyMuPDF)
  - `qrcode`
  - `Pillow`
  - `svglib`
  - `reportlab`
  - `python-dotenv`
  - `pandas`
  - `openpyxl`

## Instalación

1. Clona el repositorio:

   ```bash
   git clone https://github.com/tu_usuario/qr-generator.git
   cd qr-generator

2. Crea un entorno virtual y actívalo:

   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows, usa `venv\Scripts\activate`

3. Instala las dependencias:

   ```bash
   pip install -r requirements.txt

4. Crea un archivo .env en el directorio raíz del proyecto con el siguiente contenido:

   ```bash
   TEMPLATE_PDF=./templates/visitor_template.pdf
   INPUT_FOLDER=./input
   OUTPUT_FOLDER=./output
   POSITION=50,335
   QR_SIZE=200
   ```

## Uso
1.Coloca el archivo de Excel con los datos de los asistentes en la carpeta especificada por INPUT_FOLDER en el archivo .env.
2.Ejecuta el script init.py para generar los archivos PDF:

   ```bash
   python init.py [ruta_del_archivo_excel]
   ```

Si proporcionas la ruta_del_archivo_excel, se usará ese archivo.
- Si no proporcionas la ruta_del_archivo_excel, se buscará el archivo más reciente en la carpeta especificada por INPUT_FOLDER.

3. El script generará los archivos PDF en la carpeta especificada por OUTPUT_FOLDER y luego comprimirá todos los archivos PDF en un archivo .zip con la fecha y hora de ejecución en el nombre.

# Ejemplo

   ```bash
   python init.py ./input/attendees.xlsx
   ```

Este comando generará los archivos PDF a partir del archivo attendees.xlsx y los comprimirá en un archivo .zip.

## Docker Instructions

1. **Build the Docker image:**
   ```
   docker build -t qr-code-pdf-generator .
   ```

2. **Run the Docker container:**
   ```
   docker run -p 5000:5000 --env-file .env qr-code-pdf-generator
   ```

3. **Using Docker Compose:**
   ```
   docker-compose up
   ```

# Contribuciones 
Las contribuciones son bienvenidas. Por favor, abre un issue o un pull request para discutir cualquier cambio que te gustaría realizar.

# Licencia
Este proyecto está licenciado bajo la Licencia MIT. Consulta el archivo LICENSE para más detalles.
