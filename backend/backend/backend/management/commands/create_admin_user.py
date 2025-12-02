"""
Django management command to create an admin user with provided credentials.
Ensures init_system has been run first, then creates the admin user.
"""
import sys
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command


class Command(BaseCommand):
    help = 'Create an admin user with provided credentials. Runs init_system if not already run.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, required=True, help='Username for the admin user')
        parser.add_argument('--email', type=str, required=True, help='Email for the admin user')
        parser.add_argument('--password', type=str, required=True, help='Password for the admin user')

    def handle(self, *args, **options):
        username = options['username']
        email = options['email']
        password = options['password']

        self.stdout.write(self.style.NOTICE('Starting admin user creation process...'))

        # Step 1: Check if init_system has been run (only in Docker environment)
        try:
            from oauth2_provider.models import Application
            
            # Try to query for the OAuth application
            oauth_app = Application.objects.filter(
                client_id='XpjXSgFQQ30AQ9RWpm8NsMULl3pcwIt5i9QfdksJ'
            ).first()
            
            if not oauth_app:
                self.stdout.write(self.style.WARNING('OAuth application not found.'))
                # Check if we're in a Docker environment by checking for PostgreSQL host
                import os
                pg_host = os.environ.get('POSTGRES_HOST', 'localhost')
                
                if pg_host != 'localhost':
                    # We're in Docker, try to run init_system
                    self.stdout.write(self.style.WARNING('Running init_system in Docker environment...'))
                    try:
                        call_command('init_system')
                        self.stdout.write(self.style.SUCCESS('init_system completed successfully.'))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f'Failed to run init_system: {str(e)}'))
                        sys.exit(1)
                else:
                    # We're in local dev, skip init_system
                    self.stdout.write(self.style.WARNING('Skipping init_system (not in Docker environment).'))
                    self.stdout.write(self.style.WARNING('OAuth application will need to be created manually or via Docker.'))
            else:
                self.stdout.write(self.style.SUCCESS('OAuth application exists. System already initialized.'))
                
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Could not verify initialization: {str(e)}'))
            self.stdout.write(self.style.WARNING('Proceeding with user creation only...'))

        # Step 2: Create the admin user
        User = get_user_model()
        
        try:
            # Check if user already exists
            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f'User "{username}" already exists. Updating password...'))
                user = User.objects.get(username=username)
                user.set_password(password)
                user.email = email
                user.is_staff = True
                user.is_superuser = True
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Successfully updated user "{username}" with superuser privileges.'))
            else:
                self.stdout.write(self.style.NOTICE(f'Creating admin user "{username}"...'))
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password
                )
                self.stdout.write(self.style.SUCCESS(f'Successfully created admin user "{username}".'))
            
            # Display user info
            self.stdout.write(self.style.SUCCESS('=' * 50))
            self.stdout.write(self.style.SUCCESS(f'Admin User Details:'))
            self.stdout.write(self.style.SUCCESS(f'  Username: {user.username}'))
            self.stdout.write(self.style.SUCCESS(f'  Email: {user.email}'))
            self.stdout.write(self.style.SUCCESS(f'  Is Staff: {user.is_staff}'))
            self.stdout.write(self.style.SUCCESS(f'  Is Superuser: {user.is_superuser}'))
            self.stdout.write(self.style.SUCCESS('=' * 50))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create admin user: {str(e)}'))
            import traceback
            self.stdout.write(self.style.ERROR(traceback.format_exc()))
            sys.exit(1)

        self.stdout.write(self.style.SUCCESS('Admin user creation process completed successfully.'))

        # Write PGAdmin credentials to .env file in app/backend for Docker Compose
        try:
            import pathlib
            # Save .env in backend directory (same level as backend and node_agent)
            backend_dir = pathlib.Path(__file__).resolve().parents[3] / 'backend'
            env_path = backend_dir / '.env'
            with open(env_path, 'a', encoding='utf-8') as env_file:
                env_file.write(f'\nPGADMIN_DEFAULT_EMAIL={user.email}\n')
                env_file.write(f'PGADMIN_DEFAULT_PASSWORD={password}\n')
            self.stdout.write(self.style.SUCCESS(f'PGAdmin credentials written to {env_path}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to write PGAdmin credentials to {env_path}: {str(e)}'))
