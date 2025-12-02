"""
Initialize Alterion Panel system on first startup:
1. Create PostgreSQL database user and database
2. Ensure OAuth2 application exists with fixed client_id
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


class Command(BaseCommand):
    help = 'Initialize Alterion Panel system (create PostgreSQL user/database and OAuth2 application)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-only',
            action='store_true',
            help='Only create PostgreSQL user and database',
        )
        parser.add_argument(
            '--oauth-only',
            action='store_true',
            help='Only create OAuth2 application (requires migrations to be run first)',
        )

    def handle(self, *args, **options):
        from django.db import connection
        
        db_only = options.get('db_only', False)
        oauth_only = options.get('oauth_only', False)
        
        if not db_only and not oauth_only:
            # Run both if no flags specified
            self.stdout.write(self.style.SUCCESS('[INIT] Starting full system initialization...'))
            
            # Only create DB if it doesn't exist
            if self.should_create_database():
                self.create_postgres_user_and_db()
                self.stdout.write('[INIT] Resetting database connection...')
                connection.close()
            else:
                self.stdout.write(self.style.WARNING('[INIT] Database already exists, skipping creation...'))
            
            self.ensure_oauth_application()
            self.stdout.write(self.style.SUCCESS('[INIT] System initialization complete!'))
        elif db_only:
            self.stdout.write(self.style.SUCCESS('[INIT] Creating PostgreSQL user and database...'))
            
            # Check if database exists before creating
            if self.should_create_database():
                self.create_postgres_user_and_db()
                self.stdout.write(self.style.SUCCESS('[INIT] PostgreSQL initialization complete!'))
            else:
                self.stdout.write(self.style.WARNING('[INIT] Database already exists, skipping creation...'))
        elif oauth_only:
            self.stdout.write(self.style.SUCCESS('[INIT] Setting up OAuth2 application...'))
            self.ensure_oauth_application()
            self.stdout.write(self.style.SUCCESS('[INIT] OAuth2 setup complete!'))

    def should_create_database(self):
        """Try to connect to the target DB as the intended user and check for a required table. If fails, create DB/user."""
        import os
        db_user = settings.DB_USER
        db_name = settings.DB_NAME
        db_password = settings.DB_PASSWORD
        pg_host = settings.DATABASES['default']['HOST']
        pg_port = settings.DATABASES['default']['PORT']
        required_table = getattr(settings, 'REQUIRED_DB_TABLE', 'auth_user')  # Default to Django's user table
        try:
            conn = psycopg2.connect(
                host=pg_host,
                port=pg_port,
                user=db_user,
                password=db_password,
                database=db_name
            )
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = %s", (required_table,))
            table_exists = cur.fetchone()
            cur.close()
            conn.close()
            if table_exists:
                self.stdout.write(self.style.SUCCESS(f'[INIT] Table {required_table} exists in DB {db_name}. Skipping creation.'))
                return False
            else:
                self.stdout.write(self.style.WARNING(f'[INIT] Table {required_table} does not exist in DB {db_name}. Will create DB/user.'))
                return True
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'[INIT] Could not connect to DB {db_name} as user {db_user}: {str(e)}'))
            return True

    def create_postgres_user_and_db(self):
        """Create PostgreSQL user and database if they don't exist"""
        import os
        
        db_user = settings.DB_USER
        db_name = settings.DB_NAME
        db_password = settings.DB_PASSWORD
        pg_host = settings.DATABASES['default']['HOST']
        pg_port = settings.DATABASES['default']['PORT']
        
        self.stdout.write(f'[INIT] Connecting to PostgreSQL as postgres user...')
        
        try:
            # Connect as postgres superuser to create user and database
            conn = psycopg2.connect(
                host=pg_host,
                port=pg_port,
                user='postgres',
                password=os.environ.get('POSTGRES_PASSWORD', 'postgres'),
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Check if user exists
            cursor.execute(
                "SELECT 1 FROM pg_roles WHERE rolname = %s",
                (db_user,)
            )
            user_exists = cursor.fetchone()
            
            if not user_exists:
                self.stdout.write(f'[INIT] Creating PostgreSQL user: {db_user}')
                cursor.execute(
                    sql.SQL("CREATE USER {} WITH PASSWORD %s").format(sql.Identifier(db_user)),
                    (db_password,)
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Created user: {db_user}'))
            else:
                self.stdout.write(f'✓ User already exists: {db_user}')
                # Update password in case it changed
                cursor.execute(
                    sql.SQL("ALTER USER {} WITH PASSWORD %s").format(sql.Identifier(db_user)),
                    (db_password,)
                )
            
            # Check if database exists
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s",
                (db_name,)
            )
            db_exists = cursor.fetchone()
            
            if not db_exists:
                self.stdout.write(f'[INIT] Creating database: {db_name}')
                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(db_name),
                        sql.Identifier(db_user)
                    )
                )
                self.stdout.write(self.style.SUCCESS(f'✓ Created database: {db_name}'))
            else:
                self.stdout.write(f'✓ Database already exists: {db_name}')
            
            # Grant all privileges
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {}").format(
                    sql.Identifier(db_name),
                    sql.Identifier(db_user)
                )
            )
            
            cursor.close()
            conn.close()
            
            self.stdout.write(self.style.SUCCESS('[INIT] PostgreSQL setup complete'))
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[INIT] PostgreSQL setup failed: {str(e)}')
            )
            self.stdout.write(
                self.style.WARNING('[INIT] Make sure PostgreSQL is running and postgres user password is set')
            )
            raise

    def ensure_oauth_application(self):
        """Ensure OAuth2 application exists with fixed client_id"""
        from oauth2_provider.models import Application
        from django.contrib.auth import get_user_model
        
        FIXED_CLIENT_ID = 'XpjXSgFQQ30AQ9RWpm8NsMULl3pcwIt5i9QfdksJ'
        
        self.stdout.write('[INIT] Checking OAuth2 application...')
        
        try:
            # Check if application exists
            app = Application.objects.filter(client_id=FIXED_CLIENT_ID).first()
            
            if not app:
                self.stdout.write(f'[INIT] Creating OAuth2 application with client_id: {FIXED_CLIENT_ID}')
                
                # Get or create a system user
                User = get_user_model()
                system_user = User.objects.filter(username='system').first()
                if not system_user:
                    system_user = User.objects.create_user(
                        username='system',
                        email='system@alterion.local',
                        password=settings.SECRET_KEY
                    )
                
                # Create application
                app = Application.objects.create(
                    client_id=FIXED_CLIENT_ID,
                    user=system_user,
                    client_type=Application.CLIENT_PUBLIC,
                    authorization_grant_type=Application.GRANT_PASSWORD,
                    name='Alterion Panel',
                    skip_authorization=True
                )
                
                self.stdout.write(self.style.SUCCESS(f'✓ Created OAuth2 application: {FIXED_CLIENT_ID}'))
            else:
                self.stdout.write(f'✓ OAuth2 application already exists: {FIXED_CLIENT_ID}')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'[INIT] OAuth2 application setup failed: {str(e)}')
            )
            raise
