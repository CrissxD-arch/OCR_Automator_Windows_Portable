#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Verificador del sistema OCR Automator
Comprueba que todo esté listo para funcionar
"""

import sys
import importlib
import subprocess
from pathlib import Path

def check_python_version():
    """Verifica la versión de Python"""
    version = sys.version_info
    print(f"🐍 Python: {version.major}.{version.minor}.{version.micro}")
    if version.major >= 3 and version.minor >= 8:
        return True, "✅ Versión compatible"
    else:
        return False, "❌ Requiere Python 3.8+"

def check_dependencies():
    """Verifica las dependencias principales"""
    deps = {
        'pytesseract': 'OCR engine',
        'pdf2image': 'PDF conversion', 
        'pandas': 'Data processing',
        'openpyxl': 'Excel generation',
        'PIL': 'Image processing'
    }
    
    results = {}
    for dep, desc in deps.items():
        try:
            if dep == 'PIL':
                importlib.import_module('PIL')
            else:
                importlib.import_module(dep)
            results[dep] = (True, f"✅ {desc}")
        except ImportError:
            results[dep] = (False, f"❌ {desc} - No instalado")
    
    return results

def check_tesseract():
    """Verifica Tesseract OCR"""
    try:
        result = subprocess.run(['tesseract', '--version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\\n')[0]
            return True, f"✅ {version_line}"
        else:
            return False, "❌ Tesseract no funciona"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, "❌ Tesseract no instalado"

def check_project_structure():
    """Verifica la estructura del proyecto"""
    base_dir = Path(__file__).parent
    required_files = [
        'pipeline_completo.py',
        'ocr_to_csv.py', 
        'process_itau_auto_v2.py',
        'config/Itau.json'
    ]
    
    results = {}
    for file_path in required_files:
        full_path = base_dir / file_path
        if full_path.exists():
            results[file_path] = (True, "✅ Encontrado")
        else:
            results[file_path] = (False, "❌ Faltante")
    
    # Verificar carpeta de PDFs
    pdf_dir = base_dir / "pdfs" / "Itau"
    if pdf_dir.exists():
        pdf_count = len(list(pdf_dir.glob("*.pdf")))
        results["pdfs/Itau/"] = (True, f"✅ {pdf_count} PDFs encontrados")
    else:
        results["pdfs/Itau/"] = (False, "❌ Carpeta no existe")
    
    return results

def main():
    print("🔍 OCR Automator - Verificación del Sistema")
    print("=" * 55)
    
    # Verificar Python
    py_ok, py_msg = check_python_version()
    print(f"\\n{py_msg}")
    
    # Verificar dependencias
    print("\\n📦 Dependencias:")
    deps = check_dependencies()
    all_deps_ok = True
    for dep, (ok, msg) in deps.items():
        print(f"   {msg}")
        if not ok:
            all_deps_ok = False
    
    # Verificar Tesseract
    print("\\n🔍 OCR Engine:")
    tess_ok, tess_msg = check_tesseract()
    print(f"   {tess_msg}")
    
    # Verificar estructura
    print("\\n📁 Estructura del proyecto:")
    structure = check_project_structure()
    all_files_ok = True
    for file_path, (ok, msg) in structure.items():
        print(f"   {file_path}: {msg}")
        if not ok:
            all_files_ok = False
    
    # Resumen final
    print("\\n" + "=" * 55)
    if py_ok and all_deps_ok and tess_ok and all_files_ok:
        print("🎉 ¡TODO LISTO! El sistema está preparado para funcionar.")
        print("\\n💡 Para empezar:")
        print("   1. Pon PDFs en pdfs/Itau/")
        print("   2. Presiona F5 en VS Code")
        print("   3. ¡Automatización completa!")
    else:
        print("⚠️  Hay problemas que resolver:")
        if not py_ok:
            print("   - Actualizar Python")
        if not all_deps_ok:
            print("   - Instalar dependencias: pip install -r requirements.txt")
        if not tess_ok:
            print("   - Instalar Tesseract OCR")
        if not all_files_ok:
            print("   - Verificar archivos del proyecto")
    
    print("\\n🆘 Para ayuda rápida: python OCR_Automator/ayuda.py")

if __name__ == "__main__":
    main()