@echo off
setlocal
echo ==============================================================
echo   LPU Admission Intelligence - Starting Local Server
echo   AI Provider: Groq Cloud (openai/gpt-oss-120b)
echo   UI: LPU UMS 2024-25 Portal (http://localhost:8080)
echo ==============================================================

set PYTHON=C:\Users\sumit\.gemini\antigravity\scratch\python311\python.exe
if not exist "%PYTHON%" (
    set PYTHON=python
)

cd /d "%~dp0"
"%PYTHON%" app.py
pause
