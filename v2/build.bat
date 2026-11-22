@echo off
setlocal
cd /d "%~dp0"

py -3 -m pip install --upgrade pip
if errorlevel 1 goto :error
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto :error

py -3 -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name XboxControllerHotkey ^
  --icon "assets\app-icon.ico" ^
  --collect-all pygame ^
  --collect-all winsdk ^
  --add-data "assets;assets" ^
  app.py
if errorlevel 1 goto :error

echo.
echo PORTABLE BUILD COMPLETE:
echo dist\XboxControllerHotkey.exe
if /i "%~1"=="--no-pause" exit /b 0
pause
exit /b 0

:error
echo.
echo BUILD FAILED. Review the error above.
if /i "%~1"=="--no-pause" exit /b 1
pause
exit /b 1
