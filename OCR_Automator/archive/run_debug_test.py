#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de prueba con debug para el sistema OCR Automator.
Ejecuta el proceso completo con debug detallado habilitado.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_ocr_with_debug():
    """Ejecuta el OCR con debug habilitado."""
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    print("🔧 Iniciando OCR con debug detallado...")
    print("=" * 60)
    
    # Verificar que hay PDFs
    pdf_dir = script_dir / "pdfs" / "Itau"
    if not pdf_dir.exists() or not any(pdf_dir.glob("*.pdf")):
        print("❌ No se encontraron PDFs en pdfs/Itau/")
        return False
    
    pdfs = list(pdf_dir.glob("*.pdf"))
    print(f"📄 PDFs encontrados: {len(pdfs)}")
    for pdf in pdfs:
        print(f"   - {pdf.name}")
    
    print("\n" + "=" * 60)
    
    # Ejecutar OCR con debug
    python_exe = sys.executable
    ocr_command = [
        python_exe,
        "ocr_to_csv.py",
        "--client", "Itau",
        "--pdfs-dir", "pdfs/Itau",
        "--output", "debug_extraction.csv",
        "--debug",
        "--verbose"
    ]
    
    print("🚀 Ejecutando comando OCR:")
    print(" ".join(ocr_command))
    print("\n" + "=" * 60)
    
    try:
        result = subprocess.run(ocr_command, check=True)
        print("\n" + "=" * 60)
        print("✅ OCR completado exitosamente!")
        
        # Verificar archivos generados
        csv_file = script_dir / "debug_extraction.csv"
        debug_dir = script_dir / "debug_output"
        
        if csv_file.exists():
            print(f"📊 CSV generado: {csv_file}")
            
        if debug_dir.exists():
            debug_files = list(debug_dir.glob("*"))
            print(f"🔧 Archivos de debug generados: {len(debug_files)}")
            for debug_file in debug_files:
                print(f"   - {debug_file.name}")
                
            # Buscar reporte HTML
            html_reports = list(debug_dir.glob("debug_report_*.html"))
            if html_reports:
                print(f"\n🌐 Reporte HTML disponible: {html_reports[0]}")
                print("💡 Abre este archivo en tu navegador para ver el debug detallado")
        
        print("\n" + "=" * 60)
        print("🎯 Próximos pasos:")
        print("1. Revisa el reporte HTML para ver la extracción OCR paso a paso")
        print("2. Verifica los datos extraídos en debug_extraction.csv")
        print("3. Ejecuta el procesador: python process_itau_auto_v2.py --input debug_extraction.csv --debug")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando OCR: {e}")
        return False
    except KeyboardInterrupt:
        print("\n⏹️ Proceso interrumpido por el usuario")
        return False

def run_processing_with_debug():
    """Ejecuta el procesamiento con debug habilitado."""
    script_dir = Path(__file__).parent
    csv_file = script_dir / "debug_extraction.csv"
    
    if not csv_file.exists():
        print("❌ No se encontró debug_extraction.csv. Ejecuta primero el OCR.")
        return False
    
    print("\n🔄 Iniciando procesamiento con debug...")
    print("=" * 60)
    
    python_exe = sys.executable
    process_command = [
        python_exe,
        "process_itau_auto_v2.py",
        "--input", "debug_extraction.csv",
        "--output", "DEBUG_FINAL_RESULT.xlsx",
        "--report", "debug_processing_report.md",
        "-vv"
    ]
    
    print("🚀 Ejecutando comando de procesamiento:")
    print(" ".join(process_command))
    print("\n" + "=" * 60)
    
    try:
        result = subprocess.run(process_command, check=True)
        print("\n" + "=" * 60)
        print("✅ Procesamiento completado exitosamente!")
        
        # Verificar archivos generados
        excel_file = script_dir / "DEBUG_FINAL_RESULT.xlsx"
        report_file = script_dir / "debug_processing_report.md"
        
        if excel_file.exists():
            print(f"📊 Excel final: {excel_file}")
            
        if report_file.exists():
            print(f"📄 Reporte de procesamiento: {report_file}")
        
        print("\n🎉 ¡Proceso completo terminado!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error ejecutando procesamiento: {e}")
        return False

def main():
    """Función principal del script de debug."""
    print("🔧 SISTEMA DE DEBUG - OCR AUTOMATOR")
    print("=" * 60)
    print("Este script ejecuta el proceso completo con debug detallado")
    print("para que puedas ver exactamente qué está leyendo el OCR.")
    print("=" * 60)
    
    # Paso 1: OCR con debug
    if not run_ocr_with_debug():
        print("❌ Falló el paso de OCR. Abortando.")
        sys.exit(1)
    
    print("\n" + "🔄" * 20)
    input("Presiona Enter para continuar con el procesamiento...")
    
    # Paso 2: Procesamiento con debug
    if not run_processing_with_debug():
        print("❌ Falló el paso de procesamiento.")
        sys.exit(1)
    
    print("\n" + "🎉" * 20)
    print("¡DEBUG COMPLETO TERMINADO!")
    print("Revisa los archivos generados para analizar el proceso.")

if __name__ == "__main__":
    main()