@echo off
chcp 65001 >nul
echo.
echo   ♡ KAngel Piano - 安装桌面快捷方式 ♡
echo   =====================================
echo.

:: Get paths
set "APP_DIR=%~dp0"
set "EXE_PATH=%APP_DIR%KAngel Piano.exe"
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\KAngel Piano.lnk"

:: Check exe exists
if not exist "%EXE_PATH%" (
    echo   [错误] 找不到 KAngel Piano.exe
    echo   请确保此脚本和 exe 在同一目录
    pause
    exit /b 1
)

:: Create asset folder if missing
if not exist "%APP_DIR%asset" (
    mkdir "%APP_DIR%asset"
    echo   已创建 asset 文件夹（放入你的 .mid 文件）
)

:: Create desktop shortcut via PowerShell
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; ^
   $sc = $ws.CreateShortcut('%SHORTCUT%'); ^
   $sc.TargetPath = '%EXE_PATH%'; ^
   $sc.WorkingDirectory = '%APP_DIR%'; ^
   $sc.IconLocation = '%EXE_PATH%,0'; ^
   $sc.Description = 'KAngel Piano - MIDI Auto Player'; ^
   $sc.Save(); ^
   Write-Host '  桌面快捷方式已创建！'"

echo.
echo   =====================================
echo   安装完成！
echo   桌面上已出现 KAngel Piano 图标
echo   双击即可启动 ♡
echo   =====================================
echo.
pause
