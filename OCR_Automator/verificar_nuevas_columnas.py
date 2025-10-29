import pandas as pd
import os

def verificar_nuevas_columnas():
    """Verifica que las nuevas columnas estén presentes y con datos"""
    
    excel_file = "outputs/Itau/Itau_results_UNIFIED.xlsx"
    
    print("="*60)
    print("🔍 VERIFICACIÓN DE NUEVAS FUNCIONALIDADES")
    print("="*60)
    
    if not os.path.exists(excel_file):
        print(f"❌ No se encontró archivo: {excel_file}")
        return
    
    df = pd.read_excel(excel_file)
    
    # Nuevas columnas que deberían estar presentes
    nuevas_columnas = [
        'OPERACION_1',
        'FECHA_SUSCRIPCION_1', 
        'FECHA_VENCIMIENTO_1_CUOTA_1',
        'FECHA_VENCIMIENTO_ULTIMA_CUOTA_1'
    ]
    
    print(f"📊 Total de columnas en Excel: {len(df.columns)}")
    print(f"📋 Total de filas: {len(df)}")
    print()
    
    # Verificar nuevas columnas
    print("🔍 VERIFICACIÓN DE NUEVAS COLUMNAS:")
    for col in nuevas_columnas:
        if col in df.columns:
            valores_no_vacios = df[col].notna().sum()
            print(f"  ✅ {col}: Presente ({valores_no_vacios}/{len(df)} con datos)")
        else:
            print(f"  ❌ {col}: NO encontrada")
    
    print()
    print("📋 DATOS DETALLADOS POR FILA:")
    for i, row in df.iterrows():
        print(f"\n--- FILA {i+1}: {row['NOMBRE']} [{row['PRODUCTO']}] ---")
        print(f"  RUT: {row['RUT']}-{row['DV']}")
        print(f"  Operación: {row.get('OPERACION_1', 'N/A')}")
        print(f"  Fecha Suscripción: {row.get('FECHA_SUSCRIPCION_1', 'N/A')}")
        print(f"  Fecha Venc. 1ra Cuota: {row.get('FECHA_VENCIMIENTO_1_CUOTA_1', 'N/A')}")
        print(f"  Fecha Venc. Última Cuota: {row.get('FECHA_VENCIMIENTO_ULTIMA_CUOTA_1', 'N/A')}")
        print(f"  Dirección: {row['DIRECCION']}")
        print(f"  Comuna: {row['COMUNA']}")
        
        # Verificar correcciones N->Ñ
        nombre_tiene_ene = 'Ñ' in str(row['NOMBRE'])
        direccion_tiene_ene = 'Ñ' in str(row['DIRECCION'])
        comuna_tiene_ene = 'Ñ' in str(row['COMUNA'])
        
        if nombre_tiene_ene or direccion_tiene_ene or comuna_tiene_ene:
            print(f"  🔤 Correcciones N->Ñ aplicadas: ", end="")
            correcciones = []
            if nombre_tiene_ene: correcciones.append("NOMBRE")
            if direccion_tiene_ene: correcciones.append("DIRECCION") 
            if comuna_tiene_ene: correcciones.append("COMUNA")
            print(", ".join(correcciones))
    
    print()
    print("="*60)

if __name__ == "__main__":
    verificar_nuevas_columnas()