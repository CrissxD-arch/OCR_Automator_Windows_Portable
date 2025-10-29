@echo off
setlocal enableextensions
REM Cambiar a UTF-8 para mejor salida (opcional)
chcp 65001 >nul 2>&1

REM Directorios base
set "ROOT=%~dp0"
cd /d "%ROOT%"
set "OCR_DIR=%ROOT%OCR_Automator"

if not exist "%OCR_DIR%" (
  echo [ERROR] No se encontro la carpeta ^"OCR_Automator^" en: "%ROOT%"
  echo Asegurate de ejecutar este BAT dentro de la carpeta del proyecto.
  pause
  exit /b 1
)

REM Detectar Python
set "PYEXE="
if exist "c:\Users\cdiaz\AppData\Local\Python\pythoncore-3.14-64\python.exe" set "PYEXE=c:\Users\cdiaz\AppData\Local\Python\pythoncore-3.14-64\python.exe"
if not defined PYEXE (where python >nul 2>&1 && set "PYEXE=python")
if not defined PYEXE (where py >nul 2>&1 && set "PYEXE=py -3")

if not defined PYEXE (
  echo ❌ No se encontro Python. Instala Python 3.x o ajusta la ruta en este BAT.
  pause
  exit /b 1
)

echo ==================================================
echo   Ejecutando Itau UNIFICADO (PP/CC)
echo   Directorio: %OCR_DIR%
echo ==================================================

pushd "%OCR_DIR%"
if not exist "pdfs\Itau" mkdir "pdfs\Itau"
if not exist "outputs\Itau" mkdir "outputs\Itau"

%PYEXE% process_itau_unified_v1.py --geocode
set "RET=%ERRORLEVEL%"
popd

if not "%RET%"=="0" (
  echo ❌ El proceso termino con codigo %RET%.
  pause
  exit /b %RET%
)

set "OUT_XLS=%OCR_DIR%\outputs\Itau\Itau_results_UNIFIED.xlsx"
if exist "%OUT_XLS%" (
  echo ✅ Resultado: "%OUT_XLS%"
  start "" "%OUT_XLS%"
) else (
  echo ⚠️ No se encontro el Excel esperado: "%OUT_XLS%"
)

echo Listo.
pause
endlocal
