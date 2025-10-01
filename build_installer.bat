@echo off
REM Build Alterion Panel Installer

echo =====================================
echo Alterion Panel - Installer Builder
echo =====================================
echo.

powershell.exe -ExecutionPolicy Bypass -File build_installer.ps1

if %ERRORLEVEL% EQU 0 (
    echo.
    echo Build completed successfully!
    pause
) else (
    echo.
    echo Build failed! Check the error messages above.
    pause
)
