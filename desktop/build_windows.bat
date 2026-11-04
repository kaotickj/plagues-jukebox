@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "KAOS_PYTHON=python"
if exist "venv\Scripts\python.exe" set "KAOS_PYTHON=venv\Scripts\python.exe"
if exist ".venv\Scripts\python.exe" set "KAOS_PYTHON=.venv\Scripts\python.exe"

echo.
echo === Kaos Tunes 2.3.1 Windows Build ===
echo Using: %KAOS_PYTHON%
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CD%\prepare_dependencies.ps1"
if errorlevel 1 goto :failed

"%KAOS_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 goto :failed

"%KAOS_PYTHON%" -m pip install -r requirements-build.txt
if errorlevel 1 goto :failed

"%KAOS_PYTHON%" -m PyInstaller --clean --noconfirm KaosTunes.spec
if errorlevel 1 goto :failed

if not exist "dist\KaosTunes.exe" goto :missing
"%KAOS_PYTHON%" collect_licenses.py --destination "dist\licenses"
if errorlevel 1 goto :failed
copy /Y "THIRD_PARTY_NOTICES.txt" "dist\THIRD_PARTY_NOTICES.txt" >nul
if not exist "dist\licenses\chromaprint" mkdir "dist\licenses\chromaprint"
copy /Y "vendor\fpcalc\LICENSE.md" "dist\licenses\chromaprint\LICENSE.md" >nul
copy /Y "vendor\fpcalc\COPYING.LGPL-2.1.txt" "dist\licenses\chromaprint\COPYING.LGPL-2.1.txt" >nul

echo.
echo Build completed successfully:
echo %CD%\dist\KaosTunes.exe
echo.
pause
exit /b 0

:missing
echo.
echo ERROR: PyInstaller finished but dist\KaosTunes.exe was not created.
pause
exit /b 2

:failed
echo.
echo ERROR: The Windows build failed. Review the messages above.
pause
exit /b 1
