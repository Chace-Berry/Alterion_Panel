# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec file for Alterion Panel

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Get project paths
project_root = Path('.').absolute()
backend_dir = project_root / 'backend' / 'backend'
static_dir = backend_dir / 'static'

# Add backend to Python path so modules can be imported
sys.path.insert(0, str(project_root / 'backend'))

# Collect ALL submodules and data from these packages
packages_to_collect = [
    'django',
    'rest_framework',
    'rest_framework_simplejwt',
    'oauth2_provider',  # django-oauth-toolkit
    'oauthlib',
    'jwt',
    'corsheaders',
    'cryptography',
    'psutil',
    'pySMART',
    'prometheus_client',
    'paramiko',
    'fabric',
    'celery',
    'django_celery_beat',
    'django_celery_results',
    'channels',
    'daphne',
    'redis',
    'django_redis',
    'gunicorn',
    'drf_yasg',
    'keyring',
    'requests',
    'speedtest',
    'django_extensions',
    'pystray',  # System tray icon
    'PIL',      # Pillow for icon generation
]

# Collect everything from these packages
datas = []
binaries = []
hiddenimports = []

for package in packages_to_collect:
    try:
        pkg_datas, pkg_binaries, pkg_hiddenimports = collect_all(package)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hiddenimports
    except:
        pass

# Collect all backend modules using collect_submodules
hiddenimports += collect_submodules('backend')
hiddenimports += collect_submodules('dashboard')
hiddenimports += collect_submodules('services')
hiddenimports += collect_submodules('accounts')
hiddenimports += collect_submodules('authentication')

# Collect all backend files including static (already built frontend)
backend_datas = []
for pattern in ['**/*.py', '**/*.html', '**/*.css', '**/*.js', '**/*.json', '**/*.txt', '**/*.ico', '**/*.svg', '**/*.png']:
    for file in backend_dir.rglob(pattern):
        if '__pycache__' not in str(file) and '.pyc' not in str(file):
            rel_path = file.relative_to(project_root)
            backend_datas.append((str(file), str(rel_path.parent)))

a = Analysis(
    ['launcher.py'],
    pathex=[
        str(project_root),
        str(project_root / 'backend'),
        str(backend_dir),
    ],
    binaries=binaries,
    datas=datas + backend_datas + [
        (str(backend_dir / 'db.sqlite3'), 'backend/backend'),  # Include empty db
        ('README.md', '.'),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AlterionPanel',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,  # Keep console for server logs
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='frontend/public/favicon.ico' if (project_root / 'frontend' / 'public' / 'favicon.ico').exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AlterionPanel',
)
