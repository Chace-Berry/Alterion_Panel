# Alterion Panel - Windows Installer Setup Complete! 🎉

## What We Built

A professional **single-file Windows installer** that bundles your entire Django + React control panel into one distributable `.exe` file.

## ✅ Features Implemented

### 1. **System Tray Application**
- ✅ Runs in background with system tray icon
- ✅ Right-click menu:
  - "Open Control Panel" - Opens browser
  - "Quit" - Stops server and exits
- ✅ Always runs on **port 13527** (HTTPS)

### 2. **Automatic Packaging**
- ✅ Frontend build files included (no Node.js needed for users!)
- ✅ All Python dependencies bundled
- ✅ Django + REST Framework + OAuth2 fully included
- ✅ Database, migrations, static files all packaged

### 3. **First-Time Setup**
- ✅ Generates encryption keys automatically
- ✅ Creates database
- ✅ Prompts for admin user creation
- ✅ Opens browser automatically

### 4. **Build System**
- ✅ `build_installer.ps1` - One-click build script
- ✅ Auto-installs all dependencies
- ✅ Uses PyInstaller with wildcard collection
- ✅ Creates Inno Setup installer (optional)

## 📦 Files Created

| File | Purpose |
|------|---------|
| `build_installer.ps1` | Main build script |
| `build_installer.bat` | Batch file wrapper |
| `alterion_panel.spec` | PyInstaller configuration |
| `launcher.py` | Entry point with system tray |
| `installer.iss` | Inno Setup script (for full installer) |

## 🚀 How to Build

```powershell
# Option 1: PowerShell script
.\build_installer.ps1

# Option 2: Batch file
build_installer.bat
```

### Build Process:
1. ✅ Checks static files exist
2. ✅ Installs all Python dependencies
3. ✅ Runs PyInstaller (creates `dist\AlterionPanel\AlterionPanel.exe`)
4. ✅ (Optional) Creates installer with Inno Setup

## 📤 Distribution

### For Quick Testing:
Share the entire `dist\AlterionPanel\` folder (contains .exe + dependencies)

### For Production:
Run Inno Setup on `installer.iss` to create:
- `installer_output\AlterionPanel_Setup_1.0.0.exe` ← Single installer file!

## 🎯 User Experience

### Installation:
1. User runs `AlterionPanel_Setup_1.0.0.exe`
2. Chooses install location
3. Creates desktop/start menu shortcuts
4. Installs in Program Files

### First Run:
1. Console window appears with setup wizard
2. Generates encryption keys
3. Creates database
4. Prompts for admin username/password
5. Starts server on port 13527
6. Opens browser automatically
7. Minimizes to system tray

### Normal Use:
1. User double-clicks icon
2. Server starts in background
3. Browser opens to control panel
4. System tray icon appears
5. Right-click tray icon to:
   - Open control panel
   - Quit application

## 🔧 Technical Details

### Packages Included:
- Django + all apps
- Django REST Framework
- OAuth2 Provider (django-oauth-toolkit)
- CORS headers
- Cryptography
- System monitoring (psutil)
- All your custom apps (dashboard, services, accounts, authentication)
- System tray support (pystray, PIL)

### Port Configuration:
- **Fixed port:** 13527
- **Protocol:** HTTPS (with self-signed certs)
- **Accessible at:** https://localhost:13527

### Python Path Setup:
- Automatically configured
- Django apps loaded via `django.setup()`
- All modules importable

## 📝 Dependencies to Install (for building)

```powershell
# Backend requirements (auto-installed by build script)
pip install -r backend\backend\requirements.txt

# Additional for system tray
pip install pystray pillow

# PyInstaller
pip install pyinstaller
```

## ⚙️ Configuration

### Change Port:
Edit `launcher.py` line 20:
```python
SERVER_PORT = 13527  # Change this
```

### Change App Name:
Edit `installer.iss` line 4:
```
#define MyAppName "Alterion Panel"
```

### Change Version:
Edit `installer.iss` line 5:
```
#define MyAppVersion "1.0.0"
```

## 🐛 Troubleshooting

### "Module not found" errors:
- Run `.\build_installer.ps1` again (installs dependencies)
- Check `alterion_panel.spec` packages_to_collect list

### Server won't start:
- Check port 13527 isn't in use
- Look in console window for errors

### System tray icon missing:
- pystray/PIL not installed
- App falls back to console mode

## 📊 Build Output Size

Expect ~150-200 MB for the full distribution including:
- Python runtime
- All dependencies
- Django + REST Framework
- Frontend static files

## 🎨 Customization

### Icon:
Replace `frontend\public\favicon.ico` with your icon

### Tray Icon:
Edit `create_tray_icon()` function in `launcher.py`

### Setup Wizard:
Edit `run_setup()` function in `launcher.py`

## ✨ What Makes This Special

1. **No separate frontend files** - Everything bundled!
2. **System tray integration** - Professional Windows app feel
3. **Auto-setup** - Users don't need technical knowledge
4. **One-click build** - `.\build_installer.ps1` does everything
5. **Wildcard collection** - Automatically includes ALL package files

## 🚀 Next Steps

1. Test the built executable
2. Create the Inno Setup installer
3. Test on a clean Windows machine
4. Upload to GitHub Releases
5. Share with users!

---

**Built with:** PyInstaller + Inno Setup + Django + React  
**Target:** Windows 10/11  
**License:** [Your License]
