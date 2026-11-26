@echo off
setlocal

REM ============================================================
REM  LPU Admission Intelligence — Full Test Suite Runner
REM  Run from project root: tests\run_all.bat
REM ============================================================

set PYTHON=C:\Users\sumit\.gemini\antigravity\scratch\python311\python.exe
set PROJ=C:\Users\sumit\.gemini\antigravity\scratch\code-ui\code\lpu_admission_intelligence
set PYTEST=%PYTHON% -m pytest

cd /d %PROJ%

echo.
echo ========================================================
echo   LPU Admission Intelligence - Test Suite v1.0
echo ========================================================
echo.

echo [Phase 0] Baseline Engine Tests
echo ----------------------------------
%PYTEST% tests/test_engine.py -v --tb=short 2>&1
echo.

echo [Phase 1] UI Smoke Tests
echo ----------------------------------
%PYTEST% tests/test_ui_smoke.py -v --tb=short 2>&1
echo.

echo [Phase 2] API Hardening Tests
echo ----------------------------------
%PYTEST% tests/test_api_hardening.py -v --tb=short 2>&1
echo.

echo [Phase 3] Firebase Tests (mocked only)
echo ----------------------------------
%PYTEST% tests/test_firebase.py -v --tb=short -k "not Live" 2>&1
echo.

echo [Phase 4] AI Engine Tests
echo ----------------------------------
%PYTEST% tests/test_ai_engine.py -v --tb=short 2>&1
echo.

echo [Phase 5] E2E Chat Flow Tests
echo ----------------------------------
%PYTEST% tests/test_e2e_chat.py -v --tb=short 2>&1
echo.

echo [Phase 6] Original API Tests
echo ----------------------------------
%PYTEST% tests/test_api.py -v --tb=short 2>&1
echo.

echo ========================================================
echo   ALL PHASES COMPLETE
echo ========================================================
echo.
echo To run production tests, set:
echo   set PROD_URL=https://your-app.web.app
echo   %PYTEST% tests/test_production.py -v
echo.
pause

