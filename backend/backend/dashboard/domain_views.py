"""
Domain Management API Views
Handles domain CRUD operations and server linking
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from authentication.cookie_oauth2 import CookieOAuth2Authentication
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Domain, DomainCheck, Server
from .serializers import DomainSerializer, DomainCheckSerializer
from .domain_monitor import DomainMonitorService, validate_domain_name
from .logging_utils import (
    log_domain_added, log_domain_removed, log_domain_updated,
    log_domain_verified, log_domain_linked, log_domain_unlinked
)
from django.core.exceptions import ValidationError
import whois
import dns.resolver
import random
import os
from datetime import datetime


class DomainViewSet(viewsets.ModelViewSet):
    """
    ViewSet for domain management
    Handles CRUD operations for domains
    """
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]
    serializer_class = DomainSerializer
    
    def get_queryset(self):
        """Filter domains by current user"""
        return Domain.objects.filter(user=self.request.user).select_related('linked_server')
    
    def perform_create(self, serializer):
        """Set the user when creating a domain"""
        # Validate domain name
        domain_name = serializer.validated_data.get('domain_name')
        try:
            validate_domain_name(domain_name)
        except ValidationError as e:
            raise ValidationError({'domain_name': str(e)})
        
        # Set initial status to pending_verification if not verified
        if not serializer.validated_data.get('is_verified'):
            serializer.validated_data['status'] = 'pending_verification'
        
        domain = serializer.save(user=self.request.user)
        
        # Log domain creation
        log_domain_added(
            domain_name,
            user=self.request.user,
            details={'status': domain.status}
        )
    
    def perform_update(self, serializer):
        """Log when updating a domain"""
        domain = self.get_object()
        old_domain_name = domain.domain_name
        
        # Save the updated domain
        updated_domain = serializer.save()
        
        # Build details about what changed
        changes = []
        if 'domain_name' in serializer.validated_data and serializer.validated_data['domain_name'] != old_domain_name:
            changes.append(f'name: {old_domain_name} → {updated_domain.domain_name}')
        if 'status' in serializer.validated_data:
            changes.append(f'status: {updated_domain.status}')
        
        # Log domain update
        log_domain_updated(
            updated_domain.domain_name,
            user=self.request.user,
            details={'changes': ', '.join(changes) if changes else 'metadata updated'}
        )
    
    def perform_destroy(self, instance):
        """Log when deleting a domain"""
        domain_name = instance.domain_name
        linked_server = instance.linked_server.name if instance.linked_server else None
        
        # Delete the domain
        instance.delete()
        
        # Log domain removal
        log_domain_removed(
            domain_name,
            user=self.request.user,
            details={'linked_server': linked_server} if linked_server else None
        )
    
    @action(detail=True, methods=['post'])
    def link_server(self, request, pk=None):
        """Link a domain to a server"""
        domain = self.get_object()
        server_id = request.data.get('server_id')
        
        if not server_id:
            return Response(
                {'error': 'server_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            server = Server.objects.get(id=server_id, user=request.user)
        except Server.DoesNotExist:
            return Response(
                {'error': 'Server not found or you do not have permission'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Link the domain to the server
        domain.linked_server = server
        domain.save()  # This will automatically convert server to webserver type
        
        # Log domain linking
        log_domain_linked(
            domain.domain_name,
            server.name,
            user=request.user
        )
        
        serializer = self.get_serializer(domain)
        return Response({
            'message': f'Domain {domain.domain_name} linked to server {server.name}',
            'server_converted_to_webserver': server.server_type == 'webserver',
            'domain': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def unlink_server(self, request, pk=None):
        """Unlink a domain from its server"""
        domain = self.get_object()
        
        if not domain.linked_server:
            return Response(
                {'error': 'Domain is not linked to any server'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        server_name = domain.linked_server.name
        domain.linked_server = None
        domain.save()
        
        # Log domain unlinking
        log_domain_unlinked(
            domain.domain_name,
            server_name,
            user=request.user
        )
        
        serializer = self.get_serializer(domain)
        return Response({
            'message': f'Domain {domain.domain_name} unlinked from server {server_name}',
            'domain': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def check_expiry(self, request, pk=None):
        """Manually trigger a domain expiry check"""
        domain = self.get_object()
        
        try:
            service = DomainMonitorService(domain)
            check = service.perform_check()
            
            check_serializer = DomainCheckSerializer(check)
            domain_serializer = self.get_serializer(domain)
            
            return Response({
                'message': 'Domain check completed',
                'check': check_serializer.data,
                'domain': domain_serializer.data
            })
        except Exception as e:
            return Response(
                {'error': f'Failed to check domain: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def check_all(self, request):
        """Check all active domains for the user"""
        results = DomainMonitorService.check_all_domains(request.user)
        
        return Response({
            'message': 'Bulk domain check completed',
            'results': results
        })
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get domain summary statistics"""
        summary = DomainMonitorService.get_domains_summary(request.user)
        
        return Response(summary)
    
    @action(detail=True, methods=['get'])
    def checks(self, request, pk=None):
        """Get check history for a domain"""
        domain = self.get_object()
        checks = DomainCheck.objects.filter(domain=domain).order_by('-timestamp')[:20]
        
        serializer = DomainCheckSerializer(checks, many=True)
        return Response({
            'domain': domain.domain_name,
            'checks': serializer.data
        })
    
    @action(detail=True, methods=['patch'])
    def update_dns(self, request, pk=None):
        """Update DNS records for a domain - only allowed if verified"""
        domain = self.get_object()
        
        # Check if domain is verified
        if not domain.is_verified:
            return Response(
                {'error': 'Domain must be verified before DNS records can be managed'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        dns_records = request.data.get('dns_records')
        
        if dns_records is not None:
            domain.dns_records = dns_records
            domain.save()
            
            serializer = self.get_serializer(domain)
            return Response({
                'message': 'DNS records updated',
                'domain': serializer.data
            })
        
        return Response(
            {'error': 'dns_records field is required'},
            status=status.HTTP_400_BAD_REQUEST
        )


class ServerDomainViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing domains by server
    """
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]
    serializer_class = DomainSerializer
    
    def get_queryset(self):
        """Get domains for a specific server"""
        server_id = self.kwargs.get('server_pk')
        return Domain.objects.filter(
            linked_server_id=server_id,
            linked_server__user=self.request.user,
            is_active=True
        )
    
    @action(detail=False, methods=['get'])
    def stats(self, request, server_pk=None):
        """Get domain stats for a server"""
        server = get_object_or_404(Server, id=server_pk, user=request.user)
        domains = Domain.objects.filter(linked_server=server, is_active=True)
        
        return Response({
            'server': {
                'id': server.id,
                'name': server.name,
                'identifier': server.identifier,
                'type': server.server_type
            },
            'domain_count': domains.count(),
            'domains': DomainSerializer(domains, many=True).data
        })


# WHOIS lookup endpoint
@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def whois_lookup(request):
    """
    Fetch WHOIS information for a domain and generate verification token
    """
    domain_name = request.data.get('domain')
    
    if not domain_name:
        return Response(
            {'error': 'Domain name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Validate domain name
        validate_domain_name(domain_name)
        
        # Perform WHOIS lookup
        domain_info = whois.whois(domain_name)
        
        # Extract relevant information
        whois_data = {
            'domain_name': domain_info.domain_name if isinstance(domain_info.domain_name, str) else domain_info.domain_name[0] if domain_info.domain_name else domain_name,
            'registrar': domain_info.registrar or 'Unknown',
            'creation_date': str(domain_info.creation_date) if domain_info.creation_date else None,
            'expiration_date': str(domain_info.expiration_date) if domain_info.expiration_date else None,
            'updated_date': str(domain_info.updated_date) if domain_info.updated_date else None,
            'name_servers': domain_info.name_servers if domain_info.name_servers else [],
            'status': domain_info.status if domain_info.status else [],
            'emails': domain_info.emails if domain_info.emails else [],
            'registrant_name': domain_info.name if hasattr(domain_info, 'name') else None,
            'registrant_org': domain_info.org if hasattr(domain_info, 'org') else None,
            'registrant_country': domain_info.country if hasattr(domain_info, 'country') else None,
        }
        
        # Generate verification token - always load server_id from file
        verification_token = None
        server_id = None
        
        try:
            serverid_path = os.path.join(os.path.dirname(__file__), 'serverid.dat')
            with open(serverid_path, 'r') as f:
                server_id = f.read().strip()
        except FileNotFoundError:
            pass
        
        if server_id:
            # Clean server ID (remove "local-" prefix if present)
            clean_server_id = str(server_id).replace('local-', '')
            
            # Random words for verification suffix
            random_words = ['dragon', 'drake', 'water', 'fire', 'storm', 'cloud', 'thunder', 'lightning', 'phoenix', 'eagle',
                           'griffin', 'kraken', 'hydra', 'basilisk', 'pegasus', 'wyvern', 'cerberus', 'chimera',
                           'sphinx', 'minotaur', 'cyclops', 'titan', 'earth', 'wind', 'frost', 'shadow', 'light',
                           'blaze', 'ocean', 'mountain', 'forest', 'desert', 'glacier', 'volcano']
            
            # Try to get existing domain from database
            try:
                domain = Domain.objects.get(domain_name=domain_name, user=request.user)
                # If domain already has verification token, use it
                if domain.verification_token:
                    verification_token = domain.verification_token
                else:
                    # Generate new token
                    random_word = random.choice(random_words)
                    verification_token = f"Alterion-domain-verify_{clean_server_id}_{random_word}"
                    domain.verification_token = verification_token
                    domain.save()
            except Domain.DoesNotExist:
                # Domain not in database yet, generate new token
                random_word = random.choice(random_words)
                verification_token = f"Alterion-domain-verify_{clean_server_id}_{random_word}"
        
        return Response({
            'success': True,
            'domain': domain_name,
            'whois': whois_data,
            'verification_token': verification_token
        })
        
    except Exception as e:
        return Response(
            {
                'error': f'Failed to fetch WHOIS data: {str(e)}',
                'domain': domain_name
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Domain verification endpoint
@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def verify_domain(request):
    """
    Verify domain ownership via DNS TXT record or nameserver check
    Checks for: Alterion-domain-verify_<server-id>_<random-word>
    """
    domain_name = request.data.get('domain')
    
    if not domain_name:
        return Response(
            {'error': 'Domain name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Get server ID from file
        serverid_path = os.path.join(os.path.dirname(__file__), 'serverid.dat')
        with open(serverid_path, 'r') as f:
            server_id = f.read().strip()
        
        # Generate or get verification code
        verification_prefix = f"Alterion-domain-verify_{server_id}_"
        
        # Random words for verification suffix
        random_words = ['dragon', 'drake', 'water', 'fire', 'storm', 'cloud', 'thunder', 'lightning', 'phoenix', 'eagle']
        
        # Try to find existing verification in DNS
        verified = False
        verification_method = None
        verification_value = None
        nameservers_checked = []
        txt_records_found = []
        
        try:
            # Check TXT records only
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            
            try:
                txt_records = resolver.resolve(domain_name, 'TXT')
                for record in txt_records:
                    txt_value = record.to_text().strip('"')
                    txt_records_found.append(txt_value)
                    
                    # Check if it matches our verification pattern
                    if txt_value.startswith(verification_prefix):
                        verified = True
                        verification_method = 'txt_record'
                        verification_value = txt_value
                        break
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers):
                pass
                
        except Exception as dns_error:
            # DNS lookup failed, but don't fail the entire request
            pass
        
        # If verified, update domain in database
        if verified:
            try:
                domain = Domain.objects.get(domain_name=domain_name, user=request.user)
                domain.is_verified = True
                domain.verified_at = timezone.now()
                domain.verification_status = f'Verified via {verification_method}'
                domain.update_status()  # This will now check expiry since domain is verified
                domain.save()
                
                # Log domain verification
                log_domain_verified(
                    domain_name,
                    verification_method=verification_method,
                    user=request.user
                )
            except Domain.DoesNotExist:
                # Domain not in database yet, will be created later
                pass
        
        # Generate a suggested verification code if not verified
        suggested_code = None
        if not verified:
            random_word = random.choice(random_words)
            suggested_code = f"{verification_prefix}{random_word}"
        
        return Response({
            'success': True,
            'domain': domain_name,
            'verified': verified,
            'verification_method': verification_method,
            'verification_value': verification_value,
            'suggested_code': suggested_code,
            'txt_records_found': txt_records_found,
            'instructions': {
                'txt_record': f'Add a TXT record with value: {suggested_code}' if suggested_code else 'Domain verified!',
                'note': 'Add the TXT record to verify domain ownership'
            }
        })
        
    except FileNotFoundError:
        return Response(
            {'error': 'Server ID not found'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    except Exception as e:
        return Response(
            {
                'error': f'Failed to verify domain: {str(e)}',
                'domain': domain_name
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Generate or fetch verification tokens for a domain
@api_view(['POST'])
@authentication_classes([CookieOAuth2Authentication])
@permission_classes([IsAuthenticated])
def get_domain_verification_tokens(request):
    """
    Generate or fetch verification tokens for a domain
    Returns TXT record token and nameserver options
    Stores tokens in database for persistence
    """
    import json
    
    domain_name = request.data.get('domain')
    server_id_input = request.data.get('server_id')
    
    if not domain_name:
        return Response(
            {'error': 'Domain name is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not server_id_input:
        return Response(
            {'error': 'Server ID is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Clean server ID (remove "local-" prefix if present)
        server_id = server_id_input.replace('local-', '')
        
        # Random words for verification suffix
        random_words = ['dragon', 'drake', 'water', 'fire', 'storm', 'cloud', 'thunder', 'lightning', 'phoenix', 'eagle',
                       'griffin', 'phoenix', 'kraken', 'hydra', 'basilisk', 'pegasus', 'wyvern', 'cerberus', 'chimera',
                       'sphinx', 'minotaur', 'cyclops', 'titan', 'earth', 'wind', 'thunder', 'frost', 'shadow', 'light',
                       'blaze', 'ocean', 'mountain', 'forest', 'desert', 'glacier', 'volcano']
        
        # Try to get existing domain from database
        try:
            domain = Domain.objects.get(domain_name=domain_name, user=request.user)
            
            # If domain already has verification tokens, return them
            if domain.verification_token and domain.verification_ns:
                ns_records = json.loads(domain.verification_ns) if domain.verification_ns else []
                
                return Response({
                    'success': True,
                    'domain': domain_name,
                    'txt_token': domain.verification_token,
                    'ns_records': ns_records,
                    'is_verified': domain.is_verified,
                    'verified_at': domain.verified_at.isoformat() if domain.verified_at else None
                })
        except Domain.DoesNotExist:
            # Domain not in database yet, will create tokens for it
            domain = None
        
        # Generate new verification tokens
        random_word = random.choice(random_words)
        txt_token = f"Alterion-domain-verify_{server_id}_{random_word}"
        
        # Save to database if domain exists
        if domain:
            domain.verification_token = txt_token
            domain.verification_ns = ''  # Empty since we're only using TXT records
            domain.verification_status = 'pending'
            domain.save()
        
        return Response({
            'success': True,
            'domain': domain_name,
            'txt_token': txt_token,
            'ns_records': [],  # Empty array since we're not using NS verification
            'is_verified': domain.is_verified if domain else False,
            'note': 'Token generated and will be saved when domain is created'
        })
        
    except Exception as e:
        return Response(
            {
                'error': f'Failed to generate verification tokens: {str(e)}',
                'domain': domain_name
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )