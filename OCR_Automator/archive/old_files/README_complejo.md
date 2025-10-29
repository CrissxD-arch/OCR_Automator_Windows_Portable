# 🚀 OCR Automator

**Automatización completa PDF → Excel para contratos bancarios**

## ✨ ¿Qué hace?

Convierte automáticamente PDFs de contratos bancarios (Itaú, Santander, etc.) en archivos Excel limpios y formateados, extrayendo todos los campos importantes como RUT, nombre, montos, fechas, etc.

## 🎯 Uso rápido

1. **Coloca tus PDFs** en `OCR_Automator/pdfs/Itau/`
2. **Presiona F5** en VS Code
3. **¡Listo!** Tu Excel aparece como `RESULTADOS_ITAU_FINAL.xlsx`

## 📊 Resultado

- Excel profesional con 15+ campos extraídos
- Datos limpios y normalizados  
- Formato con colores y números
- Listo para análisis o reportes

## 🛠️ Instalación y Uso

### Método 1: Menu Interactivo (Recomendado)
1. **Ejecuta `MENU_OCR_AUTOMATOR.bat`** - Script con menú interactivo
2. **Selecciona opción 1** - Para probar con datos de ejemplo
3. **¡Listo!** - Tu Excel aparece como `RESULTADOS_ITAU_FINAL.xlsx`

### Método 2: Línea de comandos
1. **Instala dependencias**: `pip install -r OCR_Automator/requirements.txt`
2. **Ejecuta el script**: `python OCR_Automator/process_itau_auto_v2.py`
3. **Usa tus PDFs**: Colócalos en `OCR_Automator/pdfs/Itau/`

### Método 3: Pipeline completo (PDFs → Excel)
- Usa `python OCR_Automator/pipeline_completo.py --verbose`

## 📁 Archivos principales

- `MENU_OCR_AUTOMATOR.bat` - **🆕 Menu interactivo para Windows**
- `pipeline_completo.py` - Script principal (PDF → Excel)
- `process_itau_auto_v2.py` - Limpiador de datos (CSV → Excel)
- `ocr_to_csv.py` - Extractor OCR (PDF → CSV)
- `constants.py` - **🆕 Configuración y patrones**
- `config/Itau.json` - Patrones OCR específicos
- `TEST_INSTRUCTIONS.md` - **🆕 Guía de pruebas**

## ✅ Estado del proyecto

- ✅ **Sistema funcionando** - Probado con datos de ejemplo
- ✅ **Errores corregidos** - Importaciones y tipos arreglados  
- ✅ **Menu interactivo** - Fácil de usar en Windows
- ✅ **Documentación completa** - Instrucciones y ejemplos
- ✅ **Datos de prueba** - CSV de ejemplo incluido
