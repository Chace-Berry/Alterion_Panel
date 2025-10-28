

import whois
import logging
import ssl
import socket
from datetime import timedelta, datetime
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Domain, DomainCheck

logger = logging.getLogger(__name__)


class DomainMonitorService:
    
    
    def __init__(self, domain):
        self.domain = domain
    
    def check_domain_expiry(self):
        
        try:

            domain_info = whois.whois(self.domain.domain_name)

            expiry_date = None
            if hasattr(domain_info, 'expiration_date') and domain_info.expiration_date:
                if isinstance(domain_info.expiration_date, list):

                    expiry_date = domain_info.expiration_date[0]
                else:
                    expiry_date = domain_info.expiration_date

            registrar = ''
            if hasattr(domain_info, 'registrar') and domain_info.registrar:
                if isinstance(domain_info.registrar, list):
                    registrar = domain_info.registrar[0] if domain_info.registrar else ''
                else:
                    registrar = str(domain_info.registrar)

            if expiry_date:
                if expiry_date.tzinfo is None:
                    expiry_date = timezone.make_aware(expiry_date)
            
            return True, expiry_date, registrar, ""
            
        except whois.parser.PywhoisError as e:
            logger.warning(f"WHOIS lookup failed for {self.domain.domain_name}: {e}")
            return False, None, "", f"WHOIS lookup failed: {str(e)}"
        except Exception as e:
            logger.error(f"Domain check error for {self.domain.domain_name}: {e}")
            return False, None, "", f"Domain check error: {str(e)}"
    
    def check_ssl_certificate(self):
        """
        Fetch SSL certificate from a live website and extract expiry date
        Returns: (success, ssl_expiry_date, error_message)
        """
        try:
            # Parse domain name - remove port if present
            domain_name = self.domain.domain_name.split(':')[0]
            port = 443  # Default HTTPS port
            
            # Check if domain has custom port
            if ':' in self.domain.domain_name:
                try:
                    port = int(self.domain.domain_name.split(':')[1])
                except ValueError:
                    port = 443
            
            # Create SSL context
            context = ssl.create_default_context()
            
            # Connect to the domain and get certificate
            with socket.create_connection((domain_name, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain_name) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Extract expiry date from certificate
                    # Certificate date format: 'Dec 31 19:54:57 2027 GMT'
                    not_after = cert.get('notAfter')
                    if not_after:
                        # Parse the date string
                        expiry_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                        # Make it timezone-aware
                        expiry_date = timezone.make_aware(expiry_date)
                        
                        return True, expiry_date, ""
                    else:
                        return False, None, "Certificate has no expiry date"
                        
        except socket.gaierror as e:
            logger.warning(f"SSL check failed for {self.domain.domain_name}: DNS resolution error")
            return False, None, f"DNS resolution failed: {str(e)}"
        except socket.timeout:
            logger.warning(f"SSL check failed for {self.domain.domain_name}: Connection timeout")
            return False, None, "Connection timeout"
        except ssl.SSLError as e:
            logger.warning(f"SSL check failed for {self.domain.domain_name}: SSL error")
            return False, None, f"SSL error: {str(e)}"
        except Exception as e:
            logger.error(f"SSL check error for {self.domain.domain_name}: {e}")
            return False, None, f"SSL check error: {str(e)}"
    
    def perform_check(self):
        """
        Perform domain expiry check and SSL certificate check
        """
        success, expiry_date, registrar, error_message = self.check_domain_expiry()
        
        # Also check SSL certificate if domain has SSL enabled
        ssl_success = False
        ssl_expiry = None
        ssl_error = ""
        
        if self.domain.ssl_enabled:
            ssl_success, ssl_expiry, ssl_error = self.check_ssl_certificate()

        check = DomainCheck.objects.create(
            domain=self.domain,
            expiry_date_found=expiry_date,
            registrar_found=registrar,
            check_successful=success,
            error_message=error_message if error_message else ssl_error
        )

        if success:
            if expiry_date:
                self.domain.expiry_date = expiry_date
            if registrar:
                self.domain.registrar = registrar
            self.domain.last_checked = timezone.now()
            self.domain.update_status()
        
        # Update SSL expiry separately
        if ssl_success and ssl_expiry:
            self.domain.ssl_expiry = ssl_expiry
            self.domain.save()
        
        return check
    
    def get_domain_status(self):
        
        days_remaining = self.domain.days_until_expiry
        
        return {
            'domain_name': self.domain.domain_name,
            'expiry_date': self.domain.expiry_date.isoformat() if self.domain.expiry_date else None,
            'days_remaining': days_remaining,
            'status': self.domain.status,
            'registrar': self.domain.registrar,
            'last_checked': self.domain.last_checked.isoformat() if self.domain.last_checked else None,
        }
    
    @classmethod
    def get_domains_summary(cls, user):
        
        from django.db.models import Count, Q
        
        domains = Domain.objects.filter(user=user, is_active=True)
        
        summary = {
            'total_domains': domains.count(),
            'status_breakdown': {
                'active': domains.filter(status='active').count(),
                'warning': domains.filter(status='warning').count(),
                'critical': domains.filter(status='critical').count(),
                'expired': domains.filter(status='expired').count(),
                'unknown': domains.filter(status='unknown').count(),
            },
            'expiring_soon': domains.filter(
                status__in=['warning', 'critical'],
                expiry_date__isnull=False
            ).order_by('expiry_date')[:5].values(
                'domain_name', 'expiry_date', 'status', 'registrar'
            ),
            'needs_check': domains.filter(
                Q(last_checked__isnull=True) | 
                Q(last_checked__lt=timezone.now() - timedelta(hours=24))
            ).count()
        }
        
        return summary
    
    @classmethod
    def check_all_domains(cls, user):
        
        domains = Domain.objects.filter(
            user=user, 
            is_active=True,
            last_checked__lt=timezone.now() - timedelta(hours=12)  # Only check if last check was > 12 hours ago
        )
        
        results = []
        for domain in domains:
            try:
                service = cls(domain)
                check = service.perform_check()
                results.append({
                    'domain': domain.domain_name,
                    'success': check.check_successful,
                    'status': domain.status,
                    'days_remaining': domain.days_until_expiry
                })
            except Exception as e:
                logger.error(f"Failed to check domain {domain.domain_name}: {e}")
                results.append({
                    'domain': domain.domain_name,
                    'success': False,
                    'error': str(e)
                })
        
        return results


def validate_domain_name(domain_name):
    
    import re

    pattern = r'^([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$'
    
    if not re.match(pattern, domain_name):
        raise ValidationError(f"Invalid domain name format: {domain_name}")

    if len(domain_name) > 253:
        raise ValidationError("Domain name too long")
    
    return True


class DomainExpiryNotifier:
    
    
    @classmethod
    def get_expiring_domains(cls, user, days_threshold=30):
        
        threshold_date = timezone.now() + timedelta(days=days_threshold)
        
        return Domain.objects.filter(
            user=user,
            is_active=True,
            expiry_date__lte=threshold_date,
            expiry_date__gt=timezone.now(),
            status__in=['warning', 'critical']
        ).order_by('expiry_date')
    
    @classmethod
    def create_expiry_alerts(cls, user):
        
        from .alert_system import AlertSystem
        
        expiring_domains = cls.get_expiring_domains(user, days_threshold=30)
        alert_system = AlertSystem()
        
        alerts_created = 0
        for domain in expiring_domains:
            days_remaining = domain.days_until_expiry
            
            if days_remaining <= 7:
                level = 'critical'
                message = f"Domain {domain.domain_name} expires in {days_remaining} days!"
            elif days_remaining <= 30:
                level = 'warning' 
                message = f"Domain {domain.domain_name} expires in {days_remaining} days"
            else:
                continue

            from .models import Alert
            recent_alert = Alert.objects.filter(
                message__icontains=domain.domain_name,
                created_at__gte=timezone.now() - timedelta(days=1),
                resolved=False
            ).first()
            
            if not recent_alert:
                alert_system.create_alert(
                    message=message,
                    level=level,
                    alert_type='domain_expiry',
                    details={'domain': domain.domain_name, 'days_remaining': days_remaining}
                )
                alerts_created += 1
        
        return alerts_created