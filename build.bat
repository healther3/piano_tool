@echo off
echo ============================================
echo   KAngel Piano - Build .exe
echo ============================================
echo.

:: Install dependencies
pip install pywebview mido pydirectinput keyboard pyinstaller requests

echo.
echo Building exe...
echo.

:: Kill running instance if any
taskkill /f /im "KAngel Piano.exe" >nul 2>&1

:: Use "python -m PyInstaller" to avoid PATH issues
python -m PyInstaller --onefile --windowed ^
  --add-data "index.html;." ^
  --add-data "core\loader.py;core" ^
  --add-data "core\manager.py;core" ^
  --hidden-import=mido ^
  --hidden-import=mido.backends ^
  --hidden-import=mido.backends.rtmidi ^
  --hidden-import=pydirectinput ^
  --hidden-import=keyboard ^
  --hidden-import=clr ^
  --hidden-import=requests ^
  --icon=icon.ico ^
  --name "KAngel Piano" ^
  main.py --noconfirm

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] Build failed! Check the output above.
  pause
  exit /b 1
)

:: Package release zip
echo.
echo Packaging release zip...
if exist "dist\asset" rmdir /s /q "dist\asset"
xcopy "asset" "dist\asset\" /e /i /q >nul 2>&1
if exist "KAngel Piano.zip" del "KAngel Piano.zip"
powershell -NoProfile -Command "Compress-Archive -Path 'dist\*' -DestinationPath 'KAngel Piano.zip' -Force"

echo.
echo ============================================
echo   Build complete!
echo.
echo   dist\KAngel Piano.exe
echo   KAngel Piano.zip  (release package)
echo ============================================
pause
