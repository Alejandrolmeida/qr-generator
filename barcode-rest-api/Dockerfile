FROM python:3.9

# Define el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiar los archivos de la aplicación
COPY . .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Asegurar que src/ está en el PYTHONPATH
ENV PYTHONPATH=/app/src

# Exponer el puerto 5000 para Azure
EXPOSE 5000

# Usar Gunicorn con la ruta correcta
CMD ["gunicorn", "-b", "0.0.0.0:5000", "src.app:app"]