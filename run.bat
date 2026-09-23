@echo off
rem Uruchamianie VCDS LogScope w trybie deweloperskim (z lokalnego środowiska .venv).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Brak srodowiska .venv - uruchom najpierw: uv venv --python 3.11 .venv ^&^& uv pip install --python .venv\Scripts\python.exe PySide6 pyqtgraph numpy
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m vcds_viewer %*
