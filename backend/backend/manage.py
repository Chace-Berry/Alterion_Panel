#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
# Ensure project root is in sys.path for all import contexts
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)




def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    try:
        from django.core.management import execute_from_command_line
        # Ensure server ID is generated/persisted on every run (after Django sets up the path)
        try:
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)
            from dashboard.views import get_stable_server_id
            get_stable_server_id()
        except Exception:
            pass
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    import sys
    # Always run with HTTPS on port 13527 using provided certs with WebSocket support
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == 'runserver'):
        # Use Uvicorn for full ASGI support (HTTP + WebSocket)
        try:
            import uvicorn
            import django
            
            # Set up Django
            os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
            django.setup()
            
            # Get certificate paths
            cert_dir = os.path.dirname(os.path.abspath(__file__))
            ssl_keyfile = os.path.join(cert_dir, 'localhost-key.pem')
            ssl_certfile = os.path.join(cert_dir, 'localhost.pem')
            
            print("=" * 70)
            print("🚀 Starting Alterion Panel Server (Hot Reload Enabled)")
            print("=" * 70)
            print("HTTPS Server: https://localhost:13527/")
            print("WebSocket: wss://localhost:13527/")
            print("Hot Reload: Watching for file changes...")
            print("=" * 70)
            
            # Run Uvicorn with SSL and hot reload
            uvicorn.run(
                "backend.asgi:application",
                host="0.0.0.0",
                port=13527,
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
                reload=True,  # Enable hot reload
                reload_dirs=[cert_dir],  # Watch the backend directory
                log_level="info"
            )
        except ImportError as e:
            print(f"Error: {e}")
            print("Uvicorn not installed. Please install it: pip install uvicorn")
            sys.exit(1)
    else:
        main()

