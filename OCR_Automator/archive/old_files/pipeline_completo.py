#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline completo: PDF → CSV → Excel limpio
Ejecuta todo el proceso de automatización en secuencia:
1. OCR de PDFs → CSV
2. Limpieza de CSV → Excel formateado
"""

import subprocess
import sys
from pathlib import Path
import argparse

def run_command(command, description):
    """Ejecuta un comando y maneja errores."""
    print(f"\\n🔄 {description}...")
    print(f"💻 Ejecutando: {' '.join(command)}")
    
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        print("✅ Completado exitosamente")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Error: {e}")
        if e.stdout:
            print(f"Salida: {e.stdout}")
        if e.stderr:
            print(f"Error: {e.stderr}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Pipeline completo PDF → Excel")
    parser.add_argument("--client", default="Itau", help="Cliente (por defecto: Itau)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Modo verboso")
    
    args = parser.parse_args()
    
    # Configurar rutas
    script_dir = Path(__file__).parent
    python_path = sys.executable  # Usar el Python actual
    ocr_script = script_dir / "ocr_to_csv.py"
    cleanup_script = script_dir / "process_itau_auto_v2.py"
    
    print("🚀 Iniciando pipeline completo PDF → Excel")
    print("=" * 50)
    
    # Paso 1: OCR de PDFs a CSV
    ocr_command = [str(python_path), str(ocr_script), "--client", args.client]
    if args.verbose:
        ocr_command.append("-v")
    
    if not run_command(ocr_command, "Extrayendo datos de PDFs con OCR"):
        print("❌ Falló la extracción OCR")
        sys.exit(1)
    
    # Paso 2: Limpieza de CSV a Excel
    csv_file = script_dir / "Itau_results_ALL.csv"
    if not csv_file.exists():
        print(f"❌ No se encontró el archivo CSV: {csv_file}")
        sys.exit(1)
    
    cleanup_command = [str(python_path), str(cleanup_script), "--input", str(csv_file)]
    if args.verbose:
        cleanup_command.extend(["-vv"])
    
    if not run_command(cleanup_command, "Limpiando datos y generando Excel"):
        print("❌ Falló la limpieza de datos")
        sys.exit(1)
    
    # Verificar archivos generados
    excel_file = script_dir / "Itau_results_ALL.cleaned.xlsx"
    report_file = script_dir / "fix_report.md"
    
    print("\\n" + "=" * 50)
    print("🎉 ¡Pipeline completado exitosamente!")
    print("=" * 50)
    
    if excel_file.exists():
        print(f"📊 Excel generado: {excel_file}")
        print(f"📏 Tamaño: {excel_file.stat().st_size / 1024:.1f} KB")
    
    if report_file.exists():
        print(f"📄 Reporte: {report_file}")
    
    print("\\n💡 Para descargar el Excel:")
    print("1. En VS Code, navega al archivo en el explorador")
    print("2. Clic derecho → Download")
    print("3. O copia el archivo a la raíz del proyecto")
    
    print("\\n🎯 ¡Listo para usar!")

if __name__ == "__main__":
    main()