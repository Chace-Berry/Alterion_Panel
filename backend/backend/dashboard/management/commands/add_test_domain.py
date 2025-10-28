"""
Management command to add a test verified domain
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from services.models import Domain
from datetime import timedelta
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import os

User = get_user_model()

class Command(BaseCommand):
    help = 'Add test verified domain localhost:13527'

    def get_ssl_expiry(self, cert_path):
        """Extract expiry date from SSL certificate"""
        try:
            with open(cert_path, 'rb') as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data, default_backend())
            expiry = cert.not_valid_after_utc
            
            # Convert to timezone-aware datetime
            return timezone.make_aware(expiry) if timezone.is_naive(expiry) else expiry
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Failed to read SSL certificate: {str(e)}'))
            return None

    def handle(self, *args, **options):
        # Get the first user (or create one if none exists)
        user = User.objects.first()
        if not user:
            self.stdout.write(self.style.ERROR('No users found. Please create a user first.'))
            return

        # Get SSL certificate path - go up from commands -> management -> dashboard to backend/backend
        # __file__ is: backend/backend/dashboard/management/commands/add_test_domain.py
        # We need: backend/backend/localhost.pem
        current_dir = os.path.dirname(__file__)  # commands/
        management_dir = os.path.dirname(current_dir)  # management/
        dashboard_dir = os.path.dirname(management_dir)  # dashboard/
        backend_backend_dir = os.path.dirname(dashboard_dir)  # backend/backend/
        ssl_cert_path = os.path.join(backend_backend_dir, 'localhost.pem')
        
        # Extract SSL certificate expiry
        ssl_expiry = self.get_ssl_expiry(ssl_cert_path)
        
        # Check if domain already exists
        domain_name = 'localhost:13527'
        
        domain, created = Domain.objects.get_or_create(
            domain_name=domain_name,
            user=user,
            defaults={
                'is_verified': True,
                'verified_at': timezone.now(),
                'verification_status': 'Verified via txt_record',
                'verification_token': 'Alterion-domain-verify_test_localhost',
                'status': 'active',
                'is_active': True,
                'ssl_enabled': True,
                'registrar': 'Test Domain',
                'web_root': '/var/www/localhost',
                'expiry_date': ssl_expiry,  # Use SSL cert expiry as domain expiry
                'ssl_expiry': ssl_expiry,    # Also store in ssl_expiry field
                'last_checked': timezone.now(),
            }
        )

        if created:
            self.stdout.write(self.style.SUCCESS(f'Successfully created test domain: {domain_name}'))
            self.stdout.write(f'  - Verified: {domain.is_verified}')
            self.stdout.write(f'  - Status: {domain.status}')
            self.stdout.write(f'  - SSL Enabled: {domain.ssl_enabled}')
            self.stdout.write(f'  - Web Root: {domain.web_root}')
            self.stdout.write(f'  - SSL Cert Path: {ssl_cert_path}')
            self.stdout.write(f'  - SSL Expiry Date: {domain.ssl_expiry}')
            self.stdout.write(f'  - Domain Expiry Date: {domain.expiry_date}')
            self.stdout.write(f'  - Days Remaining: {domain.days_until_expiry}')
        else:
            # Update existing domain with SSL expiry
            domain.is_verified = True
            domain.verified_at = timezone.now()
            domain.verification_status = 'Verified via txt_record'
            domain.verification_token = 'Alterion-domain-verify_test_localhost'
            domain.status = 'active'
            domain.is_active = True
            domain.ssl_enabled = True
            domain.web_root = '/var/www/localhost'
            domain.expiry_date = ssl_expiry  # Use SSL cert expiry
            domain.ssl_expiry = ssl_expiry
            domain.last_checked = timezone.now()
            domain.save()
            self.stdout.write(self.style.SUCCESS(f'Updated existing test domain: {domain_name}'))
            self.stdout.write(f'  - SSL Cert Path: {ssl_cert_path}')
            self.stdout.write(f'  - SSL Expiry Date: {domain.ssl_expiry}')
            self.stdout.write(f'  - Domain Expiry Date: {domain.expiry_date}')
            self.stdout.write(f'  - Days Remaining: {domain.days_until_expiry}')

