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
    echo Se você é participante, chame um instrutor.
    echo Ambiente virtual não encontrado em .venv.
    echo No laboratório, rode setup.cmd na pasta do kit.
    echo Em casa, siga docs\00-instalacao.md para instalar o ambiente.
    echo ==============================================================
    pause
    exit /b 1
)

rem pythonw has no console, so a broken environment would show nothing at all.
rem Check it with python.exe first. Its own error stays visible above our message.
set "PYTHON=%DIR%.venv\Scripts\python.exe"
"%PYTHON%" -c "import tkinter, yaml; tkinter.Tcl()"
if errorlevel 1 goto :tcltk_falhou

start "Central de treino" "%PYTHONW%" "%DIR%scripts\central_de_treino.py"
exit /b 0

:tcltk_falhou
echo ==============================================================
echo Se você é participante, chame um instrutor.
echo Não consegui preparar o ambiente Python para abrir a Central.
echo O erro está nas linhas acima. No laboratório, rode setup.cmd na pasta do kit.
echo Em casa, siga docs\00-instalacao.md. A Central precisa do tcl/tk do Python.
echo ==============================================================
pause
exit /b 1
