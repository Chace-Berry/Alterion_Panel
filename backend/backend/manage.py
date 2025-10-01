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
    # Always run with HTTPS on port 13527 using provided certs
    if len(sys.argv) == 1 or (len(sys.argv) == 2 and sys.argv[1] == 'runserver'):
        # Use runserver_plus if available
        try:
            import django_extensions
            sys.argv = [sys.argv[0], 'runserver_plus', '13527', '--cert-file', '../localhost.pem', '--key-file', '../localhost-key.pem']
        except ImportError:
            print("django-extensions not installed. Please install it for HTTPS support.")
            sys.exit(1)
    main()

