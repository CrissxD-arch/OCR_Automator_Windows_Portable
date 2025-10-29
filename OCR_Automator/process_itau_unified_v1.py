#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_itau_unified_v1.py

Sistema unificado que detecta automáticamente si un PDF es PP (Pagaré) o CC (Crédito de Consumo)
y aplica la lógica de extracción correspondiente.

Integra:
- process_itau_pp_with_pdf_conversion_v4.py (para Pagarés)
- process_itau_cc_with_pdf_conversion_v5.py (para Crédito de Consumo)
- geocoding_utils.py (correcciones de referencia)

Características:
- Detección automática de tipo de documento
- Extracción especializada según tipo
- Correcciones de referencia basadas en Excel base
- Salida unificada a outputs/Itau/Itau_results_UNIFIED.xlsx
"""

import re
import shutil
import argparse
import time
from pathlib import Path
from datetime import datetime
import pandas as pd
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import difflib
import requests

# Importar utilidades de geocodificación y corrección
try:
    from geocoding_utils import (
        clean_and_fix_address,
        fix_comuna_ocr,
        apply_reference_corrections,
        validate_rut_dv
    )
    GEO_UTILS_AVAILABLE = True
    print("✅ Utilidades de geocodificación cargadas")
except ImportError:
    GEO_UTILS_AVAILABLE = False
    print("⚠️ Utilidades de geocodificación no disponibles")
    # Funciones dummy
    def clean_and_fix_address(address): return address
    def fix_comuna_ocr(comuna): return comuna
    def apply_reference_corrections(df): return df
    def validate_rut_dv(rut: str, dv: str) -> tuple[str, str, bool]: return rut, dv, True

# ---------------- CONFIG ----------------
TESSERACT_EXE = r"C:\Users\cdiaz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
POPPLER_BIN = r"C:\poppler\Library\bin"
PROJECT_ROOT = Path.cwd()
PDF_INPUT_DIR = PROJECT_ROOT / "pdfs" / "Itau"
TEMP_RI_ROOT = PROJECT_ROOT / "RI"
OUT_DIR = PROJECT_ROOT / "outputs" / "Itau"
OUT_XLSX = OUT_DIR / "Itau_results_UNIFIED.xlsx"
DEBUG_FILE = PROJECT_ROOT / "outputs" / "Itau_debug_unified.txt"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OCR-Automator/1.0 (cdiaz@ejemplo.com)"
# ----------------------------------------

# Verificar Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    test_img = Image.new('RGB', (100, 100), color='white')
    pytesseract.image_to_string(test_img, lang='spa')
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract disponible")
except Exception as e:
    TESSERACT_AVAILABLE = False
    print(f"⚠️ Tesseract no disponible: {e}")

# Columnas unificadas (incluye todos los campos de PP y CC)
UNIFIED_COLUMNS = [
    "OPERACION_1","RUT","DV","NOMBRE","DIRECCION","COMUNA",
    "FECHA_SUSCRIPCION_1","MONTO_CREDITO_1","CUOTAS_1","TASA_1","MONTO_CUOTA_1","MONTO_ULTIMA_CUOTA_1",
    "FECHA_VENCIMIENTO_1_CUOTA_1","FECHA_VENCIMIENTO_ULTIMA_CUOTA_1",
    "CUOTA_MOROSA_1","FECHA_CUOTA_MOROSA_1",
    "CAPITAL_1","EXHORTO","SUCURSAL","PRODUCTO","NOMBRE_APODERADO","NOMBRE_APODERADO_2"
]

COMUNAS = [
    # RM y variantes
    "SANTIAGO","LAS CONDES","PROVIDENCIA","ÑUÑOA","NUNOA","MAIPU","MAIPÚ","PUENTE ALTO","LA FLORIDA","LA REINA",
    "VITACURA","HUECHURABA","RECOLETA","INDEPENDENCIA","CONCHALI","CONCHALÍ","QUINTA NORMAL","ESTACIÓN CENTRAL","ESTACION CENTRAL",
    "CERRO NAVIA","LO PRADO","RENCA","MACUL","PEÑALOLÉN","PENALOLEN","LA CISTERNA","SAN MIGUEL","SAN JOAQUÍN","SAN JOAQUIN",
    "SAN RAMÓN","SAN RAMON","LA GRANJA","EL BOSQUE","LO ESPEJO","PEDRO AGUIRRE CERDA","CERRILLOS","LO BARNECHEA","QUILICURA",
    # V y VIII regiones y más
    "VALPARAISO","VALPARAÍSO","VIÑA DEL MAR","VINA DEL MAR","QUILPUE","QUILPUÉ","VILLA ALEMANA","QUILLOTA","LA CALERA","SAN ANTONIO",
    "CONCEPCION","CONCEPCIÓN","CORONEL","TALCAHUANO","CHIGUAYANTE","HUALPÉN","HUALPEN","PENCO","LOTA","TOMÉ","TOME",
    # Otras regiones
    "PUERTO AYSÉN","PUERTO AYSEN","PUERTO MONTT","TEMUCO","ANTOFAGASTA","COPIAPO","COPIAPÓ","RANCAGUA","OSORNO","LA SERENA",
    "CHILLAN","CHILLÁN","PUNTA ARENAS","CURICO","CURICÓ","ILLAPEL","COQUIMBO","LINARES","IQUIQUE","SAN BERNARDO","COLINA",
    "PUERTO VARAS","MELIPILLA","BUIN","PAINE","PEÑAFLOR","PENAFLOR","PADRE HURTADO","CAÑETE","CANETE"
]

MONTHS = {
    'enero':1,'febrero':2,'marzo':3,'abril':4,'mayo':5,'junio':6,
    'julio':7,'agosto':8,'septiembre':9,'setiembre':9,'octubre':10,'noviembre':11,'diciembre':12
}

# --------------- Debug helper ---------------
def write_debug(s: str):
    DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(s + "\n")

# --------------- Detección de tipo de documento ---------------
def detect_document_type(text_pages):
    """
    Detecta si es un Pagaré (PP) o Crédito de Consumo (CC) basándose en contenido.
    """
    combined_text = "\n".join(text_pages)
    combined_up = combined_text.upper()
    
    # Indicadores de Pagaré (PP)
    pp_indicators = [
        "PAGARÉ", "PAGARE", "PAGARÁ", "DOCUMENTO MERCANTIL",
        "VALOR RECIBIDO", "CONTRAVALOR RECIBIDO", "ME OBLIGO A PAGAR",
        "VENCIMIENTO"
    ]
    
    # Indicadores de Crédito de Consumo (CC)
    cc_indicators = [
        "CRÉDITO DE CONSUMO", "CREDITO DE CONSUMO", "LÍNEA DE CRÉDITO",
        "CONTRATO DE MUTUO", "CUOTAS", "TASA DE INTERÉS", "CRONOGRAMA",
        "TABLA DE DESARROLLO", "PLAN DE PAGOS"
    ]
    
    pp_score = sum(1 for indicator in pp_indicators if indicator in combined_up)
    cc_score = sum(1 for indicator in cc_indicators if indicator in combined_up)
    
    # Verificar por patrones específicos
    if re.search(r'\ben\s+\d+\s+cuotas\b', combined_text, re.IGNORECASE):
        cc_score += 3
    # Casos especiales: "PAGARE CREDITO CONSUMO" debe contar como CC
    if re.search(r'pagar[ée]?\s+cr[ée]dito\s+de?\s+consumo', combined_text, re.IGNORECASE):
        cc_score += 10
    
    if re.search(r'pagar[ée]|me\s+obligo\s+a\s+pagar', combined_text, re.IGNORECASE):
        pp_score += 3
    
    # Bloque de identidad CC: señales fuertes en cualquier página
    if (
        re.search(r'Nombre\s+y\s+Apellidos\s+del\s+deudor', combined_text, re.IGNORECASE)
        and re.search(r'C[eé]dula\s+de\s+Identidad', combined_text, re.IGNORECASE)
    ):
        cc_score += 4
    
    doc_type = "PP" if pp_score > cc_score else "CC"
    write_debug(f"[DETECT] PP_score={pp_score}, CC_score={cc_score} -> {doc_type}")
    
    return doc_type

# --------------- Utilidades comunes ---------------
def fmt_date(d, mname, y):
    m = MONTHS.get((mname or "").strip().lower())
    if not m: return ""
    try:
        return datetime(int(y), int(m), int(d)).strftime("%d-%m-%Y")
    except:
        return ""

def format_thousands_dot(n):
    if n is None: return ""
    return f"{n:,}".replace(",", ".")

def normalize_token(tok): 
    return tok.strip().strip(" .,:;").upper()

def fuzzy_comuna(s):
    su = normalize_token(s)
    su = fix_n_to_ene(su)
    if not su: return ""
    # Exact match
    for c in COMUNAS:
        if c in su or su in c:
            return c
    # Fuzzy match
    best = difflib.get_close_matches(su, COMUNAS, n=1, cutoff=0.72)
    return best[0] if best else su

def looks_like_physical_address(s):
    if not s: return False
    if re.search(r'\d{1,5}', s): return True
    return bool(re.search(r'\b(CALLE|AVENIDA|AVDA|AV|PJE|PAS|PASAJE|MARINA|CIRCUNVAL|BOULEVARD|BLVD|PROLONGACION|DEPARTAMENTO|DEPTO|DPTO|Nº|N°|LOCAL|EDIF|BLOCK|BLOQUE|BRISAS)\b', s, re.IGNORECASE))

# --------------- Fechas ---------------
def parse_spanish_date(text):
    t = text.replace('\n',' ')
    m = re.search(r'(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b)', t)
    if m:
        s = m.group(1).replace('-', '/')
        for fmt in ("%d/%m/%Y","%d/%m/%y"):
            try: return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
            except: pass
    # Variantes frecuentes en PP/CC: "a 29 de mayo de 2023", "el día 29 de mayo de 2023",
    # "Santiago, 29 de mayo de 2023" (ciudad opcional al comienzo)
    for pat in [
        r'\b(?:en\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+,?\s*)?a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})',
        r'\bel\s+d[ií]a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})',
        r'\b[A-Za-zÁÉÍÓÚÑáéíóúñ]+,\s*(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})',
        r'\b[A-Za-zÁÉÍÓÚÑáéíóúñ]+\s*,?\s*a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})',
        r'\b(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})\b',
    ]:
        m = re.search(pat, t, re.IGNORECASE)
        if m:
            return fmt_date(m.group(1), m.group(2), m.group(3))
    return ""

# --------------- Producto (hints) ---------------
def extract_producto_hint(text: str) -> str:
    """Busca indicaciones de producto en el texto (p.ej., 'Producto: TC')."""
    m = re.search(r'Producto\s*[:\-]\s*([A-Z]{1,4})', text, re.IGNORECASE)
    if m:
        return m.group(1).upper().strip()
    return ""

# --------------- Operación ---------------
def extract_operation_from_text(text):
    # Ser tolerantes con el caracter "N°" que suele degradarse como "N?" o "N*"
    for pat in [
        r'N[°º\*\?\W]?\s*(?:Operaci[oó]n|Operación)[:\s]*([0-9]{6,})',
        r'\b(?:Operaci[oó]n|Operación)\s*N[°º\*\?\W]?\s*([0-9]{6,})',
        r'N[°º\*\?\W]?\s*Producto[:\s]*([0-9]{6,})',
        r'\bProducto\s*N[°º\*\?\W]?\s*[:\s]*([0-9]{6,})'
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m: return m.group(1).strip()
    return ""

def extract_operation_allpages(text_pages):
    for t in text_pages:
        op = extract_operation_from_text(t)
        if op: return op
    return ""

def extract_operation_from_filename(filename: str) -> str:
    """Obtiene la operación desde el nombre del archivo si viene embebida.
    Ejemplos válidos: 860418.pdf -> 860418, 4191896500082450_PP.pdf -> 4191896500082450
    Regla: tomar el grupo de dígitos más largo de largo >= 6.
    """
    if not filename:
        return ""
    try:
        stem = Path(filename).stem
    except Exception:
        stem = filename
    # Buscar todos los grupos de dígitos
    nums = re.findall(r"(\d{6,})", stem)
    if not nums:
        return ""
    # Devolver el más largo; si empatan, el primero
    nums.sort(key=lambda s: (-len(s), stem.find(s)))
    return nums[0]

# --------------- Fechas de Vencimiento ---------------
def extract_fecha_vencimiento_primera_cuota(text):
    """Extrae fecha de vencimiento de la primera cuota"""
    patterns = [
        # Patrón específico encontrado: "primera cuota el día 29 de junio de 2023"
        r'primera\s+cuota\s+el\s+d[ií]a\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})',
        r'venciendo\s+la\s+primera\s+cuota\s+el\s+d[ií]a\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})',
        # Patrones adicionales
        r'(?:primera?\s+cuota|1[aª]?\s+cuota|cuota\s+inicial)[:\s]*(?:vence|vencimiento|fecha)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'(?:vencimiento|fecha)[:\s]*(?:primera?\s+cuota|1[aª]?\s+cuota)[:\s]*([0-3]?\d[\/\-][0-1]?\d{2}[\/\-](?:20)?\d{2})',
        r'1[aª]?\s+cuota[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'(?:del|desde)\s+([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})\s+(?:en\s+adelante|mensual)',
        r'primera?\s+(?:cuota|pago)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})'
    ]
    
    for i, pat in enumerate(patterns):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if i < 2:  # Patrones con formato "día X de mes de año"
                day = m.group(1)
                month = m.group(2).lower()
                year = m.group(3)
                fecha_norm = format_spanish_date(day, month, year)
                if fecha_norm:
                    return fecha_norm
            else:  # Patrones con formato dd/mm/yyyy
                fecha_str = m.group(1)
                fecha_norm = normalize_date_format(fecha_str)
                if fecha_norm:
                    return fecha_norm
    return ""

def extract_fecha_vencimiento_ultima_cuota(text):
    """Extrae fecha de vencimiento de la última cuota"""
    patterns = [
        # Patrón específico encontrado: "la última el 29 de mayo de 2028"
        r'(?:y\s+)?la\s+última\s+el\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})',
        r'última\s+cuota\s+el\s+d[ií]a\s+(\d{1,2})\s+de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})',
        # Patrones adicionales
        r'(?:última?\s+cuota|final\s+cuota|cuota\s+final)[:\s]*(?:vence|vencimiento|fecha)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'(?:vencimiento|fecha)[:\s]*(?:última?\s+cuota|final\s+cuota)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'(?:hasta|hasta\s+el)\s+([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'(?:término|fin|finaliza)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})',
        r'última?\s+(?:cuota|pago)[:\s]*([0-3]?\d[\/\-][0-1]?\d[\/\-](?:20)?\d{2})'
    ]
    
    for i, pat in enumerate(patterns):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if i < 2:  # Patrones con formato "día X de mes de año"
                day = m.group(1)
                month = m.group(2).lower()
                year = m.group(3)
                fecha_norm = format_spanish_date(day, month, year)
                if fecha_norm:
                    return fecha_norm
            else:  # Patrones con formato dd/mm/yyyy
                fecha_str = m.group(1)
                fecha_norm = normalize_date_format(fecha_str)
                if fecha_norm:
                    return fecha_norm
    return ""

def normalize_date_format(fecha_str):
    """Normaliza formato de fecha a DD-MM-YYYY"""
    if not fecha_str:
        return ""
    
    # Limpiar y normalizar separadores
    fecha_clean = re.sub(r'[\/\-\.]', '/', fecha_str.strip())
    
    # Intentar varios formatos
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            dt_obj = datetime.strptime(fecha_clean, fmt)
            return dt_obj.strftime("%d-%m-%Y")
        except:
            continue
    
    return ""

def format_spanish_date(day, month_name, year):
    """Convierte fecha en español (día, nombre_mes, año) a formato DD-MM-YYYY"""
    month_map = {
        'enero': '01', 'febrero': '02', 'marzo': '03', 'abril': '04',
        'mayo': '05', 'junio': '06', 'julio': '07', 'agosto': '08',
        'septiembre': '09', 'octubre': '10', 'noviembre': '11', 'diciembre': '12'
    }
    
    month_num = month_map.get(month_name.lower())
    if not month_num:
        return ""
    
    try:
        day_padded = day.zfill(2)
        return f"{day_padded}-{month_num}-{year}"
    except:
        return ""

# --------------- Corrección N por Ñ ---------------
def fix_n_to_ene(text):
    """
    Corrige N por Ñ en palabras comunes donde corresponda
    """
    if not text:
        return text
    
    # Diccionario de correcciones comunes N -> Ñ (solo strings)
    corrections = {
        # Apellidos comunes
        r'\bPENA\b': 'PEÑA',
        r'\bMUNOZ\b': 'MUÑOZ', 
        r'\bNUNEZ\b': 'NÚÑEZ', r'\bNUNEZ\b': 'NUÑEZ',  # aceptar ambas acentuaciones comunes
        r'\bIBANEZ\b': 'IBAÑEZ',
        r'\bYANEZ\b': 'YÁÑEZ',
        r'\bACUNA\b': 'ACUÑA',
        r'\bARGANARAZ\b': 'ARGAÑARAZ',
        r'\bZUNIGA\b': 'ZÚÑIGA',
        r'\bNIGON\b': 'ÑIGÓN',
        r'\bVICUNA\b': 'VICUÑA',
        r'\bNIQUEN\b': 'ÑIQUÉN',
        r'\bARANA\b': 'ARAÑA',
        r'\bARANO\b': 'ARAÑO',
        r'\bMONTANA\b': 'MONTAÑA',
        r'\bCASTANEDA\b': 'CASTAÑEDA',
        r'\bESPINOSA\b': 'ESPINOZA',
        
        # Nombres comunes
    r'\bNINO\b': 'NIÑO', r'\bNINO\s*\(NOMBRE\)\b': 'NIÑO (NOMBRE)',
        r'\bNINA\b': 'NIÑA',
    r'\bINIGO\b': 'IÑIGO',
    r'\bINAKI\b': 'IÑAKI',
    r'\bMANE\b': 'MAÑE', r'\bMANUE\b': 'MAÑE',
        
        # Lugares comunes
    r'\bESPANA\b': 'ESPAÑA',
        r'\bVINA\s+DEL\s+MAR\b': 'VIÑA DEL MAR',
        r'\bPENALOLEN\b': 'PEÑALOLÉN',
        r'\bPENAFLOR\b': 'PEÑAFLOR',
    r'\bPENALBA\b': 'PEÑALBA',
    r'\bNUNOA\b': 'ÑUÑOA', r'\bNUNOA\s*\(COMUNA\)\b': 'ÑUÑOA (COMUNA)',
    r'\bNUBLE\b': 'ÑUBLE',
    r'\bNANCUL\b': 'ÑANCUL',
    r'\bNACULEO\b': 'ÑACULEO',
    r'\bNICULIPE\b': 'ÑACULIPE',
    r'\bSAN\s+NICASIO\b': 'SAN IGNACIO',
        
        # Términos legales/comerciales
        r'\bSENOR\b': 'SEÑOR',
        r'\bSENORA\b': 'SEÑORA',
        r'\bDUENO\b': 'DUEÑO',
        r'\bANO\b': 'AÑO',
        r'\bANOS\b': 'AÑOS'
    }
    
    result = text
    
    for pattern, replacement in corrections.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    return result

# --------------- RUT ---------------
def find_all_ruts(text):
    matches = []
    # Etiquetados (Cédula / RUT) - Priorizando patrones específicos de PP
    for pat, base in [
        # Patrones específicos para PP con "C.L/RUT N*:" (prioridad máxima)
        (r'C\.L[\/\\]RUT\s+N\*?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 20),
        (r'C\.L\s*\/\s*RUT\s+N\*?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 19),
        # Patrones específicos para PP con "C.I/RUT N°:"
        (r'C\.I[\/\\]RUT\s+N[°º\*]?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 18),
        (r'C\.I\s*\/\s*RUT\s+N[°º\*]?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 17),
        (r'C\.I\s*\/\s*RUT\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 16),
        # Variaciones con espacios y separadores
        (r'C\s*\.\s*I\s*[\/\\]\s*RUT\s+N[°º\*]?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 15),
        # Otros patrones de cédula
        (r'C[eé]dula\s+de\s+Identidad\s*N[°\*]?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 12),
        (r'(?:C\.I\.\/RUT|C\.L\/RUT|RUT)[^:\d]{0,10}[:\s]*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 10)
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = m.start(1)
            matches.append((start, re.sub(r'[^\d]', '', m.group(1)), m.group(2).upper(), text[max(0,start-80):start+120], base))
    # Genéricos
    for m in re.finditer(r'([0-9]{1,3}(?:\.[0-9]{3}){1,2})\s*[-\s–—]*([0-9Kk])', text):
        start = m.start(1)
        ctx = text[max(0,start-80):start+120]
        # Evitar capturar números cercanos a 'Operación' o 'Producto' como RUT
        if re.search(r'Operaci[oó]n|Producto', ctx, re.IGNORECASE):
            continue
        matches.append((start, re.sub(r'[^\d]', '', m.group(1)), m.group(2).upper(), ctx, 3))
    for m in re.finditer(r'\b(\d{7,8})\s*[-\s–—]*([0-9Kk])', text):
        start = m.start(1)
        ctx = text[max(0,start-80):start+120]
        if re.search(r'Operaci[oó]n|Producto', ctx, re.IGNORECASE):
            continue
        matches.append((start, m.group(1), m.group(2).upper(), ctx, 2))
    return matches

def choose_rut_for_doc(text, ruts, doc_type="CC"):
    """
    Elige el RUT más apropiado según el tipo de documento.
    Para PP: prioriza RUTs con patrón "C.I/RUT N°:" y cercanos a "Suscriptor" o "Deudor"
    Para CC: prioriza RUTs en bloques de identidad
    Excluye RUTs del banco (97.023.000-9 Itaú)
    """
    if not ruts: return "", ""
    
    sus = re.search(r'(Nombre\s+y\s+Apellidos\s+del\s+deudor|Suscriptor(?:\s+o\s+Deudor)?|Deudor|Cliente\/Deudor)', text, re.IGNORECASE)
    sus_pos = sus.start() if sus else None
    banco_pat = re.compile(r'\bBanco\b|\bIta[uú]\b|Representado por', re.IGNORECASE)
    
    best = None; best_score = -1
    for (pos, rut, dv, ctx, base) in ruts:
        # Excluir explícitamente RUT del banco Itaú
        if rut == "97023000" and dv == "9":
            continue
            
        score = base
        
        # Penalizar fuertemente RUTs que aparezcan en contexto del banco
        if banco_pat.search(ctx):
            score -= 50
        
        # Bonificaciones según tipo de documento
        if doc_type == "PP":
            # Máxima prioridad para patrones específicos de PP "C.I/RUT N°:" o "C.L/RUT N*"
            if base >= 15:  # Patrones específicos C.I/RUT N°:
                score += 25
            # Buscar patrón específico C.L/RUT que aparece en PP
            if re.search(r'C\.L[\/\\]RUT\s+N\*?\s*:', ctx, re.IGNORECASE):
                score += 30
            # Para pagarés, priorizar RUTs cerca de "Suscriptor"
            if sus_pos is not None:
                score += max(0, 300 - abs(pos - sus_pos)) // 10
            # Buscar contexto específico de PP
            if re.search(r'C\.I[\/\\]RUT\s+N[°º]', ctx, re.IGNORECASE):
                score += 20
        else:
            # Para CC, priorizar bloques de identidad
            if "Cédula de Identidad" in ctx:
                score += 10
        
        # Bonificación por formato estándar de RUT
        if 7 <= len(rut) <= 8: score += 2
        
        if score > best_score:
            best_score = score; best = (rut, dv)
    
    return best if best else ("","")

# --------------- Nombre ---------------
def extract_nombre_generic(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        m = re.match(r'^(?:Suscriptor(?:\s+o\s+Deudor)?|Deudor|Cliente\/Deudor)[:\.\s-]*(.+)$', ln, re.IGNORECASE)
        if m:
            name = (m.group(1) or "").strip()
            return (name or (lines[i+1].strip() if i+1 < len(lines) else "")).upper()
    return ""

# --------------- Dirección/Comuna (lógica PP mejorada) ---------------
def extract_domicilio_and_comuna_pp(text):
    """
    Lógica especializada para Pagarés con puntuación mejorada.
    """
    lines_raw = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    lines = [re.sub(r'[\u2000-\u206F\u2E00-\u2E7F]+', ' ', ln) for ln in lines_raw]

    # Recolectar candidatos 'Domicilio' evitando 'y competencia'
    candidates = []
    for i, ln in enumerate(lines):
        if not re.search(r'\bDomicilio\b', ln, re.IGNORECASE):
            continue
        if re.search(r'\bDomicilio\b\s*y\s+competencia', ln, re.IGNORECASE):
            continue  # evitar cláusula legal
        
        m = re.search(r'\bDomicilio\b\s*[:.\-]*\s*(.*)$', ln, re.IGNORECASE)
        tail = (m.group(1) if m else "").strip()
        ext = tail
        
        if (len(ext) < 6 or ',' not in ext) and i+1 < len(lines) and looks_like_physical_address(lines[i+1]):
            ext = (ext + " " + lines[i+1].strip()).strip()
        
        score = 0
        if ',' in ext: score += 3
        if re.search(r'\d{2,5}', ext): score += 3
        if looks_like_physical_address(ext): score += 2
        if re.search(r'competencia|efectos\s+legales', ext, re.IGNORECASE): score -= 5
        
        candidates.append((score, i, ext))
        write_debug(f"[DOM_PP] candidate score={score} line={i} text='{ext}'")

    if candidates:
        candidates.sort(key=lambda x: (-x[0], x[1]))
        score, idx, chosen = candidates[0]
        write_debug(f"[DOM_PP] chosen score={score} line={idx} text='{chosen}'")
        
        if ',' in chosen:
            addr, tail = chosen.rsplit(',', 1)
            comuna = clean_comuna_tail(tail)
            return addr.strip().upper(), comuna
    
    return "", ""

def clean_comuna_tail(tail):
    """
    Limpia y normaliza el final de una dirección que debería contener la comuna.
    """
    t = normalize_token(tail)
    # Extraer solo letras y espacios
    m = re.match(r'([A-ZÁÉÍÓÚÑ\s]+)', t)
    cand = re.sub(r'\s+', ' ', (m.group(1).strip() if m else t))
    
    # Fuzzy matching con comunas válidas
    best = difflib.get_close_matches(cand, COMUNAS, n=1, cutoff=0.7)
    if best: return best[0]
    
    # Buscar por segmentos de palabras
    words = cand.split()
    for n in [3,2,1]:
        for k in range(len(words)-n+1):
            seg = " ".join(words[k:k+n])
            best = difflib.get_close_matches(seg, COMUNAS, n=1, cutoff=0.7)
            if best: return best[0]
    
    return cand

# --------------- Domicilio CC (bloque de identidad) ---------------
def extract_cc_identity_block(text_pages):
    """
    Extrae bloque de identidad específico para CC.
    """
    ident = {"name":"","rut":"","dv":"","address":"","comuna":"","ok":False}
    for page_idx, text in enumerate(text_pages, start=1):
        # Nombre
        mname = re.search(r'^\s*Nombre\s+y\s+Apellidos\s+del\s+deudor\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mname and not ident["name"]:
            ident["name"] = mname.group(1).strip().upper()
        
        # Cédula
        mrut = re.search(r'^\s*C[eé]dula\s+de\s+Identidad\s*N[°\*]?\s*:?\s*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])\s*$', text, re.IGNORECASE | re.MULTILINE)
        if mrut and not ident["rut"]:
            ident["rut"] = re.sub(r'[^\d]', '', mrut.group(1))
            ident["dv"] = mrut.group(2).upper()
        
        # Domicilio
        mdom = re.search(r'^\s*Domicilio\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mdom and not ident["address"]:
            cand = mdom.group(1).strip()
            if not is_bank_header_line(cand):
                ident["address"] = cand.upper()
        # Dirección Informativa (muchos CC)
        if not ident["address"]:
            minfo = re.search(r'^\s*Direcci[oó]n\s+Informativa\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
            if minfo:
                cand = minfo.group(1).strip()
                if not is_bank_header_line(cand):
                    if "," in cand:
                        left, right = cand.rsplit(",", 1)
                        ident["address"] = left.strip().upper()
                        if not ident["comuna"]:
                            ident["comuna"] = fuzzy_comuna(right)
                    else:
                        ident["address"] = cand.upper()
        
        # Comuna
        mcom = re.search(r'^\s*Comuna\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mcom and not ident["comuna"]:
            ident["comuna"] = fuzzy_comuna(mcom.group(1))
    
    # Marcar como válido si tiene datos útiles
    if ident["address"] or ident["comuna"]:
        ident["ok"] = True
    
    write_debug(f"[IDENT_CC] {ident}")
    return ident

def is_bank_header_line(s: str) -> bool:
    if not s: return False
    su = s.upper()
    return any(k in su for k in [
        "EN SU OFICINA", "PRESIDENTE RIESCO", "BANCO ITA", "COMUNA DE LAS"
    ])

# --------------- Montos ---------------
def extract_amount(text):
    candidates = []
    for m in re.finditer(r'(?:la\s+suma\s+de|cantidad\s+de)?\s*\$\s*([0-9\.\,]+)', text, re.IGNORECASE):
        raw = m.group(1); clean = re.sub(r'[^\d]', '', raw)
        num = int(clean) if clean.isdigit() else None
        ctx = text[max(0, m.start()-80): m.end()+80].lower()
        score = 10 if ('la suma de' in ctx or 'cantidad de' in ctx) else 0
        candidates.append((score, num))
    if candidates:
        candidates.sort(key=lambda x: (-x[0]))
        num = candidates[0][1]
        return format_thousands_dot(num) if num is not None else "", num
    return "", None

# --------------- Representantes ---------------
def is_name_candidate(s):
    if not s: return False
    s_clean = re.sub(r'[^A-Za-zÁÉÍÓÚÑñ\s]', '', s).strip()
    if len(s_clean) < 4: return False
    if re.search(r'C[eé]DULA|C\.L|C\.I|ID|CI\.|N[°\*]', s, re.IGNORECASE): return False
    return len(s_clean.split()) >= 2

def extract_representantes_allpages(text_pages):
    rep1 = rep2 = ""
    for text in text_pages:
        m1 = re.search(r'Representante\s*1[:\s\.-]*(.+)', text, re.IGNORECASE)
        if m1:
            cand = m1.group(1).splitlines()[0].strip()
            if is_name_candidate(cand): rep1 = cand.upper()
        m2 = re.search(r'Representante\s*2[:\s\.-]*(.+)', text, re.IGNORECASE)
        if m2:
            cand = m2.group(1).splitlines()[0].strip()
            if is_name_candidate(cand): rep2 = cand.upper()
    return rep1, rep2

# --------------- OCR helpers ---------------
def ocr_image_to_text(img_path):
    if not TESSERACT_AVAILABLE:
        write_debug(f"⚠️ Tesseract no disponible para {img_path}")
        return ""
    try: 
        img = Image.open(img_path)
        return pytesseract.image_to_string(img, lang='spa')
    except Exception as e:
        write_debug(f"ERROR OCR {img_path}: {e}")
        return ""

def convert_pdf_to_images(pdf_path, out_folder, poppler_path, dpi=200):
    out_folder.mkdir(parents=True, exist_ok=True)
    try:
        images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=str(poppler_path))
        outs = []
        for i, img in enumerate(images, start=1):
            out = out_folder / f"page{i}.png"
            img.save(out, "PNG"); outs.append(out)
        return outs
    except Exception as e:
        write_debug(f"ERROR PDF->Images {pdf_path}: {e}")
        return []

def find_existing_pdfs():
    if not PDF_INPUT_DIR.exists(): return []
    return sorted(PDF_INPUT_DIR.glob("*.pdf"))

# --------------- Procesamiento unificado ---------------
def process_document_unified(text_pages, doc_type, use_geocode=False, source_name: str | None = None):
    """
    Procesa un documento usando la lógica apropiada según su tipo.
    """
    write_debug(f"[PROCESS] Procesando como {doc_type}")
    
    if doc_type == "PP":
        return process_pagare(text_pages, use_geocode, source_name=source_name)
    else:
        return process_credito_consumo(text_pages, use_geocode, source_name=source_name)

def process_pagare(text_pages, use_geocode=False, source_name: str | None = None):
    """
    Procesa un Pagaré (PP) usando lógica especializada.
    """
    rows = []
    producto_hint = ""
    for text in text_pages:
        # Capturar hints de producto (p.ej., 'Producto: TC')
        if not producto_hint:
            producto_hint = extract_producto_hint(text)
        op = extract_operation_from_text(text)
        ruts = find_all_ruts(text)
        rut, dv = choose_rut_for_doc(text, ruts, "PP") if ruts else ("","")
        nombre = extract_nombre_generic(text)
        direccion, comuna = extract_domicilio_and_comuna_pp(text)
        fecha_sus = parse_spanish_date(text)
        monto_fmt, _ = extract_amount(text)
        
        # Extraer fechas de vencimiento
        fecha_venc_1 = extract_fecha_vencimiento_primera_cuota(text)
        fecha_venc_ultima = extract_fecha_vencimiento_ultima_cuota(text)
        
        rows.append({
            "text": text,
            "OPERACIÓN": op, "RUT": rut, "DV": dv, "NOMBRE": nombre,
            "DIRECCION": direccion, "COMUNA": comuna,
            "FECHA_SUSCRIPCION": fecha_sus, "MONTO_CREDITO": monto_fmt,
            "FECHA_VENC_1": fecha_venc_1, "FECHA_VENC_ULTIMA": fecha_venc_ultima
        })
    
    operation = extract_operation_allpages(text_pages)
    op_from_file = extract_operation_from_filename(source_name or "")
    def score_row_basic(r):
        return (50 if r.get("OPERACIÓN") else 0) + (30 if r.get("RUT") else 0) + (20 if r.get("NOMBRE") else 0) + (10 if r.get("MONTO_CREDITO") else 0)
    best = max(rows, key=score_row_basic) if rows else {}
    
    # Representantes
    rep1, rep2 = extract_representantes_allpages(text_pages)
    
    # Aplicar correcciones
    direccion = clean_and_fix_address(best.get("DIRECCION", ""))
    comuna = fix_comuna_ocr(best.get("COMUNA", ""))
    
    # Aplicar corrección N->Ñ en nombre y dirección
    nombre_corregido = fix_n_to_ene(best.get("NOMBRE", ""))
    direccion_corregida = fix_n_to_ene(direccion)
    comuna_corregida = fix_n_to_ene(comuna)
    
    # Extraer fecha de suscripción y vencimientos de todas las páginas
    fecha_sus_final = ""
    fecha_venc_1_final = ""
    fecha_venc_ultima_final = ""
    for row in rows:
        if not fecha_sus_final and row.get("FECHA_SUSCRIPCION"):
            fecha_sus_final = row["FECHA_SUSCRIPCION"]
        if not fecha_venc_1_final and row.get("FECHA_VENC_1"):
            fecha_venc_1_final = row["FECHA_VENC_1"]
        if not fecha_venc_ultima_final and row.get("FECHA_VENC_ULTIMA"):
            fecha_venc_ultima_final = row["FECHA_VENC_ULTIMA"]
    
    # Normalizar PRODUCTO: para la base seguimos usando 'PP' aunque el encabezado indique 'TC'
    producto_out = "PP"
    if producto_hint and producto_hint != "PP":
        write_debug(f"[PRODUCTO_HINT_PP] Detectado '{producto_hint}', normalizando a 'PP' para base")

    final_row = {
        "OPERACION_1": operation or best.get("OPERACIÓN","") or op_from_file,
        "RUT": best.get("RUT",""), "DV": best.get("DV",""), "NOMBRE": nombre_corregido,
        "DIRECCION": direccion_corregida, "COMUNA": comuna_corregida,
    "FECHA_SUSCRIPCION_1": fecha_sus_final or best.get("FECHA_SUSCRIPCION",""),
        "MONTO_CREDITO_1": best.get("MONTO_CREDITO",""),
        "CUOTAS_1": "", "TASA_1": "", "MONTO_CUOTA_1": "", "MONTO_ULTIMA_CUOTA_1": "",
        "FECHA_VENCIMIENTO_1_CUOTA_1": fecha_venc_1_final or best.get("FECHA_SUSCRIPCION",""),
        "FECHA_VENCIMIENTO_ULTIMA_CUOTA_1": fecha_venc_ultima_final or best.get("FECHA_SUSCRIPCION",""),
        "CUOTA_MOROSA_1": "", "FECHA_CUOTA_MOROSA_1": "",
        "CAPITAL_1": best.get("MONTO_CREDITO",""), 
        "EXHORTO": "TEMUCO", "SUCURSAL": "SANTIAGO", "PRODUCTO": producto_out,
        "NOMBRE_APODERADO": fix_n_to_ene(rep1), "NOMBRE_APODERADO_2": fix_n_to_ene(rep2)
    }
    
    write_debug("---- COMBINED ROW PP ----")
    for k,v in final_row.items(): write_debug(f"{k}: {v}")
    write_debug("---- END COMBINED ROW PP ----\n")
    
    return final_row

def process_credito_consumo(text_pages, use_geocode=False, source_name: str | None = None):
    """
    Procesa un Crédito de Consumo (CC) usando lógica especializada.
    """
    # Usar lógica del bloque de identidad
    ident = extract_cc_identity_block(text_pages)
    
    # Procesar páginas individualmente
    rows = []
    producto_hint = ""
    for text in text_pages:
        if not producto_hint:
            producto_hint = extract_producto_hint(text)
        op = extract_operation_from_text(text)
        ruts = find_all_ruts(text)
        rut_gen, dv_gen = choose_rut_for_doc(text, ruts, "CC") if ruts else ("","")
        nombre_g = extract_nombre_generic(text)
        fecha_sus = parse_spanish_date(text)
        monto_fmt, _ = extract_amount(text)
        
        # Extraer fechas de vencimiento para CC
        fecha_venc_1 = extract_fecha_vencimiento_primera_cuota(text)
        fecha_venc_ultima = extract_fecha_vencimiento_ultima_cuota(text)
        
        rows.append({
            "text": text,
            "OPERACIÓN": op, "RUT": rut_gen, "DV": dv_gen,
            "NOMBRE_G": nombre_g,
            "FECHA_SUSCRIPCION": fecha_sus, "MONTO_CREDITO": monto_fmt,
            "FECHA_VENC_1": fecha_venc_1, "FECHA_VENC_ULTIMA": fecha_venc_ultima
        })
    
    # Escoger mejor página
    def score_row_basic(r):
        return (50 if r.get("OPERACIÓN") else 0) + (30 if r.get("RUT") else 0) + (20 if r.get("NOMBRE_G") else 0) + (10 if r.get("MONTO_CREDITO") else 0)
    best = max(rows, key=score_row_basic) if rows else {}
    operation = extract_operation_allpages([r["text"] for r in rows]) or best.get("OPERACIÓN","")
    op_from_file = extract_operation_from_filename(source_name or "")
    
    # Priorizar datos del bloque de identidad
    nombre = ident["name"] or best.get("NOMBRE_G","") or ""
    rut = ident["rut"] or best.get("RUT","") or ""
    dv = ident["dv"] or best.get("DV","") or ""
    direccion = clean_and_fix_address(ident["address"] or "")
    comuna = fix_comuna_ocr(ident["comuna"] or "")
    
    # Aplicar corrección N->Ñ
    nombre_corregido = fix_n_to_ene(nombre)
    direccion_corregida = fix_n_to_ene(direccion)
    comuna_corregida = fix_n_to_ene(comuna)
    
    # Extraer fechas de vencimiento de todas las páginas
    fecha_venc_1_final = ""
    fecha_venc_ultima_final = ""
    for row in rows:
        if not fecha_venc_1_final and row.get("FECHA_VENC_1"):
            fecha_venc_1_final = row["FECHA_VENC_1"]
        if not fecha_venc_ultima_final and row.get("FECHA_VENC_ULTIMA"):
            fecha_venc_ultima_final = row["FECHA_VENC_ULTIMA"]
    
    # Representantes
    rep1, rep2 = extract_representantes_allpages(text_pages)
    
    # En CC mantenemos "CC" como producto para la base, ignorando siglas como TC
    final_row = {
        "OPERACION_1": operation or op_from_file,
        "RUT": rut, "DV": dv, "NOMBRE": nombre_corregido,
        "DIRECCION": direccion_corregida, "COMUNA": comuna_corregida,
        "FECHA_SUSCRIPCION_1": best.get("FECHA_SUSCRIPCION",""),
        "MONTO_CREDITO_1": best.get("MONTO_CREDITO",""),
        "CUOTAS_1": "", "TASA_1": "", "MONTO_CUOTA_1": "", "MONTO_ULTIMA_CUOTA_1": "",
        "FECHA_VENCIMIENTO_1_CUOTA_1": fecha_venc_1_final,
        "FECHA_VENCIMIENTO_ULTIMA_CUOTA_1": fecha_venc_ultima_final,
        "CUOTA_MOROSA_1": "", "FECHA_CUOTA_MOROSA_1": "",
        "CAPITAL_1": best.get("MONTO_CREDITO",""), 
        "EXHORTO": "TEMUCO", "SUCURSAL": "SANTIAGO", "PRODUCTO": "CC",
        "NOMBRE_APODERADO": fix_n_to_ene(rep1), "NOMBRE_APODERADO_2": fix_n_to_ene(rep2)
    }
    
    write_debug("---- COMBINED ROW CC ----")
    for k,v in final_row.items(): write_debug(f"{k}: {v}")
    write_debug("---- END COMBINED ROW CC ----\n")
    
    return final_row

# --------------- Main ---------------
def main():
    parser = argparse.ArgumentParser(description="Procesar PDFs Itau (Unificado PP/CC) -> Excel")
    parser.add_argument("--geocode", action="store_true", help="Intentar geocodificar (Nominatim)")
    args = parser.parse_args()
    use_geocode = args.geocode

    print("🚀 Inicio: proceso Itau UNIFICADO (PP/CC)")
    DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_FILE.unlink(missing_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not TESSERACT_AVAILABLE:
        print("❌ TESSERACT NO DISPONIBLE - No se puede extraer texto de PDFs")
        return

    pdfs = find_existing_pdfs()
    if not pdfs:
        print("❌ No se encontraron PDFs en:", PDF_INPUT_DIR)
        return

    print(f"📁 Encontrados {len(pdfs)} PDFs para procesar")
    
    all_rows = []
    for pdf in pdfs:
        print(f"🔄 Procesando PDF: {pdf.name}")
        ri_folder = TEMP_RI_ROOT / pdf.stem
        text_pages = []
        try:
            images = convert_pdf_to_images(pdf, ri_folder, POPPLER_BIN, dpi=200)
            if not images:
                print(f"  ❌ ERROR: no se generaron imágenes para {pdf.name}")
                continue
            
            print(f"  📄 Generadas {len(images)} páginas")
            for img in images:
                print(f"    🔍 OCR imagen: {img.name}")
                txt = ocr_image_to_text(img)
                write_debug(f"--- PAGE OCR: {img.name} ---")
                write_debug(txt[:8000])
                text_pages.append(txt)
            
            # Detectar tipo de documento
            doc_type = detect_document_type(text_pages)
            print(f"  📋 Tipo detectado: {doc_type}")
            
            # Procesar según tipo
            row = process_document_unified(text_pages, doc_type, use_geocode=use_geocode, source_name=pdf.name)
            all_rows.append(row)
            print(f"  ✅ Extraído: RUT {row['RUT']}-{row['DV']}, {row['NOMBRE']} ({doc_type})")
            
        except Exception as e:
            print(f"  ❌ ERROR procesando {pdf.name}: {str(e)}")
            write_debug(f"ERROR procesando {pdf.name}: {e}")
        finally:
            try:
                if ri_folder.exists(): shutil.rmtree(ri_folder)
            except Exception as e:
                write_debug(f"WARNING cleanup {ri_folder}: {e}")

    if all_rows:
        df_new = pd.DataFrame(all_rows, columns=UNIFIED_COLUMNS)
        
        # Aplicar correcciones de referencia si están disponibles
        if GEO_UTILS_AVAILABLE:
            print("📋 Aplicando correcciones de referencia...")
            df_corrected = apply_reference_corrections(df_new)
            corrected_count = sum(1 for i in range(len(df_new)) 
                                if df_new.iloc[i].to_dict() != df_corrected.iloc[i].to_dict())
            if corrected_count > 0:
                print(f"✅ Aplicadas {corrected_count} correcciones de referencia")
                df_new = df_corrected
        
        # Verificador rápido de campos críticos para depurar mínimos errores de extracción
        missing_counts = {k: 0 for k in ["OPERACION_1","RUT","DV","NOMBRE","COMUNA"]}
        for i, (_, row) in enumerate(df_new.iterrows(), 1):
            for k in missing_counts:
                if not str(row.get(k, "")).strip():
                    missing_counts[k] += 1
        write_debug("\n==== VERIFICADOR DE CAMPOS CRÍTICOS ====")
        for k, v in missing_counts.items():
            write_debug(f"Faltantes {k}: {v}")
        write_debug("=======================================\n")

        df_new.to_excel(OUT_XLSX, index=False)
        print(f"✅ Guardado final en: {OUT_XLSX}")
        print(f"📋 Debug info en: {DEBUG_FILE}")
        print(f"📊 Filas extraídas: {len(all_rows)}")
        
        # Mostrar resumen
        print("\n📄 RESUMEN DE DATOS EXTRAÍDOS:")
        for i, (_, row) in enumerate(df_new.iterrows(), 1):
            print(f"  Fila {i}: {row['NOMBRE']} (RUT: {row['RUT']}-{row['DV']}) - {row['COMUNA']} [{row['PRODUCTO']}]")
    else:
        print("❌ No se extrajeron filas. Revisa", DEBUG_FILE)

if __name__ == "__main__":
    main()

# --------------- Public API for Web use ---------------
def process_pdf_files(pdf_paths: list[str], geocode: bool = False, output_dir: str | None = None, fast: bool = False, dpi: int | None = None) -> tuple[str, str]:
    """
    Procesa una lista de rutas de PDFs y genera un Excel con el resultado.
    Devuelve (excel_path, debug_file_path).

    Nota: Usa la misma lógica unificada PP/CC. Crea un archivo Excel con timestamp
    en output_dir (por defecto outputs/Itau/web) y un debug asociado.
    """
    out_base = Path(output_dir) if output_dir else (OUT_DIR / "web")
    out_base.mkdir(parents=True, exist_ok=True)

    # Crear nombres con timestamp para no pisar ejecuciones concurrentes
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out_base / f"Itau_results_UNIFIED_{ts}.xlsx"
    debug_path = out_base / f"Itau_debug_unified_{ts}.txt"
    ri_root = TEMP_RI_ROOT / f"web_{ts}"

    # Redirigir temporalmente el debug global a este archivo
    global DEBUG_FILE
    prev_debug = DEBUG_FILE
    DEBUG_FILE = debug_path
    try:
        DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
        DEBUG_FILE.unlink(missing_ok=True)

        if not TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract no disponible en el servidor")

        all_rows = []
        # Prioridad: si viene dpi explícito, usarlo; si no, usar fast/standard
        dpi_val = dpi if dpi is not None else (150 if fast else 200)
        for pdf in pdf_paths:
            pdf_path = Path(pdf)
            if not pdf_path.exists():
                write_debug(f"WARN: PDF no existe -> {pdf}")
                continue
            # Usar una carpeta temporal por sesión web para evitar choques con el proceso local
            ri_folder = ri_root / pdf_path.stem
            text_pages = []
            try:
                images = convert_pdf_to_images(pdf_path, ri_folder, POPPLER_BIN, dpi=dpi_val)
                for img in images:
                    txt = ocr_image_to_text(img)
                    write_debug(f"--- PAGE OCR: {img.name} ---")
                    write_debug(txt[:8000])
                    text_pages.append(txt)
                doc_type = detect_document_type(text_pages)
                row = process_document_unified(text_pages, doc_type, use_geocode=geocode, source_name=pdf_path.name)
                all_rows.append(row)
            except Exception as e:
                write_debug(f"ERROR procesando {pdf_path.name}: {e}")
            finally:
                try:
                    if ri_folder.exists(): shutil.rmtree(ri_folder)
                except Exception as e:
                    write_debug(f"WARNING cleanup {ri_folder}: {e}")

        if not all_rows:
            # Aún así, crear un Excel vacío con columnas para feedback claro
            pd.DataFrame(columns=UNIFIED_COLUMNS).to_excel(xlsx_path, index=False)
            return str(xlsx_path), str(debug_path)

        df_new = pd.DataFrame(all_rows, columns=UNIFIED_COLUMNS)
        if GEO_UTILS_AVAILABLE and geocode:
            df_new = apply_reference_corrections(df_new)

        # Verificador rápido de campos críticos
        missing_counts = {k: 0 for k in ["OPERACION_1","RUT","DV","NOMBRE","COMUNA"]}
        for _, row in df_new.iterrows():
            for k in missing_counts:
                if not str(row.get(k, "")).strip():
                    missing_counts[k] += 1
        write_debug("\n==== VERIFICADOR DE CAMPOS CRÍTICOS (web) ====")
        for k, v in missing_counts.items():
            write_debug(f"Faltantes {k}: {v}")
        write_debug("==============================================\n")

        df_new.to_excel(xlsx_path, index=False)
        return str(xlsx_path), str(debug_path)
    finally:
        DEBUG_FILE = prev_debug