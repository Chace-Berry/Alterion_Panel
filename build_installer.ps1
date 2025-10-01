# Simple Build Script for Alterion Panel
Write-Host '=====================================' -ForegroundColor Cyan
Write-Host 'Alterion Panel - Installer Builder' -ForegroundColor Cyan
Write-Host '=====================================' -ForegroundColor Cyan

# Step 1: Check static files
Write-Host "
[1/3] Checking static files..." -ForegroundColor Yellow
if (Test-Path 'backend\backend\static\index.html') {
    Write-Host 'Frontend static files found' -ForegroundColor Green
} else {
    Write-Host 'WARNING: No static files found' -ForegroundColor Yellow
}

# Step 2: Check PyInstaller
Write-Host "
[2/4] Installing dependencies..." -ForegroundColor Yellow
Write-Host "Installing backend requirements..." -ForegroundColor Gray
pip install -r backend\backend\requirements.txt -q

$version = python -m PyInstaller --version 2>$null
Write-Host "PyInstaller $version found" -ForegroundColor Green

# Clean old builds
if (Test-Path 'dist') { Remove-Item -Recurse -Force 'dist' }
if (Test-Path 'build') { Remove-Item -Recurse -Force 'build' }

# Build executable
Write-Host '
[3/4] Creating executable - this may take 2-5 minutes...' -ForegroundColor Yellow
python -m PyInstaller alterion_panel.spec --clean --noconfirm

if (Test-Path 'dist\AlterionPanel\AlterionPanel.exe') {
    Write-Host '
[4/4] SUCCESS: Executable created!' -ForegroundColor Green
} else {
    Write-Host 'ERROR: Build failed!' -ForegroundColor Red
    exit 1
}
