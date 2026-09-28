@echo off
rem Opens Central de treino on Windows. Double-click this file.
rem
rem Finds .venv next to this script and the repo root (this script's own folder),
rem then runs scripts\central_de_treino.py with that virtual environment's
rem pythonw.exe, so no console window stays open behind the GUI and results\,
rem Demos\ and the relative paths in commands behave exactly as in the docs.
chcp 65001 >nul
setlocal

set "DIR=%~dp0"
cd /d "%DIR%"

set "PYTHONW=%DIR%.venv\Scripts\pythonw.exe"

if not exist "%PYTHONW%" (
    echo ==============================================================
    echo Ambiente virtual não encontrado em .venv.
    echo Siga docs\00-instalacao.md para instalar o ambiente do tutorial
    echo antes de abrir a Central de treino.
    echo ==============================================================
    pause
    exit /b 1
)

start "Central de treino" "%PYTHONW%" "%DIR%scripts\central_de_treino.py"
