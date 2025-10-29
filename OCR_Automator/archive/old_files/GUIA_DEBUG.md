# 🔧 Sistema de Debug - OCR Automator

## ¿Qué hace el sistema de debug?

El sistema de debug te permite ver **exactamente** qué está leyendo el OCR de cada PDF, paso a paso, para que puedas entender y mejorar la extracción de datos.

## 🚀 Cómo usar el debug

### Método 1: Menu interactivo (Más fácil)
1. Ejecuta `MENU_OCR_AUTOMATOR.bat`
2. Selecciona opción **3. 🔍 DEBUG: OCR paso a paso**
3. ¡Listo! El sistema generará reportes detallados

### Método 2: Script directo
```bash
cd OCR_Automator
python run_debug_test.py
```

### Método 3: Comandos manuales
```bash
# Paso 1: OCR con debug
python ocr_to_csv.py --client Itau --pdfs-dir pdfs/Itau --debug --verbose

# Paso 2: Procesamiento con debug
python process_itau_auto_v2.py --input debug_extraction.csv -vv
```

## 📊 Archivos generados

### 1. Reporte HTML interactivo
- **Archivo**: `debug_output/debug_report_YYYYMMDD_HHMMSS.html`
- **Qué contiene**: Interfaz web completa con:
  - Texto OCR extraído de cada página
  - Campos detectados y extraídos
  - Calidad del texto OCR
  - Patrones encontrados (RUTs, montos, fechas, etc.)
  - Pasos de procesamiento detallados

### 2. Datos JSON detallados
- **OCR**: `debug_output/ocr_debug_YYYYMMDD_HHMMSS.json`
- **Procesamiento**: `debug_output/processing_debug_YYYYMMDD_HHMMSS.json`

### 3. CSV extraído
- **Archivo**: `debug_extraction.csv`
- **Qué contiene**: Datos extraídos en formato CSV para procesamiento

### 4. Excel final
- **Archivo**: `DEBUG_FINAL_RESULT.xlsx`
- **Qué contiene**: Resultado final con geolocalización incluida

## 🔍 Cómo interpretar el debug

### En el reporte HTML verás:

#### Pestaña "📄 Datos OCR"
- **Por cada PDF**:
  - Número de páginas procesadas
  - Calidad del texto (barra de porcentaje)
  - Texto completo extraído por OCR
  - Campos específicos encontrados
  - Patrones detectados (RUTs, montos, fechas)

#### Pestaña "⚙️ Procesamiento"
- **Cada transformación de datos**:
  - Valor original → Valor final
  - Tipo de transformación aplicada
  - Si la transformación fue exitosa

#### Pestaña "📊 Resumen"
- **Estadísticas generales**:
  - PDFs procesados
  - Páginas analizadas  
  - Campos extraídos
  - Transformaciones realizadas

## 🎯 Casos de uso del debug

### 1. **Ver qué lee el OCR**
Si quieres saber exactamente qué texto está extrayendo:
- Abre el reporte HTML
- Ve a "Datos OCR"
- Revisa el "Texto extraído (OCR)" de cada página

### 2. **Verificar campos extraídos**
Para ver qué campos se detectaron:
- En "Datos OCR" → "Campos extraídos"
- Los campos en **verde** tienen datos
- Los campos en **amarillo** están vacíos

### 3. **Mejorar patrones de extracción**
Si faltan datos:
- Revisa "Patrones encontrados" 
- Ve qué patrones (RUTs, montos, fechas) se detectaron
- Ajusta `config/Itau.json` con mejores regex

### 4. **Analizar calidad del OCR**
- La barra de "Calidad del texto" indica qué tan bien se leyó
- Texto con baja calidad puede necesitar mejor preprocesamiento

## ⚠️ Problemas comunes y soluciones

### "No se extraen datos"
1. **Verificar calidad OCR**: Si está bajo 50%, el PDF puede tener mala calidad
2. **Revisar patrones**: En `config/Itau.json` ajustar las expresiones regulares
3. **Tesseract**: Instalar Tesseract para mejor reconocimiento

### "Campos vacíos"
1. **Ver texto OCR**: Verificar si los datos están realmente en el texto
2. **Ajustar regex**: En `config/Itau.json` mejorar los patrones de búsqueda
3. **Normalización**: Revisar si hay caracteres especiales que interfieren

### "Datos incorrectos"
1. **Ver transformaciones**: En la pestaña "Procesamiento" verificar qué se transformó
2. **Validar fuente**: Comparar con el texto OCR original
3. **Ajustar constantes**: En `constants.py` revisar las validaciones

## 🛠️ Archivos de configuración

### `config/Itau.json`
```json
{
  "regex": {
    "operacion": "Op[.:\\s]*([0-9]{6,})",
    "monto": "la cantidad de\\s*\\$?\\s*([0-9\\.,]+)",
    "rut": "RUT[:\\s]*([0-9\\.\\-Kk]+)",
    // ... más patrones
  }
}
```

### `constants.py`
- `CANONICAL_HEADERS`: Columnas finales del Excel
- `HEADER_ALIASES`: Mapeo de variaciones de nombres
- `VALID_COMUNAS`: Comunas válidas para validación

## 📈 Consejos para optimizar

1. **Iteración**: Usa el debug → ajusta configuración → vuelve a probar
2. **Patrones específicos**: Crea regex más específicos para tus documentos
3. **Validación**: Agrega validaciones en `constants.py` para datos específicos
4. **Geolocalización**: Las direcciones se mejoran automáticamente
5. **Limpieza**: Los archivos temporales se limpian automáticamente

## 🎉 ¡Listo!

Con este sistema de debug puedes:
- Ver exactamente qué lee el OCR
- Identificar por qué faltan datos
- Mejorar la precisión de extracción
- Verificar cada paso del proceso
- Optimizar para tus documentos específicos

**Recuerda**: El reporte HTML es interactivo, puedes hacer clic en las secciones para expandir/contraer y navegar fácilmente por todos los datos.