#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script de prueba rápida para verificar el sistema limpio
"""

import sys
import os
from pathlib import Path

# Agregar el directorio actual al path
sys.path.insert(0, str(Path(__file__).parent))

def test_debug_system():
    """Prueba el sistema de debug limpio."""
    print("🔧 Probando sistema de debug limpio...")
    
    try:
        from debug_system import DebugSystem, initialize_debug_system, finalize_debug_system
        
        # Inicializar debug
        debug_system = initialize_debug_system(True)
        
        if debug_system:
            # Simular extracción OCR
            debug_system.log_ocr_extraction(
                pdf_path="test.pdf",
                page_num=1,
                raw_text="BANCO ITAU\nRUT: 12.345.678-9\nMonto: $1.500.000",
                extracted_data={
                    "rut": "12.345.678-9",
                    "monto": "1500000",
                    "banco": "ITAU",
                    "direccion": ""
                }
            )
            
            # Simular paso de procesamiento
            debug_system.log_processing_step(
                step_name="validar_datos",
                input_data={"count": 1},
                output_data={"count": 1, "valid": True}
            )
            
            # Simular transformación
            debug_system.log_data_transformation(
                field_name="rut",
                original_value="12345678-9",
                final_value="12.345.678-9",
                transformation_type="formateo_rut"
            )
            
            # Finalizar y generar reporte
            report_path = finalize_debug_system(debug_system)
            
            if report_path and os.path.exists(report_path):
                print(f"✅ Reporte generado: {report_path}")
                return True
            else:
                print("❌ Error generando reporte")
                return False
        else:
            print("❌ Error inicializando debug")
            return False
            
    except Exception as e:
        print(f"❌ Error en debug system: {e}")
        return False

def test_outputs_directory():
    """Verifica que la carpeta outputs existe."""
    print("📁 Verificando estructura de outputs...")
    
    outputs_dir = Path("../outputs/Itau")
    
    if outputs_dir.exists():
        print(f"✅ Directorio existe: {outputs_dir.absolute()}")
        return True
    else:
        try:
            outputs_dir.mkdir(parents=True, exist_ok=True)
            print(f"✅ Directorio creado: {outputs_dir.absolute()}")
            return True
        except Exception as e:
            print(f"❌ Error creando directorio: {e}")
            return False

def main():
    """Ejecuta las pruebas."""
    print("🧪 Iniciando pruebas del sistema limpio...")
    print("=" * 50)
    
    # Cambiar al directorio OCR_Automator
    os.chdir(Path(__file__).parent)
    
    # Pruebas
    tests = [
        test_outputs_directory,
        test_debug_system,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Error en prueba {test.__name__}: {e}")
            results.append(False)
            print()
    
    # Resumen
    print("=" * 50)
    print("📊 Resumen de pruebas:")
    passed = sum(results)
    total = len(results)
    
    print(f"✅ Pasaron: {passed}/{total}")
    if passed == total:
        print("🎉 ¡Todas las pruebas pasaron!")
        print("🚀 El sistema está listo para usar")
    else:
        print("⚠️  Algunas pruebas fallaron")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)