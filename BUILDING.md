# Building Alterion Panel for Distribution

## Overview

You can distribute Alterion Panel as a **single .exe installer** that includes everything users need. No separate frontend files needed!

## What Gets Bundled

✅ **Backend (Django):**
- Python runtime
- All Python dependencies
- Django app + REST API
- Database migrations
- SSL certificates

✅ **Frontend (React):**
- Pre-built static files (HTML/CSS/JS)
- No Node.js needed for end users!

✅ **Launcher:**
- Auto-setup wizard
- Server startup
- Browser launcher

## Build Process

### Option 1: PowerShell (Recommended)
```powershell
.\build_installer.ps1
```

### Option 2: Batch File
```cmd
build_installer.bat
```

### Option 3: Manual Steps
```powershell
# 1. Build frontend (if not already done)
cd frontend
yarn build
cd ..

# 2. Install PyInstaller
pip install pyinstaller

# 3. Build executable
pyinstaller alterion_panel.spec --clean

# 4. Create installer (requires Inno Setup)
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

## Output

📦 **`installer_output\AlterionPanel_Setup_1.0.0.exe`**

This is the **ONLY file** you distribute to users!

## Installation Flow for End Users

1. **Run installer** → GUI wizard appears
2. **Choose install location** (default: Program Files)
3. **Select options:**
   - Desktop shortcut
   - Start menu entry
   - Run at startup (optional)
4. **Install** → Copies all files
5. **First run:**
   - Generates server ID
   - Creates encryption keys
   - Sets up database
   - Creates admin user
   - Opens browser to control panel

## File Structure After Install

```
C:\Program Files\Alterion Panel\
├── AlterionPanel.exe        ← Main executable
├── backend\
│   └── backend\
│       ├── db.sqlite3       ← Database (created on first run)
│       ├── static\          ← Frontend build files
│       ├── dashboard\
│       ├── services\
│       └── ...
└── ...
```

## Distribution

### For GitHub Releases
1. Build the installer
2. Upload `AlterionPanel_Setup_1.0.0.exe` to GitHub Releases
3. Users download and run - that's it!

### File Size
Expect ~100-150 MB (includes Python runtime + dependencies)

## Development vs Distribution

| Aspect | Development | Distribution |
|--------|-------------|--------------|
| Frontend | `yarn dev` (live reload) | Pre-built, included in .exe |
| Backend | `python manage.py runserver` | Bundled with PyInstaller |
| Database | SQLite in dev folder | Created on first user run |
| Dependencies | `pip install -r requirements.txt` | Bundled in executable |
| Node.js | Required | NOT required for users! |

## Why This Approach?

❌ **Don't ship separate files because:**
- Users don't know where to put them
- Risk of missing files
- Complex setup instructions
- Looks unprofessional

✅ **Single installer is better because:**
- Professional appearance
- One-click installation
- Automatic setup
- Includes uninstaller
- Users expect this on Windows

## Updating Your Installer

When you make changes:

1. **Code changes:** Update backend/frontend code
2. **Version bump:** Edit `installer.iss` line 5: `#define MyAppVersion "1.0.1"`
3. **Rebuild:** Run `.\build_installer.ps1`
4. **Distribute:** Share new `AlterionPanel_Setup_1.0.1.exe`

## Requirements for Building (Developer Machine Only)

- Python 3.11+
- Node.js/Yarn (for frontend build)
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6: https://jrsoftware.org/isinfo.php

## Requirements for Users (NONE!)

Users just need:
- Windows 10/11
- That's it! Everything else is bundled.

## Troubleshooting Build Issues

### "PyInstaller not found"
```powershell
pip install pyinstaller
```

### "Inno Setup not found"
Download from: https://jrsoftware.org/isinfo.php

### "Frontend not built"
```powershell
cd frontend
yarn install
yarn build
cd ..
```

### Rebuild from scratch
```powershell
# Clean everything
Remove-Item -Recurse -Force dist, build, installer_output -ErrorAction SilentlyContinue

# Rebuild
.\build_installer.ps1
```
