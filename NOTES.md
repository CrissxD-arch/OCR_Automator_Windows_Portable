# OCR Automator · Notas del proyecto

Actualizado: 2025-10-29

## Resumen
- Soporte web con login y selector de banco (Itaú / Santander).
- Procesadores unificados para PP/CC:
  - `OCR_Automator/process_itau_unified_v1.py`
  - `OCR_Automator/process_santander_unified_v1.py`
- Mejoras OCR y normalización:
  - Corrección N→Ñ y acentos (ej.: PENA→PEÑA, NUNOA→ÑUÑOA, VINA→VIÑA, ZUNIGA→ZÚÑIGA, etc.).
  - Ampliación de comunas y fuzzy matching, con variantes acentuadas y sin acento.
- Limpieza automática de subidas temporales.
- Páginas legales básicas: Términos y Privacidad.
- Git inicializado con `.gitignore` para excluir datos sensibles y temporales.

## Cómo ejecutar (local)
1) Crear/activar entorno
```powershell
py -3.11 -m venv .venv
& ".venv/Scripts/Activate.ps1"
pip install -r OCR_Automator/requirements_web.txt
```
2) Ejecutar web (elige una):
```powershell
& ".venv/Scripts/python.exe" "OCR_Automator/webapp/app.py"
# o
& ".\RUN_WEBSERVER.bat"
```
3) Abrir navegador:
- Local: http://127.0.0.1:5000
- En la red (otra PC): http://<TU_IP_LOCAL>:5000
  - Si hace falta, permitir el puerto 5000:
```powershell
netsh advfirewall firewall add rule name="OCR Automator 5000" dir=in action=allow protocol=TCP localport=5000
```

## Login y configuración
- Credenciales por defecto (desarrollo): admin / change_me.
- Archivo de credenciales local (no versionado): `OCR_Automator/config/web_config.json`.
  - Se incluye `web_config.example.json` como plantilla.
- Secret de Flask (recomendado en producción): variable de entorno `OCR_AUTOMATOR_SECRET`.

## Flujo web
1) Login → Subir PDFs.
2) Seleccionar banco: Itaú o Santander.
3) Seleccionar calidad OCR (Rápida/Estándar/Alta) y geocodificación (opcional).
4) Procesar → Redirige a “Resultados”.
5) Descarga Excel y Debug.
   - Salidas: `outputs/<Banco>/web/Itau_results_UNIFIED_*.xlsx` o `Santander_results_UNIFIED_*.xlsx`.

## Normalización Ñ y comunas
- Se aplica N→Ñ a nombres, direcciones y comunas con un diccionario extendido.
- `fuzzy_comuna` ahora normaliza antes de comparar y cubre variantes con/sin acentos.
- Próximo posible: cargar comunas desde `OCR_Automator/config/comunas_chile.txt` para edición sin tocar código.

## Páginas legales
- Footer con enlaces:
  - Términos: `/legal/terminos` (archivo `webapp/templates/terms.html`).
  - Privacidad: `/legal/privacidad` (archivo `webapp/templates/privacy.html`).
- Archivo `THIRD_PARTY_NOTICES.md` con licencias de Tesseract, Poppler, Flask, etc.

## Git (backup y trabajo remoto)
- Repo ya inicializado. Para conectar a GitHub:
```powershell
git remote add origin https://github.com/<tu_usuario>/OCR_Automator_Windows_Portable.git
git branch -M main
git push -u origin main
```
- Archivos excluidos por `.gitignore`:
  - `.venv/`, `outputs/`, `OCR_Automator/pdfs/`, `RI*/`, `web_uploads/`, `OCR_Automator/config/web_config.json`.
- Ejemplo de config: `OCR_Automator/config/web_config.example.json`.

## Tesseract/Poppler
- Tesseract (Windows): `C:\Users\cdiaz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`.
- Poppler: `C:\poppler\Library\bin` (usado por pdf2image).

## Próximos pasos sugeridos
- [ ] Cargar comunas desde archivo `config/comunas_chile.txt` + botón para recargar sin reiniciar.
- [ ] Limpieza automática de resultados viejos (p. ej., >14 días) en `outputs/<Banco>/web`.
- [ ] Contador de errores por ejecución en “Resultados” con enlace directo al Debug.
- [ ] Geocodificación con control de tasa y reintentos; posibilidad de desactivar para grandes lotes.
- [ ] Hash de contraseñas en `web_config.json` (p. ej., bcrypt) y política de contraseñas.
- [ ] Integrar nuevos bancos (mismo patrón que Santander/Itaú).
- [ ] Opción de exportar directamente a una base de datos (SQLite/PostgreSQL) además del Excel.

## Contacto/Notas
- Si aparece una variante OCR no cubierta (ej.: confusión de tilde o Ñ), anótala aquí y se incorporará al normalizador.
