@echo off
echo ============================================
echo 🚀 OCR AUTOMATOR - EJECUTOR PRINCIPAL
echo ============================================
echo.

REM Activar entorno virtual
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ❌ Entorno virtual no encontrado
    echo 💡 Ejecuta primero: INSTALADOR_WINDOWS.bat
    pause
    exit /b 1
)

REM Ir al directorio correcto
cd /d "%~dp0OCR_Automator"

REM Verificar PDFs
echo 📁 Verificando PDFs en pdfs\Itau\...
if not exist "pdfs\Itau\*.pdf" (
    echo ❌ No se encontraron archivos PDF en pdfs\Itau\
    echo 💡 Coloca tus archivos PDF en la carpeta pdfs\Itau\
    pause
    exit /b 1
)

REM Contar PDFs
for /f %%i in ('dir /b "pdfs\Itau\*.pdf" 2^>nul ^| find /c /v ""') do set PDF_COUNT=%%i
echo ✅ Encontrados %PDF_COUNT% archivos PDF

echo.
echo 🔄 Iniciando procesamiento completo PDF → Excel...
echo ⏱️  Esto puede tomar unos minutos dependiendo del número de PDFs
echo.

REM Ejecutar pipeline completo
python pipeline_completo.py --client Itau -v

REM Verificar resultado
if exist "*.xlsx" (
    echo.
    echo ============================================
    echo 🎉 ¡PROCESAMIENTO COMPLETADO!
    echo ============================================
    echo.
    echo 📊 Archivo Excel generado:
    for %%f in (*.xlsx) do echo    📄 %%f
    echo.
    echo 💡 Puedes abrir el archivo Excel directamente
    echo    o copiarlo donde necesites.
    echo.
    
    REM Preguntar si abrir Excel
    set /p OPEN_EXCEL="¿Abrir Excel automáticamente? (s/n): "
    if /i "%OPEN_EXCEL%"=="s" (
        for %%f in (*.xlsx) do start "" "%%f"
    )
) else (
    echo ❌ No se generó el archivo Excel
    echo 💡 Revisa los mensajes de error arriba
)

echo.
echo 🔚 Presiona cualquier tecla para salir...
pause >nul