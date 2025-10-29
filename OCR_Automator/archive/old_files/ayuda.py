#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ayuda rápida para OCR Automator
Muestra comandos útiles y estado del sistema
"""

import os
from pathlib import Path

def main():
    print("🚀 OCR Automator - Ayuda Rápida")
    print("=" * 50)
    
    # Verificar estructura
    base_dir = Path(__file__).parent
    pdf_dir = base_dir / "pdfs" / "Itau"
    
    print("\\n📁 Estructura del proyecto:")
    print(f"   📄 PDFs: {pdf_dir}")
    print(f"   ⚙️  Config: {base_dir / 'config' / 'Itau.json'}")
    print(f"   🔧 Scripts: {base_dir}")
    
    # Contar PDFs
    if pdf_dir.exists():
        pdf_count = len(list(pdf_dir.glob("*.pdf")))
        print(f"\\n📊 PDFs encontrados: {pdf_count}")
        if pdf_count == 0:
            print("   ⚠️  Coloca tus archivos PDF en la carpeta pdfs/Itau/")
    else:
        print("\\n❌ Carpeta de PDFs no existe")
    
    print("\\n🎯 Comandos disponibles:")
    print("\\n1. 🔄 Proceso completo (PDF → Excel):")
    print("   python pipeline_completo.py --client Itau -v")
    
    print("\\n2. 📄 Solo extracción OCR (PDF → CSV):")
    print("   python ocr_to_csv.py --client Itau -v")
    
    print("\\n3. 🧹 Solo limpieza (CSV → Excel):")
    print("   python process_itau_auto_v2.py --input archivo.csv")
    
    print("\\n4. ❓ Ver ayuda de un script:")
    print("   python [script].py --help")
    
    print("\\n🚀 Uso más fácil:")
    print("   1. Pon PDFs en pdfs/Itau/")
    print("   2. Presiona F5 en VS Code")
    print("   3. Selecciona 'Pipeline Completo'")
    
    print("\\n📊 Resultado:")
    print("   - RESULTADOS_ITAU_FINAL.xlsx (en la raíz)")
    print("   - Listo para descargar con clic derecho")
    
    print("\\n" + "=" * 50)
    print("✨ ¡Todo listo para automatizar!")

if __name__ == "__main__":
    main()