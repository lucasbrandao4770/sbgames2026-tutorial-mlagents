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

rem m3: pythonw has no console to show a missing Tcl/Tk error on; check with
rem python.exe here first, so a failure can be reported before that happens.
set "PYTHON=%DIR%.venv\Scripts\python.exe"
"%PYTHON%" -c "import tkinter, yaml; tkinter.Tcl()" >nul 2>&1
if errorlevel 1 goto :tcltk_falhou

start "Central de treino" "%PYTHONW%" "%DIR%scripts\central_de_treino.py"
exit /b 0

:tcltk_falhou
echo ==============================================================
echo Não consegui preparar o ambiente Python para abrir a Central.
echo Reinstale o Python pelo instalador do python.org, com a opção
echo tcl/tk marcada, seguindo docs\00-instalacao.md.
echo ==============================================================
pause
exit /b 1
