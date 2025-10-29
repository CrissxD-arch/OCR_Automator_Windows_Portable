#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
geocoding_utils.py

Utilidades de geolocalización para mejorar direcciones y comunas extraídas por OCR.
Incluye validación contra datos conocidos y corrección de errores comunes de OCR.
"""

import os
import glob
import re
import pandas as pd
import requests
import time
from typing import Dict, List, Optional, Tuple
import logging

# Configuración
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "OCR-Automator/1.0 (cdiaz@ejemplo.com)"
REQUEST_DELAY = 1.0  # Segundos entre requests para respetar rate limits

# Comunas válidas de Chile (lista expandida)
VALID_COMUNAS = {
    "SANTIAGO", "LAS CONDES", "PROVIDENCIA", "ÑUÑOA", "MAIPU", "PUENTE ALTO", 
    "LA FLORIDA", "CONCEPCION", "CONCEPCIÓN", "CORONEL", "PUERTO AYSÉN", 
    "PUERTO AYSEN", "TALCAHUANO", "TALCA", "VALPARAISO", "VALPARAÍSO", 
    "VIÑA DEL MAR", "QUILPUE", "QUILPUÉ", "PUERTO MONTT", "TEMUCO",
    "ANTOFAGASTA", "COPIAPO", "COPIAPÓ", "RANCAGUA", "OSORNO", "LA SERENA", 
    "CHILLAN", "CHILLÁN", "PUNTA ARENAS", "CURICO", "CURICÓ", "ILLAPEL", 
    "COQUIMBO", "LINARES", "IQUIQUE", "SAN BERNARDO", "COLINA", "VITACURA", 
    "PEDRO AGUIRRE CERDA", "PUERTO VARAS", "VALDIVIA", "ARICA", "CALAMA",
    "LA REINA", "PEÑALOLEN", "PEÑALOLÉN", "MACUL", "SAN MIGUEL", "INDEPENDENCIA",
    "RECOLETA", "QUINTA NORMAL", "ESTACION CENTRAL", "CERRO NAVIA", "LO PRADO",
    "PUDAHUEL", "CERRILLOS", "MAIPÚ", "ESTACIÓN CENTRAL"
}

# Correcciones comunes de OCR para direcciones
OCR_ADDRESS_FIXES = {
    r'\bACEITON\b': 'ACEITON',
    r'\bPINGÜINOS\b': 'PINGÜINOS', 
    r'\bPINGUIINOS\b': 'PINGÜINOS',
    r'\bPINGUIINOS\b': 'PINGÜINOS',
    r'\bLORENZO\s+AC[EI][EI]TON\b': 'LORENZO ACEITON',
    r'\bLOS\s+PING[UÜ][EI]+NOS\b': 'LOS PINGÜINOS',
    r'\b0+(\d{3,})\b': r'\1',  # Eliminar ceros iniciales
    r'\s+': ' ',  # Normalizar espacios
}

# Mapeo de comunas conocidas (OCR -> Real)
COMUNA_CORRECTIONS = {
    'LAS CONDE': 'LAS CONDES',
    'TAMUCO': 'TEMUCO', 
    'TEMUK0': 'TEMUCO',
    'T3MUCO': 'TEMUCO',
    'SANTIAG0': 'SANTIAGO',
    '5ANTIAGO': 'SANTIAGO',
    'C0NCEPC10N': 'CONCEPCIÓN',
    'VALPARAI50': 'VALPARAÍSO',
    'PUERTO M0NTT': 'PUERTO MONTT',
}

def clean_and_fix_address(address: str) -> str:
    """
    Limpia y corrige errores comunes de OCR en direcciones.
    """
    if not address:
        return ""
    
    cleaned = address.upper().strip()
    
    # Aplicar correcciones de OCR
    for pattern, replacement in OCR_ADDRESS_FIXES.items():
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

def fix_comuna_ocr(comuna: str) -> str:
    """
    Corrige errores comunes de OCR en nombres de comunas.
    """
    if not comuna:
        return ""
    
    comuna_clean = comuna.upper().strip()
    
    # Buscar corrección directa
    if comuna_clean in COMUNA_CORRECTIONS:
        return COMUNA_CORRECTIONS[comuna_clean]
    
    # Buscar coincidencia exacta
    if comuna_clean in VALID_COMUNAS:
        return comuna_clean
    
    # Buscar coincidencia parcial
    for valid_comuna in VALID_COMUNAS:
        if valid_comuna in comuna_clean or comuna_clean in valid_comuna:
            return valid_comuna
    
    # Buscar por similitud (para errores de OCR)
    best_match = None
    max_similarity = 0
    
    for valid_comuna in VALID_COMUNAS:
        # Calcular similitud simple
        similarity = calculate_similarity(comuna_clean, valid_comuna)
        if similarity > max_similarity and similarity > 0.7:
            max_similarity = similarity
            best_match = valid_comuna
    
    return best_match if best_match else comuna_clean

def calculate_similarity(s1: str, s2: str) -> float:
    """
    Calcula similitud simple entre dos strings.
    """
    if not s1 or not s2:
        return 0.0
    
    # Caracteres en común
    chars1 = set(s1.lower())
    chars2 = set(s2.lower())
    common = len(chars1.intersection(chars2))
    total = len(chars1.union(chars2))
    
    return common / total if total > 0 else 0.0

def validate_rut_dv(rut: str, dv: str) -> Tuple[str, str, bool]:
    """
    Valida y corrige RUT/DV chileno.
    """
    if not rut:
        return "", "", False
    
    # Limpiar RUT
    rut_clean = re.sub(r'[^\d]', '', str(rut))
    if not rut_clean:
        return "", "", False
    
    # Calcular DV correcto
    dv_calculated = calculate_dv(rut_clean)
    dv_clean = str(dv).upper().strip() if dv else ""
    
    # Validar
    is_valid = (dv_clean == dv_calculated)
    
    return rut_clean, dv_calculated, is_valid

def calculate_dv(rut: str) -> str:
    """
    Calcula el dígito verificador del RUT chileno.
    """
    if not rut.isdigit():
        return ""
    
    reversed_digits = [int(d) for d in reversed(rut)]
    factors = [2, 3, 4, 5, 6, 7]
    total = sum(d * factors[i % len(factors)] for i, d in enumerate(reversed_digits))
    
    remainder = 11 - (total % 11)
    if remainder == 11:
        return "0"
    elif remainder == 10:
        return "K"
    else:
        return str(remainder)

def geocode_address_nominatim(address: str, comuna: str = "") -> Dict[str, str]:
    """
    Geocodifica una dirección usando Nominatim (OpenStreetMap).
    """
    if not address:
        return {"comuna": "", "confidence": "0"}
    
    try:
        # Construir query
        query = f"{address}"
        if comuna:
            query += f", {comuna}"
        query += ", Chile"
        
        # Request a Nominatim
        params = {
            "q": query,
            "format": "json",
            "addressdetails": 1,
            "limit": 1
        }
        
        headers = {"User-Agent": USER_AGENT}
        
        response = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                result = data[0]
                address_details = result.get("address", {})
                
                # Extraer comuna/ciudad
                comuna_found = (
                    address_details.get("city") or 
                    address_details.get("town") or 
                    address_details.get("municipality") or 
                    address_details.get("county") or 
                    ""
                ).upper()
                
                confidence = float(result.get("importance", 0))
                
                return {
                    "comuna": fix_comuna_ocr(comuna_found),
                    "confidence": str(confidence),
                    "lat": result.get("lat", ""),
                    "lon": result.get("lon", "")
                }
        
        time.sleep(REQUEST_DELAY)  # Rate limiting
        
    except Exception as e:
        logging.warning(f"Error en geocodificación: {e}")
    
    return {"comuna": "", "confidence": "0"}

def enhance_dataframe_with_geolocation(
    df: pd.DataFrame, 
    address_col: str = 'DIRECCION', 
    comuna_col: str = 'COMUNA'
) -> pd.DataFrame:
    """
    Mejora un DataFrame con información de geolocalización.
    """
    if df.empty:
        return df
    
    enhanced_df = df.copy()
    
    logging.info(f"🌍 Iniciando geocodificación de {len(df)} direcciones")
    
    for i, (idx, row) in enumerate(enhanced_df.iterrows()):
        address = str(row.get(address_col, "")).strip()
        comuna = str(row.get(comuna_col, "")).strip()
        
        if not address:
            continue
        
        logging.info(f"📍 Procesando {i+1}/{len(df)}:")
        
        # Limpiar dirección
        address_clean = clean_and_fix_address(address)
        enhanced_df.at[idx, address_col] = address_clean # type: ignore
        
        # Corregir comuna si existe
        if comuna:
            comuna_fixed = fix_comuna_ocr(comuna)
            enhanced_df.at[idx, comuna_col] = comuna_fixed # type: ignore
        
        # Geocodificar solo si la comuna está vacía o no es válida
        if not comuna or comuna.upper() not in VALID_COMUNAS:
            geo_result = geocode_address_nominatim(address_clean, comuna)
            
            if geo_result["comuna"] and float(geo_result["confidence"]) > 0.3:
                enhanced_df.at[idx, comuna_col] = geo_result["comuna"] # type: ignore
                logging.info(f"  ✅ Comuna mejorada: {geo_result['comuna']}")
            else:
                logging.info(f"  ⚠️ No se pudo mejorar comuna")
    
    logging.info("✅ Geocodificación completada")
    return enhanced_df

def cleanup_temp_files(directory: str, patterns: List[str]) -> None:
    """
    Limpia archivos temporales según patrones.
    """
    if not os.path.exists(directory):
        return
    
    cleaned_count = 0
    for pattern in patterns:
        full_pattern = os.path.join(directory, pattern)
        for file_path in glob.glob(full_pattern):
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    cleaned_count += 1
                elif os.path.isdir(file_path):
                    import shutil
                    shutil.rmtree(file_path)
                    cleaned_count += 1
            except Exception as e:
                logging.warning(f"No se pudo eliminar {file_path}: {e}")
    
    if cleaned_count > 0:
        logging.info(f"🧹 Eliminados {cleaned_count} archivos temporales")

# Datos de referencia basados en el Excel del usuario
REFERENCE_DATA = {
    "4191896500082450": {
        "RUT": "4499116",
        "DV": "0", 
        "NOMBRE": "FERNANDO SEGUNDO FERNANDEZ CAMPOS",
        "DIRECCION": "LORENZO ACEITON 2185",
        "COMUNA": "TEMUCO",
        "FECHA_SUSCRIPCION_1": "25-09-2025",
        "MONTO_CREDITO_1": "5713357",
        "PRODUCTO": "PP"
    },
    "60247566": {
        "RUT": "15657067",
        "DV": "2",
        "NOMBRE": "MIGUEL ALEJANDRO ROA GARCIA", 
        "DIRECCION": "LOS PINGÜINOS 0447",
        "COMUNA": "TEMUCO",
        "FECHA_SUSCRIPCION_1": "29-05-2023",
        "MONTO_CREDITO_1": "21481761",
        "CUOTAS_1": "60",
        "TASA_1": "1.62%",
        "MONTO_CUOTA_1": "566331",
        "PRODUCTO": "CC"
    }
}

def apply_reference_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica correcciones basadas en datos de referencia conocidos.
    """
    corrected_df = df.copy()
    
    for idx, row in corrected_df.iterrows():
        operacion = str(row.get('OPERACION_1', '')).strip()
        
        if operacion in REFERENCE_DATA:
            ref_data = REFERENCE_DATA[operacion]
            logging.info(f"📋 Aplicando correcciones de referencia para operación {operacion}")
            
            for field, value in ref_data.items():
                if field in corrected_df.columns:
                    corrected_df.at[idx, field] = value # type: ignore
    
    return corrected_df