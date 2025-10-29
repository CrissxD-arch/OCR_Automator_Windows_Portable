#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script simple para probar el debug - solo genera debug.txt
"""

import sys
import os
from pathlib import Path

# Agregar directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    """Ejecuta OCR con debug simple."""
    print("🔧 Iniciando debug simple...")
    
    try:
        # Ejecutar OCR con debug
        os.system('python ocr_to_csv.py --client Itau --pdfs-dir pdfs/Itau --debug --verbose')
        
        # Ejecutar procesamiento
        os.system('python process_itau_auto_v2.py --input Itau_results_ALL.csv --format excel -vv')
        
        print("\n✅ Debug completado!")
        print("📂 Revisa la carpeta debug_output/ para el archivo debug_XXXXX.txt")
        print("📊 Excel generado en outputs/Itau/")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()