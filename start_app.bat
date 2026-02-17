@echo off
setlocal

REM Always run from repository root (location of this .bat file)
cd /d "%~dp0"

REM Ensure local package imports work
set PYTHONPATH=%CD%

REM Prefer project virtual environment if available
if exist ".venv\Scripts\python.exe" (
  echo Using virtual environment Python: .venv\Scripts\python.exe
  ".venv\Scripts\python.exe" -m streamlit run ui/app.py
  goto :end
)

REM Fallback to system Python launcher
where py >nul 2>nul
if %errorlevel%==0 (
  echo Using Python launcher: py
  py -m streamlit run ui/app.py
  goto :end
)

REM Final fallback
echo Using python from PATH
python -m streamlit run ui/app.py

:end
endlocal
