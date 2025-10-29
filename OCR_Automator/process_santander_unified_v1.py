#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_santander_unified_v1.py

Sistema unificado para cliente Santander que detecta automáticamente si un PDF es PP (Pagaré) o CC (Crédito de Consumo)
y aplica la lógica de extracción correspondiente (genérica, robusta ante OCR), reutilizando utilidades del proyecto.

Salida: outputs/Santander/Santander_results_UNIFIED.xlsx y un log debug.
"""

import re
import shutil
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import difflib

# RUTs institucionales a evitar como titular (frecuentes en contratos)
INSTITUTIONAL_RUTS = {"97036000"}

# Geocoding utils (opcionales)
try:
    from geocoding_utils import (
        clean_and_fix_address,
        fix_comuna_ocr,
        apply_reference_corrections,
    )
    GEO_UTILS_AVAILABLE = True
    print("✅ Utilidades de geocodificación cargadas")
except Exception:
    GEO_UTILS_AVAILABLE = False
    print("⚠️ Utilidades de geocodificación no disponibles")
    def clean_and_fix_address(address): return address
    def fix_comuna_ocr(comuna): return comuna
    def apply_reference_corrections(df): return df

# ---------------- CONFIG ----------------
TESSERACT_EXE = r"C:\Users\cdiaz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
POPPLER_BIN = r"C:\poppler\Library\bin"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR  # Usamos la carpeta del módulo como raíz del proyecto
PDF_INPUT_DIR = PROJECT_ROOT / "pdfs" / "Santander"
TEMP_RI_ROOT = PROJECT_ROOT / "RI_Santander"
OUT_DIR = PROJECT_ROOT / "outputs" / "Santander"
OUT_XLSX = OUT_DIR / "Santander_results_UNIFIED.xlsx"
DEBUG_FILE = PROJECT_ROOT / "outputs" / "Santander_debug_unified.txt"
# ----------------------------------------

# Verificar Tesseract
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    test_img = Image.new('RGB', (40, 20), color='white')
    pytesseract.image_to_string(test_img, lang='spa')
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract disponible")
except Exception as e:
    TESSERACT_AVAILABLE = False
    print(f"⚠️ Tesseract no disponible: {e}")

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

def write_debug(s: str):
    DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEBUG_FILE, "a", encoding="utf-8") as f:
        f.write(s + "\n")

# --------- Utilidades ---------
def normalize_token(tok):
    return tok.strip().strip(" .,:;").upper()

def fuzzy_comuna(s):
    su = normalize_token(s)
    # Corrección N->Ñ y equivalentes comunes antes de comparar
    su = fix_n_to_ene(su)
    if not su: return ""
    for c in COMUNAS:
        if c in su or su in c:
            return c
    best = difflib.get_close_matches(su, COMUNAS, n=1, cutoff=0.72)
    return best[0] if best else su

def fmt_date(d, mname, y):
    m = MONTHS.get((mname or "").strip().lower())
    if not m: return ""
    try: return datetime(int(y), int(m), int(d)).strftime("%d-%m-%Y")
    except: return ""

# --------- Fechas ---------
def parse_spanish_date(text):
    t = text.replace('\n',' ')
    m = re.search(r'(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b)', t)
    if m:
        s = m.group(1).replace('-', '/')
        for fmt in ("%d/%m/%Y","%d/%m/%y"):
            try: return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
            except: pass
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

# --------- Operación ---------
def extract_operation_from_text(text):
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

# --------- RUT ---------
def find_all_ruts(text):
    matches = []
    for pat, base in [
        (r'C[ée]dula\s+de\s+Identidad\s*N[°oº\*]?\s*:?\s*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 12),
        (r'\bRUT\b[^:\d]{0,10}[:\sNNoº°]*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 10),
        (r'(?:C\.I\.|CI\b)[^:\d]{0,10}[:\s]*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 8),
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = m.start(1)
            matches.append((start, re.sub(r'[^\d]', '', m.group(1)), m.group(2).upper(), text[max(0,start-80):start+120], base))
    for m in re.finditer(r'([0-9]{1,3}(?:\.[0-9]{3}){1,2})\s*[-\s–—]*([0-9Kk])', text):
        start = m.start(1)
        ctx = text[max(0,start-80):start+120]
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

def extract_rut_global(text_pages):
    joined = "\n".join(text_pages)
    cands = []
    for m in re.finditer(r'(?:RUT|C[ée]dula\s+de\s+Identidad)[^\d]{0,15}([\d\.]{6,})\s*[-–—]?\s*([0-9Kk])', joined, re.IGNORECASE):
        rut = re.sub(r'[^\d]', '', m.group(1))
        dv = m.group(2).upper()
        if 7 <= len(rut) <= 8 and is_valid_rut(rut, dv) and rut not in INSTITUTIONAL_RUTS:
            cands.append((m.start(1), rut, dv))
    if cands:
        cands.sort(key=lambda t: t[0])
        return cands[0][1], cands[0][2]
    # Fallback sin etiqueta
    for m in re.finditer(r'\b(\d{7,8})\s*[-\s–—]*([0-9Kk])\b', joined):
        rut = m.group(1); dv = m.group(2).upper()
        ctx = joined[max(0, m.start()-60): m.end()+60].upper()
        if ("BANCO" in ctx or "SANTANDER" in ctx):
            continue
        if is_valid_rut(rut, dv) and rut not in INSTITUTIONAL_RUTS:
            return rut, dv
    return "", ""

def choose_rut_for_doc(text, ruts, doc_type="CC"):
    if not ruts: return "", ""
    sus = re.search(r'(Nombre\s+y\s+Apellidos\s+del\s+deudor|Suscriptor|Deudor|Cliente)', text, re.IGNORECASE)
    sus_pos = sus.start() if sus else None
    best = None; best_score = -1
    for (pos, rut, dv, ctx, base) in ruts:
        score = base
        # Penalizar RUTs institucionales conocidos (banco)
        if rut in INSTITUTIONAL_RUTS:
            score -= 20
        # Bonus si DV válido
        if is_valid_rut(rut, dv):
            score += 5
        # Penalizar contexto con palabras de entidad bancaria
        ctx_up = ctx.upper()
        if "BANCO" in ctx_up or "SANTANDER" in ctx_up:
            score -= 10
        if doc_type == "PP":
            if sus_pos is not None:
                score += max(0, 300 - abs(pos - sus_pos)) // 10
        if 7 <= len(rut) <= 8: score += 2
        if score > best_score:
            best_score = score; best = (rut, dv)
    return best if best else ("","")

# --------- Nombre/Dirección ---------
def cleanup_name(s: str) -> str:
    up = s.upper().strip()
    up = re.sub(r'^(NOMBRE\s+DEUDOR\s*[:\-]+\s*)', '', up)
    up = re.sub(r'^(DEUDOR\s*[:\-]+\s*)', '', up)
    up = re.sub(r'^(SUSCRIPTOR\s*[:\-]+\s*)', '', up)
    return re.sub(r"\s+", " ", up).strip()

def extract_nombre_generic(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    name_cands = []
    patterns = [
        r'^(?:Nombre\s+y\s+Apellidos\s+del\s+deudor|Suscriptor|Deudor|Cliente)[:\.\s-]*(.+)$',
        r'^(?:Señor|Señora|Sr\.?|Sra\.?)[:\.\s-]*(.+)$',
    ]
    for i, ln in enumerate(lines):
        for pat in patterns:
            m = re.match(pat, ln, re.IGNORECASE)
            if m:
                val = (m.group(1) or "").strip()
                if not val and i+1 < len(lines):
                    val = lines[i+1].strip()
                name_cands.append(val)
    # Heurística: nombre con 2-5 palabras, sin términos legales ni S.A.
    for cand in name_cands:
        up = cand.upper()
        if any(bad in up for bad in ["PAGARE", "PAGARÉ", "CREDITO", "CRÉDITO", "S.A", "SOCIEDAD", "BANCO"]):
            continue
        words = [w for w in re.split(r"\s+", up) if w and len(w) > 1]
        if 2 <= len(words) <= 6 and len(up) <= 80:
            return cleanup_name(up)
    # Fallback 1: buscar línea previa a una línea con RUT
    for i, ln in enumerate(lines):
        if re.search(r'\bRUT\b|C[eé]dula\s+de\s+Identidad', ln, re.IGNORECASE):
            prev = lines[i-1].strip() if i > 0 else ""
            up = prev.upper()
            if prev and re.search(r"[A-Za-zÁÉÍÓÚÑ]{2,}", prev) and not any(b in up for b in ["BANCO","SANTANDER","CHILE","S.A","PAGARE","CREDITO"]):
                return cleanup_name(up)
    # Fallback 2: primera línea con pinta de nombre en mayúsculas
    for ln in lines[:15]:
        up = ln.upper()
        if re.search(r"^[A-ZÁÉÍÓÚÑ\s]{8,}$", up) and len(up.split()) >= 2 and len(up) <= 80:
            if not any(bad in up for bad in ["PAGARE", "PAGARÉ", "CREDITO", "CRÉDITO", "BANCO", "SANTANDER", "CHILE"]):
                return cleanup_name(up)
    return ""

def looks_like_physical_address(s):
    if not s: return False
    if re.search(r'\d{1,5}', s): return True
    return bool(re.search(r'\b(CALLE|AVENIDA|AVDA|AV|PJE|PAS|PASAJE|Nº|N°|DEPTO|DPTO|LOCAL|BLOCK)\b', s, re.IGNORECASE))

def extract_domicilio_and_comuna(text):
    lines_raw = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    lines = [re.sub(r'[\u2000-\u206F\u2E00-\u2E7F]+', ' ', ln) for ln in lines_raw]
    for i, ln in enumerate(lines):
        if not re.search(r'^\s*(?:Domicilio|Direcci[oó]n)\b', ln, re.IGNORECASE):
            continue
        m = re.search(r'^\s*(?:Domicilio|Direcci[oó]n)\s*[:.\-]+\s*(.*)$', ln, re.IGNORECASE)
        tail = (m.group(1) if m else "").strip()
        ext = tail
        if (len(ext) < 6 or ',' not in ext) and i+1 < len(lines) and looks_like_physical_address(lines[i+1]):
            ext = (ext + " " + lines[i+1].strip()).strip()
        # Buscar comuna etiquetada en líneas siguientes
        comuna_lab = ""
        for j in range(1, 4):
            if i+j < len(lines):
                m2 = re.search(r'\bComuna\b\s*[:.\-]*\s*(.+)$', lines[i+j], re.IGNORECASE)
                if m2:
                    comuna_lab = m2.group(1).strip()
                    break
        if ',' in ext and not comuna_lab:
            addr, tail2 = ext.rsplit(',', 1)
            return fix_n_to_ene(addr.strip().upper()), fuzzy_comuna(tail2)
        if ext and comuna_lab:
            return fix_n_to_ene(ext.strip().upper()), fuzzy_comuna(comuna_lab)
    # Fallback: "domiciliado en" / "con domicilio en"
    m = re.search(r'(?:domiciliad[oa]\s+en|con\s+domicilio\s+en)\s+([^\n\r]+)', text, re.IGNORECASE)
    if m:
        tail = m.group(1).strip()
        if ',' in tail:
            addr, tail2 = tail.rsplit(',', 1)
            return fix_n_to_ene(addr.strip().upper()), fuzzy_comuna(tail2)
        return fix_n_to_ene(tail.upper()), ""
    return "", ""
 
# --------- Corrección N por Ñ (nombres, direcciones, comunas) ---------
def fix_n_to_ene(text: str) -> str:
    if not text:
        return text
    repl = [
        (r'\bPENA\b', 'PEÑA'), (r'\bMUNOZ\b', 'MUÑOZ'), (r'\bNUNEZ\b', 'NÚÑEZ'), (r'\bIBANEZ\b', 'IBAÑEZ'), (r'\bYANEZ\b', 'YÁÑEZ'),
        (r'\bNINO\b', 'NIÑO'), (r'\bNINA\b', 'NIÑA'), (r'\bESPANA\b', 'ESPAÑA'), (r'\bVINA\s+DEL\s+MAR\b', 'VIÑA DEL MAR'),
        (r'\bPENALOLEN\b', 'PEÑALOLÉN'), (r'\bPENAFLOR\b', 'PEÑAFLOR'), (r'\bNUNOA\b', 'ÑUÑOA'), (r'\bCANETE\b', 'CAÑETE'),
        (r'\bSENOR\b', 'SEÑOR'), (r'\bSENORA\b', 'SEÑORA'), (r'\bDUENO\b', 'DUEÑO'), (r'\bANO\b', 'AÑO'), (r'\bANOS\b', 'AÑOS')
    ]
    out = text
    for pat, rep in repl:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out

# --------- Montos ---------
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
        return f"{num:,}".replace(",", ".") if num is not None else "", num
    return "", None

def extract_credit_amount_cc(text_pages):
    joined = "\n".join(text_pages)
    # Prefer "la suma de $..."
    m = re.search(r'la\s+suma\s+de[^$\d]{0,10}\$\s*([0-9\.,]+)', joined, re.IGNORECASE)
    if m:
        clean = re.sub(r'[^\d]', '', m.group(1))
        if clean.isdigit():
            return f"{int(clean):,}".replace(",", ".")
    # Fallback: mayor monto con $ en el documento
    best = 0
    for m in re.finditer(r'\$\s*([0-9\.,]{4,})', joined):
        clean = re.sub(r'[^\d]', '', m.group(1))
        if clean.isdigit():
            val = int(clean)
            best = max(best, val)
    if best > 0:
        return f"{best:,}".replace(",", ".")
    return ""

# --------- RUT Utils ---------
def rut_calc_dv(num_str: str) -> str:
    if not num_str.isdigit():
        return ""
    digits = list(map(int, reversed(num_str)))
    factors = [2,3,4,5,6,7]
    s = sum(d * factors[i % len(factors)] for i, d in enumerate(digits))
    mod = 11 - (s % 11)
    if mod == 11: return "0"
    if mod == 10: return "K"
    return str(mod)

def is_valid_rut(rut: str, dv: str) -> bool:
    rut_num = re.sub(r"[^\d]", "", rut or "")
    dv = (dv or "").upper()
    if not rut_num or not dv: return False
    return rut_calc_dv(rut_num) == dv

# --------- Cuotas/Tasa ---------
def extract_cuotas_tasa(text_pages):
    joined = "\n".join(text_pages)
    page1 = text_pages[0] if text_pages else ""
    cuotas = ""
    tasa = ""
    monto_cuota = ""
    monto_ultima = ""
    f_venc_1 = ""
    f_venc_ult = ""
    # Cuotas (global)
    m = re.search(r'\b(?:en\s+)?(\d{1,3})\s+cuotas\b', joined, re.IGNORECASE)
    if m:
        cuotas = m.group(1)
    # Tasa % (buscar cerca de 'tasa' o 'interés' en página 1)
    for pat in [
        r'\btasa\b[^%\n\r]{0,80}?([0-9][0-9\.,]{0,4})\s*%',
        r'inter[eé]s[^%\n\r]{0,80}?([0-9][0-9\.,]{0,4})\s*%'
    ]:
        m = re.search(pat, page1, re.IGNORECASE)
        if m:
            tasa = m.group(1).replace(',', '.').strip() + '%'
            break
    if not tasa:
        # Fallback: cualquier número con % cerca de 'tasa' o 'interes'
        for m in re.finditer(r'([0-9][0-9\.,]{0,4})\s*%', page1):
            start = m.start()
            ctx = page1[max(0, start-120): m.end()+10].lower()
            if 'tasa' in ctx or 'interes' in ctx or 'interés' in ctx:
                val = m.group(1).replace(',', '.')
                tasa = val + '%'
                break
    # Monto de la cuota: patrón típico 'iguales de $<monto>' en página 1
    for pat in [
        r'iguales\s+de\s*\$\s*([0-9\.,]+)',
        r'cuota\s+mensual[^$\n\r]{0,60}\$\s*([0-9\.,]+)',
        r'monto\s+de\s+la\s+cuota[^$\n\r]{0,60}\$\s*([0-9\.,]+)'
    ]:
        m = re.search(pat, page1, re.IGNORECASE)
        if m:
            clean = re.sub(r'[^\d]', '', m.group(1))
            if clean.isdigit():
                monto_cuota = f"{int(clean):,}".replace(",", ".")
                break
    # Monto última cuota: 'una última de $ <monto>'
    m = re.search(r'una\s+[úu]ltima\s+de\s*\$\s*([0-9\.,]+)', page1, re.IGNORECASE)
    if m:
        clean = re.sub(r'[^\d]', '', m.group(1))
        if clean.isdigit():
            monto_ultima = f"{int(clean):,}".replace(",", ".")
    # Fechas: primera (a contar del ...) y última (con vencimiento el ...)
    m = re.search(r'a\s+contar\s+del\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+del\s+año\s+(\d{4})', page1, re.IGNORECASE)
    if m:
        f_venc_1 = fmt_date(m.group(1), m.group(2), m.group(3))
    if not f_venc_1:
        # Fallbacks
        for pat in [
            r'(?:primera|1[aª]?|1\.)\s*cuota[^\n\r]{0,30}(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'(?:primera|1[aª]?|1\.)\s*cuota[^\n\r]{0,60}a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})',
        ]:
            m = re.search(pat, page1, re.IGNORECASE)
            if m:
                if m.lastindex == 1:
                    try:
                        for fmt in ("%d/%m/%Y","%d/%m/%y","%d-%m-%Y","%d-%m-%y"):
                            try:
                                f_venc_1 = datetime.strptime(m.group(1).replace('-', '/'), fmt).strftime("%d-%m-%Y")
                                break
                            except: pass
                    except: pass
                else:
                    f_venc_1 = fmt_date(m.group(1), m.group(2), m.group(3))
                if f_venc_1:
                    break
    # Última: buscar alrededor de 'una última de $...' 'con vencimiento el ...'
    m = re.search(r'una\s+[úu]ltima\s+de\s*\$[^\n\r]{0,80}?con\s+vencimiento\s+el\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+del\s+año\s+(\d{4})', page1, re.IGNORECASE)
    if m:
        f_venc_ult = fmt_date(m.group(1), m.group(2), m.group(3))
    if not f_venc_ult:
        # Más flexibles
        for pat in [
            r'(?:[úu]ltima|\b\d+\s*/\s*\d+\b\s*cuota)[^\n\r]{0,40}(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'vencimiento\s+el\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+del\s+año\s+(\d{4})',
        ]:
            m = re.search(pat, page1, re.IGNORECASE)
            if m:
                if m.lastindex == 1:
                    try:
                        for fmt in ("%d/%m/%Y","%d/%m/%y","%d-%m-%Y","%d-%m-%y"):
                            try:
                                f_venc_ult = datetime.strptime(m.group(1).replace('-', '/'), fmt).strftime("%d-%m-%Y")
                                break
                            except: pass
                    except: pass
                else:
                    f_venc_ult = fmt_date(m.group(1), m.group(2), m.group(3))
                if f_venc_ult:
                    break
    return cuotas, tasa, monto_cuota, monto_ultima, f_venc_1, f_venc_ult

# --------- OCR/PDF ---------
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

# --------- CC Name/Address/Date helpers ---------
def _find_after_label(lines, start_idx, label_regex, max_ahead=8):
    rr = re.compile(label_regex, re.IGNORECASE)
    for j in range(start_idx, min(len(lines), start_idx + max_ahead)):
        m = rr.search(lines[j])
        if m:
            # tail after label punctuation
            tail = re.sub(label_regex, "", lines[j], flags=re.IGNORECASE).strip()
            if tail:
                return tail, j
            # otherwise next non-empty line
            for k in range(j + 1, min(len(lines), j + 3)):
                if lines[k].strip():
                    return lines[k].strip(), k
    return "", -1

def _split_address_comuna_inline(s):
    # If there is a comma, split on last comma
    if "," in s:
        addr, tail = s.rsplit(",", 1)
        return addr.strip(), fuzzy_comuna(tail)
    # Try from end building 1..3 tokens to match known comunas
    toks = [t for t in re.split(r"\s+", s.strip()) if t]
    for take in range(1, min(4, len(toks)) + 1):
        tail = " ".join(toks[-take:])
        fc = fuzzy_comuna(tail)
        if fc and fc in COMUNAS:
            addr = " ".join(toks[:-take])
            return addr.strip(), fc
    return s.strip(), ""

def extract_cc_name_addr_comuna_and_date(text_pages):
    joined = "\n".join(text_pages)
    lines = [ln.strip() for ln in joined.splitlines() if ln.strip()]
    name = ""; addr = ""; comuna = ""; fecha = ""
    # Find Cliente/deudor block
    for i, ln in enumerate(lines):
        if re.search(r'Cliente\s*/?\s*deudor', ln, re.IGNORECASE):
            # Name follows
            cand, at = _find_after_label(lines, i, r'^\s*Cliente\s*/?\s*deudor\s*[:\-]*\s*')
            if cand:
                name = cleanup_name(cand)
            # Address line typically starts with Domicilio
            a2, at2 = _find_after_label(lines, i, r'^\s*Domicilio\s*[:\-]*\s*')
            if a2:
                addr, comuna = _split_address_comuna_inline(a2)
            break
    # Date like: En SANTIAGO, a 13 de FEBRERO del año 2025
    m = re.search(r'\bEn\s+[A-ZÁÉÍÓÚÑ\s]+,?\s*a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+del?\s+año\s+(\d{4})', joined, re.IGNORECASE)
    if m:
        fecha = fmt_date(m.group(1), m.group(2), m.group(3))
    if not fecha:
        fecha = parse_spanish_date(joined)
    return name, addr, comuna, fecha

# --------- Procesamiento ---------
def detect_document_type(text_pages):
    combined = "\n".join(text_pages)
    up = combined.upper()
    pp_ind = ["PAGARÉ", "PAGARE", "DOCUMENTO MERCANTIL", "ME OBLIGO A PAGAR"]
    cc_ind = ["CRÉDITO DE CONSUMO", "CREDITO DE CONSUMO", "CUOTAS", "TASA DE INTERÉS", "PLAN DE PAGOS"]
    pp = sum(1 for s in pp_ind if s in up)
    cc = sum(1 for s in cc_ind if s in up)
    if re.search(r'\ben\s+\d+\s+cuotas\b', combined, re.IGNORECASE): cc += 2
    return "PP" if pp > cc else "CC"

def process_document_unified(text_pages, doc_type, source_name: str | None = None):
    rows = []
    for text in text_pages:
        op = extract_operation_from_text(text)
        ruts = find_all_ruts(text)
        rut, dv = choose_rut_for_doc(text, ruts, doc_type) if ruts else ("","")
        nombre = extract_nombre_generic(text)
        direccion, comuna = extract_domicilio_and_comuna(text)
        fecha_sus = parse_spanish_date(text)
        monto_fmt, _ = extract_amount(text)
        rows.append({
            "text": text,
            "OPERACIÓN": op, "RUT": rut, "DV": dv, "NOMBRE": nombre,
            "DIRECCION": direccion, "COMUNA": comuna,
            "FECHA_SUSCRIPCION": fecha_sus, "MONTO_CREDITO": monto_fmt
        })
    def score_row_basic(r):
        return (50 if r.get("OPERACIÓN") else 0) + (30 if r.get("RUT") else 0) + (20 if r.get("NOMBRE") else 0)
    best = max(rows, key=score_row_basic) if rows else {}
    operation = extract_operation_allpages([r["text"] for r in rows]) or best.get("OPERACIÓN","")
    # Prefer operation from filename if available
    if source_name:
        m = re.search(r'(\d{6,})', source_name)
        if m:
            operation = m.group(1)
    cuotas, tasa, monto_cuota, monto_ult, f_v1, f_vu = extract_cuotas_tasa(text_pages)
    # Si el RUT no se encontró en la mejor página, intentar globalmente
    if not best.get("RUT"):
        grut, gdv = extract_rut_global(text_pages)
        if grut:
            best["RUT"], best["DV"] = grut, gdv
    # Para CC: reforzar nombre/dirección/comuna/fecha y monto
    if doc_type == "CC":
        n2, a2, c2, f2 = extract_cc_name_addr_comuna_and_date(text_pages)
        if n2: best["NOMBRE"] = n2
        if a2: best["DIRECCION"] = a2
        if c2: best["COMUNA"] = c2
        if f2: best["FECHA_SUSCRIPCION"] = f2
        m2 = extract_credit_amount_cc(text_pages)
        if m2: best["MONTO_CREDITO"] = m2

    # Normalizar N->Ñ antes de correcciones de referencia
    addr_norm = fix_n_to_ene(best.get("DIRECCION",""))
    comuna_norm = fuzzy_comuna(fix_n_to_ene(best.get("COMUNA","")))
    final_row = {
        "OPERACION_1": operation,
        "RUT": best.get("RUT",""), "DV": best.get("DV",""), "NOMBRE": fix_n_to_ene(best.get("NOMBRE","")),
        "DIRECCION": clean_and_fix_address(addr_norm), "COMUNA": fix_comuna_ocr(comuna_norm),
        "FECHA_SUSCRIPCION_1": best.get("FECHA_SUSCRIPCION",""),
        "MONTO_CREDITO_1": best.get("MONTO_CREDITO",""),
    "CUOTAS_1": cuotas or "", "TASA_1": tasa or "", "MONTO_CUOTA_1": monto_cuota or "", "MONTO_ULTIMA_CUOTA_1": monto_ult or "",
        "FECHA_VENCIMIENTO_1_CUOTA_1": f_v1 or "", "FECHA_VENCIMIENTO_ULTIMA_CUOTA_1": f_vu or "",
        "CUOTA_MOROSA_1": "", "FECHA_CUOTA_MOROSA_1": "",
        "CAPITAL_1": best.get("MONTO_CREDITO",""),
        "EXHORTO": "SANTIAGO", "SUCURSAL": "SANTIAGO", "PRODUCTO": doc_type,
        "NOMBRE_APODERADO": "", "NOMBRE_APODERADO_2": "",
    }
    write_debug("---- COMBINED ROW SANTANDER ----")
    for k,v in final_row.items(): write_debug(f"{k}: {v}")
    write_debug("---- END COMBINED ROW SANTANDER ----\n")
    return final_row

# --------- Main ---------
def main():
    parser = argparse.ArgumentParser(description="Procesar PDFs Santander (PP/CC) -> Excel")
    parser.add_argument("--dpi", type=int, default=200, help="DPI para convertir PDF a imágenes")
    args = parser.parse_args()

    print("🚀 Inicio: proceso Santander UNIFICADO (PP/CC)")
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
            images = convert_pdf_to_images(pdf, ri_folder, POPPLER_BIN, dpi=args.dpi)
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
            doc_type = detect_document_type(text_pages)
            print(f"  📋 Tipo detectado: {doc_type}")
            row = process_document_unified(text_pages, doc_type, source_name=pdf.name)
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
        if GEO_UTILS_AVAILABLE:
            print("📋 Aplicando correcciones de referencia...")
            df_new = apply_reference_corrections(df_new)
        # Verificador rápido
        missing_counts = {k: 0 for k in ["OPERACION_1","RUT","DV","NOMBRE","COMUNA"]}
        for _, row in df_new.iterrows():
            for k in missing_counts:
                if not str(row.get(k, "")).strip():
                    missing_counts[k] += 1
        write_debug("\n==== VERIFICADOR DE CAMPOS CRÍTICOS ====")
        for k, v in missing_counts.items():
            write_debug(f"Faltantes {k}: {v}")
        write_debug("=======================================\n")

        try:
            df_new.to_excel(OUT_XLSX, index=False)
            print(f"✅ Guardado final en: {OUT_XLSX}")
        except PermissionError:
            alt = OUT_DIR / f"Santander_results_UNIFIED_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            df_new.to_excel(alt, index=False)
            print(f"⚠️ Archivo Excel en uso. Guardado en: {alt}")
        print(f"📋 Debug info en: {DEBUG_FILE}")
        print(f"📊 Filas extraídas: {len(all_rows)}")
    else:
        print("❌ No se extrajeron filas. Revisa", DEBUG_FILE)

if __name__ == "__main__":
    main()

# --------------- Public API for Web use ---------------
def process_pdf_files(pdf_paths: list[str], geocode: bool = False, output_dir: str | None = None, fast: bool = False, dpi: int | None = None) -> tuple[str, str]:
    """
    Procesa una lista de rutas de PDFs y genera un Excel con el resultado.
    Devuelve (excel_path, debug_file_path).

    Crea un archivo Excel con timestamp en output_dir (por defecto outputs/Santander/web)
    y un archivo de debug asociado. Usa la lógica unificada PP/CC.
    """
    out_base = Path(output_dir) if output_dir else (OUT_DIR / "web")
    out_base.mkdir(parents=True, exist_ok=True)

    # Crear nombres con timestamp para no pisar ejecuciones concurrentes
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out_base / f"Santander_results_UNIFIED_{ts}.xlsx"
    debug_path = out_base / f"Santander_debug_unified_{ts}.txt"
    ri_root = TEMP_RI_ROOT / f"web_{ts}"

    # Redirigir temporalmente el debug global a este archivo
    global DEBUG_FILE
    prev_debug = DEBUG_FILE
    DEBUG_FILE = debug_path
    try:
        DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            DEBUG_FILE.unlink(missing_ok=True)
        except Exception:
            pass

        if not TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract no disponible en el servidor")

        all_rows = []
        dpi_val = dpi if dpi is not None else (150 if fast else 200)
        for pdf in pdf_paths:
            pdf_path = Path(pdf)
            if not pdf_path.exists():
                write_debug(f"WARN: PDF no existe -> {pdf}")
                continue
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
                row = process_document_unified(text_pages, doc_type, source_name=pdf_path.name)
                all_rows.append(row)
            except Exception as e:
                write_debug(f"ERROR procesando {pdf_path.name}: {e}")
            finally:
                try:
                    if ri_folder.exists(): shutil.rmtree(ri_folder)
                except Exception as e:
                    write_debug(f"WARNING cleanup {ri_folder}: {e}")

        if not all_rows:
            pd.DataFrame(columns=UNIFIED_COLUMNS).to_excel(xlsx_path, index=False)
            return str(xlsx_path), str(debug_path)

        df_new = pd.DataFrame(all_rows, columns=UNIFIED_COLUMNS)
        if GEO_UTILS_AVAILABLE and geocode:
            df_new = apply_reference_corrections(df_new)

        # Verificador rápido de campos críticos (web)
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
