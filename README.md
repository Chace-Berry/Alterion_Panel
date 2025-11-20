<div align="center">
    <picture>
        <source media="(prefers-color-scheme: dark)" srcset="assets/logo.svg?v=1">
        <source media="(prefers-color-scheme: light)" srcset="assets/logo-2.svg?v=1">
        <img alt="Alterion Logo" src="assets/logo-2.svg?v=1" width="400">
    </picture>
</div>

<div align="center">

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.2.7-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)](https://reactjs.org/)
[![Version](https://img.shields.io/badge/version-1.0.0-green.svg)](.)

**A modern web hosting control panel that is actually free**  
Built with React frontend and Django REST API backend  
Native Windows application with system tray integration

---

</div>

## � Quick Start for End Users

**Want to run Alterion Panel on your Windows PC?**

1. Download `AlterionPanel_Setup_1.0.0.exe` from [Releases](https://github.com/chaceberry/alterion-panel/releases)
2. Run the installer and follow the setup wizard
3. The application will run in your system tray with automatic startup
4. Right-click the tray icon to open the control panel or quit
5. Access the panel at: **https://localhost:13527**

**No Python, Node.js, or command line required!** Everything is bundled in the installer.

---

## 📦 Windows Installer Distribution

For end users who want to run Alterion Panel on Windows, we provide a **single-file installer** that packages everything needed.

### Features

✅ **System Tray Integration** - Runs in background with icon in system tray  
✅ **Right-Click Menu** - Open control panel or quit from tray icon  
✅ **Fixed Port** - Always runs on port 13527 (HTTPS)  
✅ **No Console Window** - Clean background execution  
✅ **Auto-Start** - Opens browser automatically on launch  
✅ **Professional Install** - GUI wizard with custom install path  
✅ **Desktop & Start Menu Shortcuts** - Easy access  
✅ **Automatic Setup** - Generates encryption keys and database on first run  
✅ **Uninstaller Included** - Clean removal via Windows Control Panel  

### Default Install Location

```
C:\Program Files\chace_berry\Alterion\AlterionPanel\
```

### Building the Installer (For Developers)

#### Prerequisites
- Python 3.11+ with pip
- All backend dependencies installed (`pip install -r backend/backend/requirements.txt`)
- [PyInstaller](https://pyinstaller.org/) (`pip install pyinstaller`)
- [Inno Setup 6](https://jrsoftware.org/isinfo.php) for creating the installer GUI

#### Build Steps

1. **Ensure frontend static files are built:**
   ```powershell
   # The frontend build should already be in backend/backend/static/
   # If not, build it first:
   cd frontend
   yarn install
   yarn build
   ```

2. **Run the automated build script:**
   ```powershell
   # From project root
   .\build_installer.ps1
   ```

3. **Build process:**
   - Step 1: Validates static files exist
   - Step 2: Installs all Python dependencies
   - Step 3: Runs PyInstaller to create standalone executable
   - Step 4: Creates Windows installer with Inno Setup

4. **Output:**
   ```
   installer_output\AlterionPanel_Setup_1.0.0.exe
   ```
   This is the **only file** you need to distribute!

### What Gets Bundled

The installer includes:
- Python 3.13 runtime (embedded)
- Django 4.2.7 and all backend dependencies
- React frontend (pre-built static files)
- SSL certificates (self-signed for localhost)
- All required Python packages (see `alterion_panel.spec`)
- System tray icon (favicon.ico)
- Launcher application with Django initialization

### Technical Details

- **Executable**: `dist/AlterionPanel/AlterionPanel.exe`
- **Entry Point**: `launcher.py`
- **PyInstaller Spec**: `alterion_panel.spec`
- **Installer Script**: `installer.iss` (Inno Setup)
- **Build Script**: `build_installer.ps1`

---

---

## 🏗️ Architecture Overview

This project demonstrates a modern approach to building a desktop web application with a React frontend and Django REST API backend.

### Core Components

#### Backend (Django REST API)
- **Framework**: Django 4.2.7 with Django REST Framework
- **Authentication**: OAuth2 with custom token views
- **Database**: SQLite (embedded, no external DB required)
- **Security**: CSRF protection, encrypted credentials, secure session management
- **API Endpoints**: RESTful API for all service management operations

#### Frontend (React SPA)
- **Framework**: React 18 with modern hooks
- **Routing**: React Router for navigation
- **Styling**: CSS variables with dynamic theming
- **State Management**: Context API for auth and theme
- **Build Tool**: Vite for fast builds and HMR

#### Desktop Integration
- **Launcher**: Python-based system tray application
- **Server**: Django development server running in background (port 13527)
- **Process Management**: Background execution with CREATE_NO_WINDOW flag
- **System Tray**: pystray with PIL for Windows tray icon
- **Browser**: Automatic launch via webbrowser module

### Data Flow

```
User → System Tray Icon → Launcher (launcher.py)
                              ↓
                    Django Server (port 13527)
                              ↓
                    Static Files (React SPA)
                              ↓
                    Browser → React App
                              ↓
                    API Calls → Django REST Framework
                              ↓
                    Database/Services
```

```

---

## ✨ Key Features

### Service Management
- **FTP Server**: Pure-FTPd management with MySQL authentication
- **Database Server**: MySQL/MariaDB instance management
- **Email Server**: Postfix/Dovecot email server configuration
- **Web Server**: Nginx/LiteSpeed web server monitoring and management

### Account Management
- Create and manage FTP accounts
- Database creation and user permissions
- Email account provisioning
- User role and permission management
- Secure credential storage with encryption

### System Monitoring
- Real-time CPU, Memory, and Disk usage metrics
- Network I/O monitoring with bandwidth graphs
- Service status monitoring (running/stopped)
- System resource alerts and notifications
- Activity log management

### Security Features
- OAuth2 token-based authentication
- Encrypted credential storage using Fernet symmetric encryption
- CSRF protection on all forms
- Secure session management
- HTTPS with self-signed certificates (localhost)
- Server ID for unique instance identification

---

## 💻 Development Setup

For developers who want to contribute or modify the application.

### Prerequisites

- **Python 3.11+** with pip
- **Node.js 18+** with yarn/npm
- **Git** for version control

### 1. Clone the Repository

```bash
git clone https://github.com/chace-berry/alterion-panel.git
cd alterion-panel
```
```bash
git clone https://github.com/chaceberry/alterion-panel.git
cd alterion-panel
```

### 2. Backend Setup (Django)

```bash
cd backend/backend

# Install Python dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Create a superuser account
python manage.py createsuperuser

# Collect static files (if running in production mode)
python manage.py collectstatic --noinput
```

### 3. Frontend Setup (React)

```bash
cd ../../frontend

# Install Node dependencies
yarn install
# or: npm install

# Build for production
yarn build
# or: npm run build

# This creates the static files in backend/backend/static/
```

### 4. Development Mode

#### Option A: Separate Development Servers (Recommended for Frontend Development)

```bash
# Terminal 1: Django Backend
cd backend/backend
python manage.py runserver 13527

# Terminal 2: React Frontend with Hot Reload
cd frontend
yarn dev
# Frontend proxy configured to forward API calls to Django backend
```

#### Option B: Django Serves Built React App (Production-like)

```bash
# Build React app first
cd frontend
yarn build

# Then run Django server
cd ../backend/backend
python manage.py runserver 13527

# Access at: https://localhost:13527
```

---

## 🐳 Docker Deployment

For containerized deployment with Nginx reverse proxy.

```bash
cd docker
docker-compose up --build
```

**Services:**
- **Backend**: Django REST API on port 8000
- **Frontend**: React SPA served by Nginx on port 80
- **Nginx**: Reverse proxy handling routing

---



## 🔐 Security Considerations

### Implemented Security Measures

1. **Authentication & Authorization**
   - OAuth2 token-based authentication
   - Session management with secure cookies
   - User permission checks on all endpoints
   - Superuser-only access for sensitive operations

2. **Data Protection**
   - CSRF protection on all POST/PUT/DELETE requests
   - Fernet symmetric encryption for sensitive credentials
   - Secure password hashing with Django's PBKDF2
   - HTTPS with TLS certificates (self-signed for localhost)

3. **Input Validation**
   - Django REST Framework serializers for data validation
   - SQL injection protection via Django ORM
   - XSS protection with Django's template escaping
   - File upload validation and sanitization

4. **System Security**
   - Subprocess command sanitization for service management
   - Limited system access with proper permission checks
   - Secure file path handling
   - Environment variable protection

### Security Best Practices for Production

- Replace self-signed certificates with valid TLS certificates
- Use environment variables for sensitive settings (SECRET_KEY, etc.)
- Enable Django's security middleware in production
- Set `DEBUG = False` in production
- Configure proper CORS settings
- Implement rate limiting on API endpoints
- Regular security audits and dependency updates

---

## 🔧 Configuration

### Backend Configuration (`backend/backend/settings.py`)

```python
# Server Configuration
PORT = 13527  # Fixed HTTPS port

# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Encryption
# Server ID and encryption keys are auto-generated on first run
# Located in: backend/dashboard/serverid.dat

# CORS Settings
CORS_ALLOWED_ORIGINS = [
    'https://localhost:13527',
]

# Static Files
STATIC_ROOT = BASE_DIR / 'static'
STATIC_URL = '/static/'
```

### Frontend Configuration (`frontend/src/config.js`)

```javascript
export const API_BASE_URL = 'https://localhost:13527';
export const API_ENDPOINTS = {
  token: '/api/token/',
  refresh: '/api/token/refresh/',
  logout: '/api/logout/',
  services: '/api/services/',
  // ... more endpoints
};
```

---

## 🚀 Deployment Options

### 1. Windows Desktop Application (Recommended)
- Single executable installer
- System tray integration
- No external dependencies
- Perfect for local development or single-server setups

### 2. Traditional Web Server
- Django serves both API and static files
- Single domain, single server
- Nginx/Apache reverse proxy (optional)
- Best for VPS/dedicated server deployments

### 3. Microservices Architecture
- React frontend served by Nginx (port 80/443)
- Django API on separate server/port
- CORS configuration required
- Best for scalable cloud deployments

### 4. Docker Containers
- Containerized frontend and backend
- Docker Compose orchestration
- Easy scaling and deployment
- Best for cloud platforms (AWS, Azure, GCP)

---

## 🛠️ Troubleshooting

### Common Issues

**Issue: "Apps aren't loaded yet" error**
- Solution: Ensure `django.setup()` is called before importing models
- This is handled in `launcher.py` for desktop builds

**Issue: Static files not found**
- Solution: Run `python manage.py collectstatic` or ensure frontend is built
- Check that `backend/backend/static/` contains React build files

**Issue: CORS errors in browser**
- Solution: Verify `CORS_ALLOWED_ORIGINS` in `settings.py`
- Ensure frontend is accessing the correct API URL

**Issue: Port 13527 already in use**
- Solution: Check for other Alterion instances running
- Kill process: `taskkill /F /IM AlterionPanel.exe` (Windows)

**Issue: SSL certificate warnings**
- Expected: Self-signed certificates will show browser warnings
- Solution: Click "Advanced" → "Proceed to localhost" in browser

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ESLint configuration for JavaScript/React
- Write meaningful commit messages
- Add tests for new features
- Update documentation as needed

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0** - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Django** - Amazing web framework
- **React** - Modern frontend library
- **PyInstaller** - Python to executable packaging
- **Inno Setup** - Professional Windows installer creation

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/chaceberry/alterion_panel/issues)
- **Discussions**: [GitHub Discussions](https://github.com/chaceberry/alterion_panel/discussions)
- **Email**: chaceberry686@gmail.com

---

<div align="center">

**Made with ❤️ by Chace Berry**

[Coming Soon]() • [Comming Soon]() • [GitHub](https://github.com/chaceberry/alterion-panel)

</div>
