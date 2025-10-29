@echo off
setlocal ENABLEEXTENSIONS

REM Lanzador local para Santander UNIFICADO (PP/CC)
REM Preferir .venv, con fallback a py -3.14

set SCRIPT_DIR=%~dp0
set VENV_PY="%SCRIPT_DIR%\.venv\Scripts\python.exe"
set PROJECT_PY="%SCRIPT_DIR%\OCR_Automator\process_santander_unified_v1.py"

if exist %VENV_PY% (
    echo Iniciando con el entorno del proyecto (.venv)
    %VENV_PY% %PROJECT_PY% --dpi 200
) else (
    echo Iniciando con Python del sistema
    py -3.14 %PROJECT_PY% --dpi 200
)

endlocal
