@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "APP=%SCRIPT_DIR%OCR_Automator\webapp\app.py"

echo Starting OCR Automator web server...
if exist "%SCRIPT_DIR%.venv\Scripts\python.exe" (
  echo Using virtualenv Python
  "%SCRIPT_DIR%.venv\Scripts\python.exe" "%APP%"
) else (
  echo Using system Python (py -3.14)
  py -3.14 "%APP%"
)

pause@echo off
setlocal

REM Change to project root
cd /d "%~dp0"

echo ==================================================
echo   Iniciando servidor web OCR Automator
echo   URL: http://localhost:5000
echo   Usuario: admin  Password: change_me  (cambiar en OCR_Automator\config\web_config.json)
echo ==================================================

REM Optional: set secret key for sessions (fallback used in app.py if not set)
if "%OCR_AUTOMATOR_SECRET%"=="" set "OCR_AUTOMATOR_SECRET=dev-secret-change-me"

REM Prefer the workspace virtual environment if available and Flask is installed
set "VENV_PY=.\.venv\Scripts\python.exe"
set "PY_CMD=py -3.14"

if exist "%VENV_PY%" (
	"%VENV_PY%" -c "import flask" >nul 2>&1
	if %errorlevel%==0 (
		set "PY_CMD=%VENV_PY%"
	) else (
		echo [INFO] Flask no detectado en venv; usando Python del sistema py -3.14
	)
)

%PY_CMD% "OCR_Automator\webapp\app.py"

endlocal
