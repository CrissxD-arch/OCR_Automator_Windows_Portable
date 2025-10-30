#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_indisa_unified_v1.py

Procesador simple para Cliente Indisa / Cheques.
- Convierte PDF a imágenes con pdf2image
- OCR con Tesseract (spa)
- Extrae campos básicos (RUT, DV, NOMBRE, MONTO, FECHA) de forma robusta pero genérica
- Produce un Excel por ejecución y un archivo de debug con el texto OCR

Salida:
  outputs/Indisa/web/Indisa_results_UNIFIED_YYYYmmdd_HHMMSS.xlsx
  outputs/Indisa/web/Indisa_debug_unified_YYYYmmdd_HHMMSS.txt

Nota: Este es un punto de partida. Con muestras reales de cheques Indisa
podemos enriquecer reglas (serie, banco, cuenta, plaza, etc.).
"""

from __future__ import annotations
import re
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Tuple

import pandas as pd
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Utilidades opcionales (geocoding, validación RUT)
try:
    from geocoding_utils import (
        clean_and_fix_address,
        fix_comuna_ocr,
        apply_reference_corrections,
        validate_rut_dv,
    )
    GEO_UTILS_AVAILABLE = True
except Exception:
    GEO_UTILS_AVAILABLE = False
    def clean_and_fix_address(address): return address
    def fix_comuna_ocr(comuna): return comuna
    def apply_reference_corrections(df): return df
    def validate_rut_dv(rut: str, dv: str) -> Tuple[str, str, bool]: return rut, dv, True

# ---------------- CONFIG ----------------
TESSERACT_EXE = r"C:\Users\cdiaz\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
POPPLER_BIN = r"C:\poppler\Library\bin"
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR
TEMP_RI_ROOT = PROJECT_ROOT / "RI_Indisa"
OUT_DIR = PROJECT_ROOT / "outputs" / "Indisa"
# Valores locales por compatibilidad CLI (poco usados en web)
DEBUG_FILE = OUT_DIR / "Indisa_debug_unified.txt"
# ----------------------------------------

# Verificar Tesseract (no falla si no está, solo marca bandera)
try:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
    _test_img = Image.new('RGB', (40, 20), color='white')
    pytesseract.image_to_string(_test_img, lang='spa')
    TESSERACT_AVAILABLE = True
except Exception:
    TESSERACT_AVAILABLE = False

UNIFIED_COLUMNS = [
    # Reutilizamos columnas estándar para mantener consistencia de reportes
    "OPERACION_1","RUT","DV","NOMBRE","DIRECCION","COMUNA",
    "FECHA_SUSCRIPCION_1","MONTO_CREDITO_1","CUOTAS_1","TASA_1","MONTO_CUOTA_1","MONTO_ULTIMA_CUOTA_1",
    "FECHA_VENCIMIENTO_1_CUOTA_1","FECHA_VENCIMIENTO_ULTIMA_CUOTA_1",
    "CUOTA_MOROSA_1","FECHA_CUOTA_MOROSA_1",
    "CAPITAL_1","EXHORTO","SUCURSAL","PRODUCTO","NOMBRE_APODERADO","NOMBRE_APODERADO_2"
]

# --------------- Debug helper ---------------
def write_debug(s: str):
    try:
        DEBUG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DEBUG_FILE, "a", encoding="utf-8") as f:
            f.write(s + "\n")
    except Exception:
        pass

# --------------- OCR helpers ---------------
def convert_pdf_to_images(pdf_path: Path, out_dir: Path, poppler_bin: str, dpi: int = 200) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    images = convert_from_path(str(pdf_path), dpi=dpi, poppler_path=poppler_bin)
    saved = []
    for i, img in enumerate(images, start=1):
        p = out_dir / f"page_{i:02d}.png"
        img.save(p)
        saved.append(p)
    return saved


def ocr_image_to_text(img_path: Path) -> str:
    try:
        img = Image.open(img_path)
        txt = pytesseract.image_to_string(img, lang="spa")
        return txt
    except Exception as e:
        return f"[OCR_ERROR] {e}"

# --------------- Parsers (genéricos para cheques) ---------------
RUT_PATTERNS = [
    r"\bRUT\b[^\d]{0,10}[:\sNNoº°]*([\d\.]{6,})\s*[-–—]?\s*([0-9Kk])",
    r"\b(\d{7,8})\s*[-\s–—]*([0-9Kk])\b",
]

MONEY_PATTERNS = [
    r"\$\s*([0-9\.]{3,})",
    r"\bMONTO\s*[:\-]?\s*\$?\s*([0-9\.]{3,})",
]

DATE_PATTERNS = [
    r"\b(\d{1,2})[\/-](\d{1,2})[\/-](\d{2,4})\b",
]


def parse_rut(text: str) -> tuple[str, str]:
    for pat in RUT_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            rut_raw = re.sub(r"[^\d]", "", m.group(1))
            dv_raw = m.group(2).upper()
            rut_ok, dv_ok, valid = validate_rut_dv(rut_raw, dv_raw)
            # Si DV OCR no calza, igual aceptamos el RUT y devolvemos DV calculado para robustez
            if rut_ok:
                return rut_ok, dv_ok
    return "", ""


def parse_monto(text: str) -> str:
    # 1) Con símbolo $ o etiqueta MONTO
    for pat in MONEY_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            num = m.group(1).replace(".", "")
            try:
                return f"{int(num):,}".replace(",", ".")
            except Exception:
                return m.group(1)
    # 2) Fallback: número con miles (p.ej., 182.000) sin etiqueta
    cands = re.findall(r"(?<!\d)([1-9]\d{0,2}(?:\.\d{3})+)(?!\d)", text)
    if cands:
        # Heurística: tomar el último (suele ser el monto) o el mayor
        try:
            val = max(cands, key=lambda s: int(s.replace('.', '')))
        except Exception:
            val = cands[-1]
        return val
    return ""


def parse_fecha(text: str) -> str:
    for pat in DATE_PATTERNS:
        m = re.search(pat, text)
        if m:
            d, mth, y = m.group(1), m.group(2), m.group(3)
            try:
                y = int(y)
                if y < 100: y += 2000
                dt = datetime(int(y), int(mth), int(d))
                return dt.strftime("%d-%m-%Y")
            except Exception:
                continue
    return ""


def extract_name_guess(text: str) -> str:
    # Heurística básica: línea cerca de RUT, en mayúsculas, sin muchos dígitos
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    best = ""
    for i, ln in enumerate(lines):
        if re.search(r"RUT|C[IÍ]DULA|CEDULA", ln, re.IGNORECASE):
            # Mirar línea previa y siguiente
            for j in (i-1, i+1):
                if 0 <= j < len(lines):
                    cand = re.sub(r"[^A-ZÁÉÍÓÚÑ\s]", "", lines[j].upper()).strip()
                    if cand and len(cand.split()) >= 2 and len(cand) <= 60:
                        return cand
    # Fallback: primera línea en mayúsculas razonable
    for ln in lines[:10]:
        cand = re.sub(r"[^A-ZÁÉÍÓÚÑ\s]", "", ln.upper()).strip()
        if cand and len(cand.split()) >= 2 and len(cand) <= 60:
            best = cand
            break
    return best


# --------------- Core ---------------
def process_single_pdf(pdf_path: Path, ri_root: Path, dpi: int) -> dict:
    ri_folder = ri_root / pdf_path.stem
    text_pages: list[str] = []
    try:
        images = convert_pdf_to_images(pdf_path, ri_folder, POPPLER_BIN, dpi=dpi)
        for img in images:
            txt = ocr_image_to_text(img)
            write_debug(f"--- PAGE OCR: {img.name} ---")
            write_debug(txt[:8000])
            text_pages.append(txt)
        joined = "\n".join(text_pages)
        rut, dv = parse_rut(joined)
        monto = parse_monto(joined)
        fecha = parse_fecha(joined)
        nombre = extract_name_guess(joined)
        # Armar fila compatible con reporte unificado
        row = {
            "OPERACION_1": re.findall(r"(\d{6,})", pdf_path.stem)[0] if re.search(r"\d{6,}", pdf_path.stem) else "",
            "RUT": rut,
            "DV": dv,
            "NOMBRE": nombre,
            "DIRECCION": "",
            "COMUNA": "",
            "FECHA_SUSCRIPCION_1": fecha,
            "MONTO_CREDITO_1": monto,
            "CUOTAS_1": "",
            "TASA_1": "",
            "MONTO_CUOTA_1": "",
            "MONTO_ULTIMA_CUOTA_1": "",
            "FECHA_VENCIMIENTO_1_CUOTA_1": "",
            "FECHA_VENCIMIENTO_ULTIMA_CUOTA_1": "",
            "CUOTA_MOROSA_1": "",
            "FECHA_CUOTA_MOROSA_1": "",
            "CAPITAL_1": monto,
            "EXHORTO": "",
            "SUCURSAL": "",
            "PRODUCTO": "CHEQUE",
            "NOMBRE_APODERADO": "",
            "NOMBRE_APODERADO_2": "",
        }
        return row
    finally:
        try:
            if ri_folder.exists(): shutil.rmtree(ri_folder)
        except Exception:
            pass


# --------------- Public API ---------------
def process_pdf_files(pdf_paths: List[str], geocode: bool = False, output_dir: str | None = None, fast: bool = False, dpi: int | None = None) -> tuple[str, str]:
    """
    Procesa lista de PDFs de cheques Indisa. Devuelve (excel_path, debug_path).
    """
    out_base = Path(output_dir) if output_dir else (OUT_DIR / "web")
    out_base.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    xlsx_path = out_base / f"Indisa_results_UNIFIED_{ts}.xlsx"
    debug_path = out_base / f"Indisa_debug_unified_{ts}.txt"
    ri_root = TEMP_RI_ROOT / f"web_{ts}"

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

        rows = []
        dpi_val = dpi if dpi is not None else (150 if fast else 200)
        for p in pdf_paths:
            pth = Path(p)
            if not pth.exists():
                write_debug(f"WARN: PDF no existe -> {p}")
                continue
            try:
                row = process_single_pdf(pth, ri_root, dpi=dpi_val)
                rows.append(row)
            except Exception as e:
                write_debug(f"ERROR procesando {pth.name}: {e}")

        if not rows:
            pd.DataFrame(columns=UNIFIED_COLUMNS).to_excel(xlsx_path, index=False)
            return str(xlsx_path), str(debug_path)

        df = pd.DataFrame(rows, columns=UNIFIED_COLUMNS)
        if GEO_UTILS_AVAILABLE and geocode:
            df = apply_reference_corrections(df)

        # Breve verificador
        miss = {k: 0 for k in ["RUT","DV","NOMBRE","MONTO_CREDITO_1"]}
        for _, r in df.iterrows():
            for k in miss:
                if not str(r.get(k, "")).strip():
                    miss[k] += 1
        write_debug("\n==== VERIFICADOR DE CAMPOS (Indisa) ====")
        for k, v in miss.items():
            write_debug(f"Faltantes {k}: {v}")
        write_debug("========================================\n")

        df.to_excel(xlsx_path, index=False)
        return str(xlsx_path), str(debug_path)
    finally:
        DEBUG_FILE = prev_debug
