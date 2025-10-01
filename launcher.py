"""
Alterion Panel - Windows Launcher
This is the main entry point for the Windows .exe version
"""

import os
import sys
import subprocess
import threading
import webbrowser
import time
from pathlib import Path

# Try to import pystray for system tray, if not available run in console mode
try:
    import pystray
    from PIL import Image, ImageDraw
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False

# Global server process
server_process = None
SERVER_PORT = 13527


def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    
    return os.path.join(base_path, relative_path)


def setup_environment():
    """Setup the application environment"""
    app_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    backend_parent = app_dir / "backend"
    backend_dir = backend_parent / "backend"
    
    # Add backend directories to Python path
    sys.path.insert(0, str(backend_parent))
    sys.path.insert(0, str(backend_dir))
    
    # Set environment variables
    os.environ['DJANGO_SETTINGS_MODULE'] = 'backend.settings'
    os.environ['PYTHONPATH'] = str(backend_dir)
    
    # Initialize Django
    import django
    django.setup()
    
    return backend_dir


def run_setup(backend_dir):
    """Run initial setup: generate keys, migrate database, etc."""
    print("=" * 60)
    print("Alterion Panel - First Time Setup")
    print("=" * 60)
    
    os.chdir(backend_dir)
    
    # Generate Server ID
    print("\n[1/4] Generating Server ID...")
    try:
        import importlib.util
        views_path = backend_dir / 'dashboard' / 'views.py'
        spec = importlib.util.spec_from_file_location("dashboard.views", str(views_path))
        views = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(views)
        server_id = views.get_stable_server_id()
        print(f"✓ Server ID: {server_id}")
    except Exception as e:
        print(f"⚠ Warning: Could not generate server ID: {e}")
    
    # Generate encryption keys
    print("\n[2/4] Generating Encryption Keys...")
    try:
        subprocess.run([sys.executable, '-m', 'services.pem', '--force'], check=True)
    except Exception as e:
        print(f"⚠ Warning: Could not generate keys: {e}")
    
    # Run migrations
    print("\n[3/4] Setting up database...")
    try:
        subprocess.run([sys.executable, 'manage.py', 'migrate', '--noinput'], check=True)
    except Exception as e:
        print(f"⚠ Warning: Migration failed: {e}")
    
    # Collect static files
    print("\n[4/4] Collecting static files...")
    try:
        subprocess.run([sys.executable, 'manage.py', 'collectstatic', '--noinput'], check=True)
    except Exception as e:
        print(f"⚠ Warning: Could not collect static files: {e}")
    
    # Create superuser
    print("\nCreating admin user...")
    username = input("Enter admin username (default: admin): ").strip() or "admin"
    email = input("Enter admin email: ").strip() or "admin@localhost"
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        if not User.objects.filter(username=username).exists():
            import getpass
            password = getpass.getpass("Enter admin password: ")
            User.objects.create_superuser(username=username, email=email, password=password)
            print(f"✓ Admin user '{username}' created successfully!")
        else:
            print(f"✓ User '{username}' already exists")
    except Exception as e:
        print(f"⚠ Warning: Could not create admin user: {e}")
    
    print("\n" + "=" * 60)
    print("✓ Setup complete!")
    print("=" * 60)


def start_django_server(backend_dir, port=13527):
    """Start the Django development server as background process"""
    global server_process
    os.chdir(backend_dir)
    
    try:
        server_process = subprocess.Popen([
            sys.executable, 
            'manage.py', 
            'runserver', 
            f'{port}',
            '--noreload'
        ], 
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return True
    except Exception as e:
        print(f"✗ Error starting server: {e}")
        return False


def stop_django_server():
    """Stop the Django server"""
    global server_process
    if server_process:
        server_process.terminate()
        server_process.wait(timeout=5)
        server_process = None


def create_tray_icon():
    """Load the application icon for the system tray"""
    try:
        # Try to load the icon from the app directory
        app_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        icon_paths = [
            app_dir / 'frontend' / 'public' / 'favicon.ico',
            app_dir / 'backend' / 'backend' / 'static' / 'favicon.ico',
            app_dir / 'favicon.ico',
        ]
        
        for icon_path in icon_paths:
            if icon_path.exists():
                return Image.open(str(icon_path))
        
        # Fallback: create a simple colored square icon
        print("⚠ Warning: favicon.ico not found, using fallback icon")
        width = 64
        height = 64
        color1 = (52, 152, 219)  # Blue
        color2 = (41, 128, 185)  # Darker blue
        
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle([width // 4, height // 4, 3 * width // 4, 3 * height // 4], fill=color2)
        
        return image
    except Exception as e:
        print(f"⚠ Warning: Could not load icon: {e}")
        # Return a simple fallback
        image = Image.new('RGB', (64, 64), (52, 152, 219))
        return image


def on_open(icon, item):
    """Open the control panel in browser"""
    webbrowser.open(f"https://localhost:{SERVER_PORT}")


def on_quit(icon, item):
    """Quit the application"""
    print("Stopping Alterion Panel...")
    stop_django_server()
    icon.stop()


def setup_system_tray():
    """Setup system tray icon with menu"""
    icon_image = create_tray_icon()
    
    menu = pystray.Menu(
        pystray.MenuItem("Open Control Panel", on_open, default=True),
        pystray.MenuItem("Quit", on_quit)
    )
    
    icon = pystray.Icon(
        "alterion_panel",
        icon_image,
        "Alterion Panel",
        menu
    )
    
    icon.run()


def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════╗
    ║      Alterion Panel - Windows         ║
    ║         Control Panel Server          ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Setup environment
    backend_dir = setup_environment()
    
    # Check if this is first run
    setup_marker = backend_dir / "dashboard" / "serverid.dat"
    if not setup_marker.exists():
        print("\n📦 First time setup detected...")
        response = input("\nRun setup now? (yes/no): ").lower()
        if response in ['yes', 'y', '']:
            run_setup(backend_dir)
        else:
            print("⚠ Setup skipped. Run setup.py manually if needed.")
    
    # Start server in background
    url = f"https://localhost:{SERVER_PORT}"
    print(f"\n🚀 Starting Alterion Panel on {url}")
    print("=" * 60)
    
    if not start_django_server(backend_dir, SERVER_PORT):
        input("\nPress Enter to exit...")
        sys.exit(1)
    
    # Wait a moment for server to start
    time.sleep(2)
    
    # Open browser
    print(f"🌐 Opening browser: {url}")
    webbrowser.open(url)
    
    # Run system tray if available
    if TRAY_AVAILABLE:
        print("\n✓ Server running in background")
        print("  Right-click tray icon to open or quit")
        print("=" * 60)
        try:
            setup_system_tray()
        except KeyboardInterrupt:
            pass
    else:
        print("\n✓ Server running (System tray not available)")
        print("  Press Ctrl+C to stop")
        print("=" * 60)
        try:
            # Keep the process alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
    
    # Cleanup
    stop_django_server()
    print("\n✓ Server stopped")


if __name__ == '__main__':
    main()


if __name__ == "__main__":
    main()
