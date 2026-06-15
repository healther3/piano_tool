@echo off
echo ============================================
echo   KAngel Piano - Build .exe
echo ============================================
echo.

:: Install dependencies
pip install pywebview mido pydirectinput keyboard pyinstaller

echo.
echo Building...
echo.

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
  --name "KAngel Piano" ^
  main.py

if %ERRORLEVEL% NEQ 0 (
  echo.
  echo [ERROR] Build failed! Check the output above.
  pause
  exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Output: dist\KAngel Piano.exe
echo.
echo   NOTE: Place the .exe next to the "asset"
echo   folder containing your .mid files.
echo ============================================
pause
