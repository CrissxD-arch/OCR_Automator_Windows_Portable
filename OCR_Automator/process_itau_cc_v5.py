#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_itau_cc_with_pdf_conversion_v5.py

Mejoras clave:
- Prioriza y bloquea el uso del bloque de identidad del deudor (Nombre, Cédula, Domicilio, Comuna/Ciudad).
- Filtra explícitamente encabezado legal del banco (oficina, Presidente Riesco, 'comuna de Las ...').
- No permite que el encabezado legal reemplace Dirección/Comuna válidas del bloque de identidad.
- Mantiene extracción de CUOTAS, TASA, montos y fechas de 1ª/última cuota.
- Convierte PDFs (pdfs/Itau_CC) -> RI/<pdf>/pageN.png, limpia RI, y guarda Excel en outputs/Itau/Itau_results_CC.xlsx.
- Debug en outputs/Itau_debug_cc.txt
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
    # Funciones dummy para evitar errores
    def clean_and_fix_address(addr): return addr
    def fix_comuna_ocr(comuna): return comuna
    def apply_reference_corrections(df): return df
    def validate_rut_dv(rut, dv): return rut, dv, True

# ---------------- CONFIG ----------------
TESSERACT_EXE = r"C:\Users\cdiaz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
POPPLER_BIN = r"C:\poppler\Library\bin"
PROJECT_ROOT = Path.cwd()
PDF_INPUT_DIR = PROJECT_ROOT / "pdfs" / "Itau"  # Cambiado para usar la carpeta existente
TEMP_RI_ROOT = PROJECT_ROOT / "RI"
OUT_DIR = PROJECT_ROOT / "outputs" / "Itau"
OUT_XLSX = OUT_DIR / "Itau_results_REAL.xlsx"  # Nombre diferente para distinguir
DEBUG_FILE = PROJECT_ROOT / "outputs" / "Itau_debug_real.txt"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OCR-Automator/1.0 (cdiaz@ejemplo.com)"
# ----------------------------------------

# Verificar si Tesseract está disponible
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    # Test básico
    test_img = Image.new('RGB', (100, 100), color='white')
    pytesseract.image_to_string(test_img, lang='spa')
    TESSERACT_AVAILABLE = True
    print("✅ Tesseract disponible")
except Exception as e:
    TESSERACT_AVAILABLE = False
    print(f"⚠️ Tesseract no disponible: {e}")

COLUMNS = [
    "OPERACION_1","RUT","DV","NOMBRE","DIRECCION","COMUNA",
    "FECHA_SUSCRIPCION_1","MONTO_CREDITO_1","CUOTAS_1","TASA_1","MONTO_CUOTA_1","MONTO_ULTIMA_CUOTA_1",
    "FECHA_VENCIMIENTO_1_CUOTA_1","FECHA_VENCIMIENTO_ULTIMA_CUOTA_1",
    "CUOTA_MOROSA_1","FECHA_CUOTA_MOROSA_1",
    "CAPITAL_1","EXHORTO","SUCURSAL","PRODUCTO","NOMBRE_APODERADO","NOMBRE_APODERADO_2"
]

COMUNAS = [
    "SANTIAGO","LAS CONDES","PROVIDENCIA","ÑUÑOA","MAIPU","PUENTE ALTO","LA FLORIDA",
    "CONCEPCION","CONCEPCIÓN","CORONEL","PUERTO AYSÉN","PUERTO AYSEN","TALCAHUANO","TALCA",
    "VALPARAISO","VALPARAÍSO","VIÑA DEL MAR","QUILPUE","QUILPUÉ","PUERTO MONTT","TEMUCO",
    "ANTOFAGASTA","COPIAPO","COPIAPÓ","RANCAGUA","OSORNO","LA SERENA","CHILLAN","CHILLÁN",
    "PUNTA ARENAS","CURICO","CURICÓ","ILLAPEL","COQUIMBO","LINARES","IQUIQUE","SAN BERNARDO",
    "COLINA","VITACURA","PEDRO AGUIRRE CERDA","PUERTO VARAS"
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

# --------------- Utilities ---------------
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

def normalize_token(tok): return tok.strip().strip(" .,:;").upper()

def fuzzy_comuna(s):
    su = normalize_token(s)
    if not su: return ""
    # contains exact
    for c in COMUNAS:
        if c in su or su in c:
            return c
    # fuzzy
    best = difflib.get_close_matches(su, COMUNAS, n=1, cutoff=0.72)
    return best[0] if best else su

def is_bank_header_line(s: str) -> bool:
    if not s: return False
    su = s.upper()
    return any(k in su for k in [
        "EN SU OFICINA", "PRESIDENTE RIESCO", "BANCO ITA", "COMUNA DE LAS"
    ])

def looks_like_physical_address(s):
    if not s: return False
    if re.search(r'\d{1,5}', s): return True
    return bool(re.search(r'\b(CALLE|AVENIDA|AVDA|AV|PJE|PAS|PASAJE|MARINA|CIRCUNVAL|BOULEVARD|BLVD|PROLONGACION|DEPARTAMENTO|DEPTO|DPTO|Nº|N°|LOCAL|EDIF|BLOCK|BLOQUE|BRISAS)\b', s, re.IGNORECASE))

# --------------- Dates parsing ---------------
def parse_spanish_date(text):
    t = text.replace('\n',' ')
    m = re.search(r'(\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b)', t)
    if m:
        s = m.group(1).replace('-', '/')
        for fmt in ("%d/%m/%Y","%d/%m/%y"):
            try: return datetime.strptime(s, fmt).strftime("%d-%m-%Y")
            except: pass
    m = re.search(r'\b(?:en\s+[A-Za-zÁÉÍÓÚÑáéíóúñ]+,?\s*)?a\s+(\d{1,2})\s+de\s+([A-Za-záéíóúñÑ]+)\s+de\s+(\d{4})', t, re.IGNORECASE)
    if m: return fmt_date(m.group(1), m.group(2), m.group(3))
    return ""

def parse_first_last_due_dates(text):
    t = text.replace('\n',' ')
    m = re.search(r'primera\s+cuota\s+el\s+d[ií]a?\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})'
                  r'.*?l[aá]\s+[úu]ltima(?:\s+cuota)?\s+el\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})',
                  t, re.IGNORECASE)
    if m:
        return fmt_date(m.group(1), m.group(2), m.group(3)), fmt_date(m.group(4), m.group(5), m.group(6))
    m1 = re.search(r'primera\s+cuota\s+el\s+d[ií]a?\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})', t, re.IGNORECASE)
    m2 = re.search(r'[úu]ltima(?:\s+cuota)?\s+el\s+(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})', t, re.IGNORECASE)
    f1 = fmt_date(*m1.groups()) if m1 else ""
    f2 = fmt_date(*m2.groups()) if m2 else ""
    return f1, f2

# --------------- Operation / RUT / Name ---------------
def extract_operation_from_text(text):
    for pat in [
        r'N[°º\*]?\s*(?:Operaci[oó]n|Operación)[:\s]*([0-9]{6,})',
        r'\bOperaci[oó]n\s*N[°º]?\s*([0-9]{6,})',
        r'N[°º\*]?\s*Producto[:\s]*([0-9]{6,})'
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m: return m.group(1).strip()
    return ""

def extract_operation_allpages(text_pages):
    for t in text_pages:
        op = extract_operation_from_text(t)
        if op: return op
    return ""

def find_all_ruts(text):
    matches = []
    # Etiquetados (Cédula / RUT)
    for pat, base in [
        (r'C[eé]dula\s+de\s+Identidad\s*N[°\*]?\s*[:\s]+([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 12),
        (r'(?:C\.I\.\/RUT|C\.L\/RUT|RUT)[^:\d]{0,10}[:\s]*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])', 10)
    ]:
        for m in re.finditer(pat, text, re.IGNORECASE):
            start = m.start(1)
            matches.append((start, re.sub(r'[^\d]', '', m.group(1)), m.group(2).upper(), text[max(0,start-80):start+120], base))
    # Genéricos
    for m in re.finditer(r'([0-9]{1,3}(?:\.[0-9]{3}){1,2})\s*[-\s–—]*([0-9Kk])', text):
        start = m.start(1)
        matches.append((start, re.sub(r'[^\d]', '', m.group(1)), m.group(2).upper(), text[max(0,start-80):start+120], 3))
    for m in re.finditer(r'\b(\d{7,8})\s*[-\s–—]*([0-9Kk])', text):
        start = m.start(1)
        matches.append((start, m.group(1), m.group(2).upper(), text[max(0,start-80):start+120], 2))
    return matches

def choose_rut_for_doc(text, ruts):
    if not ruts: return "", ""
    sus = re.search(r'(Nombre\s+y\s+Apellidos\s+del\s+deudor|Suscriptor(?:\s+o\s+Deudor)?|Deudor|Cliente\/Deudor)', text, re.IGNORECASE)
    sus_pos = sus.start() if sus else None
    banco_pat = re.compile(r'\bBanco\b|\bIta[uú]\b|Representado por', re.IGNORECASE)
    best = None; best_score = -1
    for (pos, rut, dv, ctx, base) in ruts:
        score = base
        if sus_pos is not None:
            score += max(0, 300 - abs(pos - sus_pos)) // 10
        if not banco_pat.search(ctx): score += 5
        if 7 <= len(rut) <= 8: score += 2
        if score > best_score:
            best_score = score; best = (rut, dv)
    return best if best else ("","")

def extract_nombre_generic(text):
    # Fallback cuando no hay bloque identidad
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        m = re.match(r'^(?:Suscriptor(?:\s+o\s+Deudor)?|Deudor|Cliente\/Deudor)[:\.\s-]*(.+)$', ln, re.IGNORECASE)
        if m:
            name = (m.group(1) or "").strip()
            return (name or (lines[i+1].strip() if i+1 < len(lines) else "")).upper()
    return ""

# --------------- Identity block (pág. 3 típica) ---------------
def extract_cc_identity_block(text_pages):
    """
    Prioriza etiquetas exactas (multilínea):
      - Nombre y Apellidos del deudor:
      - Cédula de Identidad N* :
      - Domicilio :
      - Comuna : (o Ciudad :)
    Retorna dict con ok: True si al menos address o comuna vienen del bloque (no encabezado banco).
    """
    ident = {"name":"","rut":"","dv":"","address":"","comuna":"","ok":False}
    for page_idx, text in enumerate(text_pages, start=1):
        # Usar flags re.M para obedecer inicios de línea
        # Nombre
        mname = re.search(r'^\s*Nombre\s+y\s+Apellidos\s+del\s+deudor\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mname and not ident["name"]:
            ident["name"] = mname.group(1).strip().upper()
        # Cédula
        mrut = re.search(r'^\s*C[eé]dula\s+de\s+Identidad\s*N[°\*]?\s*[:]\s*([\d\.\,]{6,})\s*[-–—]?\s*([0-9Kk])\s*$', text, re.IGNORECASE | re.MULTILINE)
        if mrut and not ident["rut"]:
            ident["rut"] = re.sub(r'[^\d]', '', mrut.group(1))
            ident["dv"] = mrut.group(2).upper()
        # Domicilio
        mdom = re.search(r'^\s*Domicilio\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mdom and not ident["address"]:
            cand = mdom.group(1).strip()
            if not is_bank_header_line(cand):
                ident["address"] = cand.upper()
        # Comuna
        mcom = re.search(r'^\s*Comuna\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
        if mcom and not ident["comuna"]:
            ident["comuna"] = fuzzy_comuna(mcom.group(1))
        # Ciudad (respaldo)
        if not ident["comuna"]:
            mciu = re.search(r'^\s*Ciudad\s*[:]\s*(.+)$', text, re.IGNORECASE | re.MULTILINE)
            if mciu:
                ident["comuna"] = fuzzy_comuna(mciu.group(1))
    # Marcar ok si dirección o comuna válidas
    if ident["address"] and not is_bank_header_line(ident["address"]):
        ident["ok"] = True
    if ident["comuna"]:
        # Evitar artefacto "COMUNA DE LAS"
        if ident["comuna"].upper().startswith("COMUNA DE "):
            ident["comuna"] = ""
        else:
            ident["ok"] = True
    write_debug(f"[IDENT] {ident}")
    return ident

# --------------- Fallback domicilio/comuna (filtrado) ---------------
def extract_domicilio_and_comuna(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # etiqueta 'Domicilio :'
    for i, ln in enumerate(lines):
        if re.search(r'^\s*Domicilio\s*[:]\s*', ln, re.IGNORECASE):
            tail = re.split(r'[:]\s*', ln, maxsplit=1)[-1]
            if not is_bank_header_line(tail) and looks_like_physical_address(tail):
                return tail.strip().upper(), ""
            if i+1 < len(lines):
                nxt = lines[i+1]
                if not is_bank_header_line(nxt) and looks_like_physical_address(nxt):
                    return nxt.strip().upper(), ""
    # patrón ', <COMUNA>' pero filtrando encabezado
    joined = "\n".join(lines)
    for m in re.finditer(r'([A-Za-z0-9\.\s\-]{4,200}?),\s*([A-Za-zÁÉÍÓÚÑáéíóúñ\s\-]{3,40})[\.]?', joined, re.IGNORECASE):
        addr = m.group(1).strip(); tail = m.group(2)
        if is_bank_header_line(addr) or "COMUNA DE " in tail.upper(): continue
        if looks_like_physical_address(addr):
            return addr.upper(), fuzzy_comuna(tail)
    return "", ""

# --------------- Montos / Tasa / Cuotas ---------------
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

def extract_cuotas_and_montos(text):
    t = text.replace("\n", " ")
    cuotas = ""
    monto_cuota = ""
    monto_ult_cuota = ""
    m = re.search(r'\ben\s+(\d{1,3})\s+cuotas\b', t, re.IGNORECASE)
    if m: cuotas = m.group(1)
    m = re.search(r'por\s+la\s+suma\s+de\s*\$\s*([\d\.\,]+)\s*(?:cada|cada\s+una|cada\s+una\s+de\s+ellas)?', t, re.IGNORECASE)
    if m:
        clean = re.sub(r'[^\d]', '', m.group(1)); 
        if clean.isdigit(): monto_cuota = format_thousands_dot(int(clean))
    m = re.search(r'[y\s,]+(?:una\s+)?[úu]ltima(?:\s+cuota)?\s+de\s*\$\s*([\d\.\,]+)', t, re.IGNORECASE)
    if m:
        clean = re.sub(r'[^\d]', '', m.group(1)); 
        if clean.isdigit(): monto_ult_cuota = format_thousands_dot(int(clean))
    return cuotas, monto_cuota, monto_ult_cuota

def extract_tasa(text):
    m = re.search(r'tasa[^%]{0,50}?(\d{1,2}[\.,]\d{1,2})\s*%', text, re.IGNORECASE)
    if m: return f"{m.group(1).replace('.', ',')}%"
    m = re.search(r'inter[eé]s(?:[^%]{0,50})?(\d{1,2}[\.,]\d{1,2})\s*%', text, re.IGNORECASE)
    if m: return f"{m.group(1).replace('.', ',')}%"
    return ""

def extract_cuota_morosa(text):
    m = re.search(r'cuota\s+morosa\s*(\d{1,3})', text, re.IGNORECASE)
    cm = m.group(1) if m else ""
    f = ""
    mf = re.search(r'cuota\s+morosa.*?(\d{1,2})\s+de\s+([A-Za-zÁÉÍÓÚÑáéíóúñ]+)\s+de\s+(\d{4})', text, re.IGNORECASE)
    if mf: f = fmt_date(mf.group(1), mf.group(2), mf.group(3))
    return cm, f

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
            else:
                following = m2.group(1).splitlines()
                if len(following) >= 2 and is_name_candidate(following[1]):
                    rep2 = following[1].upper()
    if not rep2:
        for text in text_pages:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            for i, ln in enumerate(lines):
                if re.search(r'Representante\s*2', ln, re.IGNORECASE) and i+1 < len(lines):
                    cand = lines[i+1]
                    if is_name_candidate(cand): rep2 = cand.upper(); break
            if rep2: break
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

def geocode_address(addr):
    if not addr: return ""
    try:
        r = requests.get(NOMINATIM_URL, params={"q": f"{addr}, Chile","format":"json","addressdetails":1,"limit":1}, headers={"User-Agent": USER_AGENT}, timeout=8)
        if r.status_code == 200 and r.json():
            a = r.json()[0].get("address", {})
            city = a.get("city") or a.get("town") or a.get("municipality") or a.get("county") or ""
            return (city or "").upper()
        write_debug(f"Geocode HTTP {r.status_code} for {addr}")
    except Exception as e:
        write_debug(f"Geocode exception: {e} for {addr}")
    return ""

# --------------- Finalize address/comuna (solo si falta comuna) ---------------
def finalize_address_comuna(row):
    dir_val = (row.get("DIRECCION") or "").strip()
    com_val = (row.get("COMUNA") or "").strip().upper()
    if dir_val and (not com_val or com_val == "SANTIAGO"):
        if ',' in dir_val and not is_bank_header_line(dir_val):
            left, right = dir_val.rsplit(',', 1)
            comm = fuzzy_comuna(right)
            if comm and (comm in COMUNAS or len(comm) >= 4):
                row["DIRECCION"] = left.strip().upper()
                row["COMUNA"] = comm
    return row

# --------------- Combine per PDF ---------------
def extract_all_from_text_pages_cc(text_pages, use_geocode=False):
    # 1) identidad del deudor (primaria)
    ident = extract_cc_identity_block(text_pages)

    # 2) demás campos desde páginas (genéricos)
    rows = []
    for text in text_pages:
        op = extract_operation_from_text(text)
        ruts = find_all_ruts(text)
        rut_gen, dv_gen = choose_rut_for_doc(text, ruts) if ruts else ("","")
        nombre_g = extract_nombre_generic(text)
        direccion_h, comuna_h = extract_domicilio_and_comuna(text)
        fecha_sus = parse_spanish_date(text)
        monto_fmt, _ = extract_amount(text)
        f1, fN = parse_first_last_due_dates(text)
        cuotas, monto_cuota, monto_ult = extract_cuotas_and_montos(text)
        tasa = extract_tasa(text)
        cuota_morosa, fecha_cuota_morosa = extract_cuota_morosa(text)
        rows.append({
            "text": text,
            "OPERACIÓN": op, "RUT": rut_gen, "DV": dv_gen,
            "NOMBRE_G": nombre_g, "DIRECCION_H": direccion_h, "COMUNA_H": comuna_h,
            "FECHA_SUSCRIPCION": fecha_sus, "MONTO_CREDITO": monto_fmt,
            "F1": f1, "FN": fN,
            "CUOTAS": cuotas, "MONTO_CUOTA": monto_cuota, "MONTO_ULTIMA_CUOTA": monto_ult, "TASA": tasa,
            "CUOTA_MOROSA": cuota_morosa, "FECHA_CUOTA_MOROSA": fecha_cuota_morosa
        })

    # 3) escoger página base para otros campos
    def score_row_basic(r):
        return (50 if r.get("OPERACIÓN") else 0) + (30 if r.get("RUT") else 0) + (20 if r.get("NOMBRE_G") else 0) + (10 if r.get("MONTO_CREDITO") else 0)
    best = max(rows, key=score_row_basic) if rows else {}
    operation = extract_operation_allpages([r["text"] for r in rows]) or best.get("OPERACIÓN","")

    # 4) fijar identidad (bloque) – NO sobreescribir con encabezado legal
    nombre = ident["name"] or best.get("NOMBRE_G","") or ""
    rut = ident["rut"] or best.get("RUT","") or ""
    dv = ident["dv"] or best.get("DV","") or ""
    direccion = ident["address"]  # si hay identidad, se usa tal cual
    comuna = ident["comuna"]

    # 5) si identidad no aportó, usar heurística (pero filtrando encabezado del banco)
    if not direccion:
        direccion = best.get("DIRECCION_H","")
        if is_bank_header_line(direccion): direccion = ""
    if not comuna:
        comuna = best.get("COMUNA_H","")
        if comuna.upper().startswith("COMUNA DE "): comuna = ""

    # 6) completar desde combinado solo si aún faltan
    if not direccion or not comuna:
        addr2, com2 = extract_domicilio_and_comuna("\n".join([r["text"] for r in rows]))
        if addr2 and not direccion: direccion = addr2.upper()
        if com2 and not comuna: comuna = com2

    # 7) normalización final (no toca identidad válida)
    tmp = {"DIRECCION": direccion, "COMUNA": comuna}
    tmp = finalize_address_comuna(tmp)
    direccion, comuna = tmp["DIRECCION"], tmp["COMUNA"]

    # 8) opcional geocode si comuna aún vacía
    if use_geocode and direccion and not comuna:
        gc = geocode_address(direccion)
        if gc and gc != "SANTIAGO": comuna = gc

    # 9) fechas / montos / tasa
    combined_text = "\n".join([r["text"] for r in rows])
    f1 = best.get("F1",""); fN = best.get("FN","")
    if not f1 or not fN:
        f1c, fNc = parse_first_last_due_dates(combined_text)
        f1 = f1 or f1c; fN = fN or fNc
    cuotas = best.get("CUOTAS",""); monto_cuota = best.get("MONTO_CUOTA",""); monto_ult = best.get("MONTO_ULTIMA_CUOTA",""); tasa = best.get("TASA","")
    if not cuotas or not monto_cuota or not monto_ult:
        c2, mc2, mu2 = extract_cuotas_and_montos(combined_text)
        cuotas = cuotas or c2; monto_cuota = monto_cuota or mc2; monto_ult = monto_ult or mu2
    if not tasa: tasa = extract_tasa(combined_text)

    # 10) representantes
    rep1, rep2 = extract_representantes_allpages([r["text"] for r in rows])

    # 11) fecha suscripción
    fecha_sus = best.get("FECHA_SUSCRIPCION","") or parse_spanish_date(combined_text)

    # 12) monto / capital
    monto = best.get("MONTO_CREDITO","")

    final_row = {
        "OPERACION_1": operation or "",
        "RUT": rut, "DV": dv, "NOMBRE": nombre,
        "DIRECCION": clean_and_fix_address(direccion), 
        "COMUNA": fix_comuna_ocr(comuna),
        "FECHA_SUSCRIPCION_1": fecha_sus,
        "MONTO_CREDITO_1": monto,
        "CUOTAS_1": cuotas, "TASA_1": tasa, "MONTO_CUOTA_1": monto_cuota, "MONTO_ULTIMA_CUOTA_1": monto_ult,
        "FECHA_VENCIMIENTO_1_CUOTA_1": f1,
        "FECHA_VENCIMIENTO_ULTIMA_CUOTA_1": fN,
        "CUOTA_MOROSA_1": best.get("CUOTA_MOROSA",""),
        "FECHA_CUOTA_MOROSA_1": best.get("FECHA_CUOTA_MOROSA",""),
        "CAPITAL_1": monto, 
        "EXHORTO": "TEMUCO",  # Valor por defecto
        "SUCURSAL": "SANTIAGO",  # Valor por defecto
        "PRODUCTO": "CC",
        "NOMBRE_APODERADO": rep1, 
        "NOMBRE_APODERADO_2": rep2
    }
    write_debug("---- COMBINED ROW CC ----")
    for k,v in final_row.items(): write_debug(f"{k}: {v}")
    write_debug("---- END COMBINED ROW CC ----\n")
    return final_row

# --------------- Main ---------------
def main():
    parser = argparse.ArgumentParser(description="Procesar PDFs Itau (CC) -> Excel v5 REAL DATA")
    parser.add_argument("--geocode", action="store_true", help="Intentar geocodificar (Nominatim)")
    args = parser.parse_args()
    use_geocode = args.geocode

    print("🚀 Inicio: proceso Itau CC v5 - EXTRACCIÓN REAL DE PDFs")
    DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEBUG_FILE.unlink(missing_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if not TESSERACT_AVAILABLE:
        print("❌ TESSERACT NO DISPONIBLE - No se puede extraer texto de PDFs")
        print("💡 Instala Tesseract desde: https://github.com/UB-Mannheim/tesseract/wiki")
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
                write_debug(f"--- PAGE OCR CC: {img.name} ---")
                write_debug(txt[:8000])
                text_pages.append(txt)
            
            row = extract_all_from_text_pages_cc(text_pages, use_geocode=use_geocode)
            all_rows.append(row)
            print(f"  ✅ Extraído: RUT {row['RUT']}-{row['DV']}, {row['NOMBRE']}")
            
        except Exception as e:
            print(f"  ❌ ERROR procesando {pdf.name}: {str(e)}")
            write_debug(f"ERROR procesando {pdf.name}: {e}")
        finally:
            try:
                if ri_folder.exists(): shutil.rmtree(ri_folder)
            except Exception as e:
                write_debug(f"WARNING cleanup {ri_folder}: {e}")

    if all_rows:
        df_new = pd.DataFrame(all_rows, columns=COLUMNS)
        
        # Aplicar correcciones de referencia si están disponibles
        if GEO_UTILS_AVAILABLE:
            print("📋 Aplicando correcciones de referencia...")
            df_corrected = apply_reference_corrections(df_new)
            corrected_count = sum(1 for i in range(len(df_new)) 
                                if df_new.iloc[i].to_dict() != df_corrected.iloc[i].to_dict())
            if corrected_count > 0:
                print(f"✅ Aplicadas {corrected_count} correcciones de referencia")
                df_new = df_corrected
        
        df_new.to_excel(OUT_XLSX, index=False)
        print(f"✅ Guardado final en: {OUT_XLSX}")
        print(f"📋 Debug info en: {DEBUG_FILE}")
        print(f"📊 Filas extraídas: {len(all_rows)}")
        
        # Mostrar resumen de datos extraídos
        print("\n📄 RESUMEN DE DATOS EXTRAÍDOS:")
        for i, row in df_new.iterrows():
            print(f"  Fila {i+1}: {row['NOMBRE']} (RUT: {row['RUT']}-{row['DV']}) - {row['COMUNA']}")
    else:
        print("❌ No se extrajeron filas. Revisa", DEBUG_FILE)

if __name__ == "__main__":
    main()