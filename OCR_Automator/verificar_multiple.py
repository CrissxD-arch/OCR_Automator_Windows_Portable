import pandas as pd
import os

def verificar_procesamiento_multiple():
    """Verifica los resultados del procesamiento de múltiples PDFs"""
    
    # Contar PDFs en la carpeta
    pdf_dir = "pdfs/Itau"
    pdf_files = [f for f in os.listdir(pdf_dir) if f.endswith('.pdf')]
    
    print("="*50)
    print("🔍 VERIFICACIÓN DE PROCESAMIENTO MÚLTIPLE")
    print("="*50)
    print(f"📁 PDFs encontrados en {pdf_dir}: {len(pdf_files)}")
    for i, pdf in enumerate(pdf_files, 1):
        print(f"  {i}. {pdf}")
    
    # Verificar resultados en Excel
    excel_file = "outputs/Itau/Itau_results_UNIFIED.xlsx"
    if os.path.exists(excel_file):
        df = pd.read_excel(excel_file)
        print(f"\n📊 Filas procesadas en Excel: {len(df)}")
        print(f"✅ Coincidencia: {'SÍ' if len(df) == len(pdf_files) else 'NO'}")
        
        print("\n📋 RESUMEN POR FILA:")
        for i, row in df.iterrows():
            tipo_doc = row['PRODUCTO']
            rut_completo = f"{row['RUT']}-{row['DV']}"
            print(f"  Fila {i+1}: {row['NOMBRE'][:30]}... -> RUT: {rut_completo} [{tipo_doc}]")
            print(f"           Dirección: {row['DIRECCION']}, {row['COMUNA']}")
    else:
        print(f"\n❌ No se encontró archivo de resultados: {excel_file}")
    
    print("="*50)

if __name__ == "__main__":
    verificar_procesamiento_multiple()