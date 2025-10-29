import pandas as pd

df = pd.read_excel('outputs/Itau/Itau_results_UNIFIED.xlsx')
print('=== RESULTADOS FINALES ===')
print(f'Total filas: {len(df)}')
print()

print('RUTs VERIFICADOS:')
for i, row in df.iterrows():
    rut_completo = f"{row['RUT']}-{row['DV']}"
    print(f'  Fila {i+1}: {row["NOMBRE"]} -> RUT: {rut_completo} [{row["PRODUCTO"]}]')

print()
print('OPERACIONES:')
for i, row in df.iterrows():
    print(f'  PDF {i+1}: Operación {row["OPERACION_1"]} - {row["DIRECCION"]}, {row["COMUNA"]}')