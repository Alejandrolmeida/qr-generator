# Tests

Scripts de prueba y validación del proyecto.

## test_qr_styles.py

Genera 4 variantes de QR para validar visualmente el generador premium
antes de integrarlo en producción.

```bash
# Desde la raíz del proyecto
PYTHONPATH=backend python3 tests/test_qr_styles.py
```

Los archivos de salida se guardan en `output/qr_test/` (excluido de git por `.gitignore`).
