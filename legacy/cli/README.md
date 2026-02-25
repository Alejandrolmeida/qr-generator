# Legacy CLI Tools

Estos scripts son las herramientas de línea de comandos originales del proyecto,
anteriores a la arquitectura API/microservicio actual.

Se mantienen exclusivamente como referencia histórica. **No se usan en producción.**

| Script | Descripción |
|--------|-------------|
| `create_card.py` | Genera tarjetas de acreditación en PDF con QR embebido (PyMuPDF) |
| `label.py` | Genera etiquetas individuales con QR (qrcode + fitz) |
| `init.py` | Script de entrada que procesa un CSV/Excel y llama a `create_card.py` |

## Uso (solo referencia)

```bash
# Requiere: pip install python-dotenv PyMuPDF qrcode pillow openpyxl
python3 init.py
```

La funcionalidad equivalente en producción reside en:
- `backend/app/services/pdf_service.py`
- `backend/app/services/qr_service.py`
- `backend/app/services/excel_service.py`
