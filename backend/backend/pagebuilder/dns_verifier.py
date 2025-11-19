"""
DNS Verification Service
Verifies domain A-records point to the correct server IP before deployment.
"""

import dns.resolver
import dns.exception
import socket
import requests
from typing import Dict, Optional, List
from datetime import datetime


class DNSVerifier:
    """
    Handles DNS verification and domain validation for deployments.
    """
    
    def __init__(self):
        self.resolver = dns.resolver.Resolver()
        self.resolver.timeout = 5
        self.resolver.lifetime = 5
    
    def verify_domain(self, domain: str, expected_ip: str) -> Dict:
        """
        Verify that domain's A-record points to expected IP.
        
        Args:
            domain: Domain name to verify (e.g., example.com)
            expected_ip: Expected IP address
            
        Returns:
            Dict with verification results
        """
        result = {
            'domain': domain,
            'expected_ip': expected_ip,
            'actual_ip': None,
            'verified': False,
            'message': '',
            'timestamp': datetime.utcnow().isoformat(),
            'additional_records': []
        }
        
        try:
            # Query A records
            answers = self.resolver.resolve(domain, 'A')
            ips = [str(rdata) for rdata in answers]
            
            result['actual_ip'] = ips[0] if ips else None
            result['additional_records'] = ips[1:] if len(ips) > 1 else []
            
            # Check if expected IP is in the list
            if expected_ip in ips:
                result['verified'] = True
                result['message'] = f"Domain {domain} correctly points to {expected_ip}"
            else:
                result['message'] = (
                    f"Domain {domain} points to {result['actual_ip']}, "
                    f"but expected {expected_ip}"
                )
        
        except dns.resolver.NXDOMAIN:
            result['message'] = f"Domain {domain} does not exist"
        
        except dns.resolver.NoAnswer:
            result['message'] = f"No A record found for {domain}"
        
        except dns.resolver.Timeout:
            result['message'] = f"DNS query timeout for {domain}"
        
        except Exception as e:
            result['message'] = f"DNS verification error: {str(e)}"
        
        return result
    
    def get_server_public_ip(self) -> Optional[str]:
        """
        Get the public IP address of this server.
        
        Returns:
            Public IP address or None if unable to determine
        """
        try:
            # Try multiple services for reliability
            services = [
                'https://api.ipify.org',
                'https://ifconfig.me/ip',
                'https://icanhazip.com',
            ]
            
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        ip = response.text.strip()
                        # Validate it's a valid IP
                        socket.inet_aton(ip)
                        return ip
                except Exception:
                    continue
            
            return None
        
        except Exception:
            return None
    
    def check_domain_reachability(self, domain: str, port: int = 80) -> Dict:
        """
        Check if domain is reachable on specified port.
        
        Args:
            domain: Domain name
            port: Port to check (default 80)
            
        Returns:
            Dict with reachability status
        """
        result = {
            'domain': domain,
            'port': port,
            'reachable': False,
            'message': ''
        }
        
        try:
            # Try to establish connection
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((domain, port))
            sock.close()
            
            result['reachable'] = True
            result['message'] = f"{domain}:{port} is reachable"
        
        except socket.timeout:
            result['message'] = f"Connection to {domain}:{port} timed out"
        
        except ConnectionRefusedError:
            result['message'] = f"Connection to {domain}:{port} refused"
        
        except socket.gaierror:
            result['message'] = f"Could not resolve {domain}"
        
        except Exception as e:
            result['message'] = f"Connection error: {str(e)}"
        
        return result
    
    def get_all_dns_records(self, domain: str) -> Dict:
        """
        Get all DNS records for a domain (A, AAAA, CNAME, MX, TXT).
        
        Args:
            domain: Domain name
            
        Returns:
            Dict with all DNS records
        """
        records = {
            'domain': domain,
            'A': [],
            'AAAA': [],
            'CNAME': [],
            'MX': [],
            'TXT': [],
            'NS': []
        }
        
        record_types = ['A', 'AAAA', 'CNAME', 'MX', 'TXT', 'NS']
        
        for record_type in record_types:
            try:
                answers = self.resolver.resolve(domain, record_type)
                records[record_type] = [str(rdata) for rdata in answers]
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.Timeout):
                pass
            except Exception:
                pass
        
        return records
    
    def verify_subdomain(self, subdomain: str, root_domain: str, expected_ip: str) -> Dict:
        """
        Verify subdomain points to expected IP.
        
        Args:
            subdomain: Subdomain (e.g., api)
            root_domain: Root domain (e.g., example.com)
            expected_ip: Expected IP address
            
        Returns:
            Dict with verification results
        """
        full_domain = f"{subdomain}.{root_domain}" if subdomain else root_domain
        return self.verify_domain(full_domain, expected_ip)
    
    def suggest_dns_configuration(self, domain: str, server_ip: str) -> Dict:
        """
        Generate DNS configuration suggestions.
        
        Args:
            domain: Domain name
            server_ip: Server IP address
            
        Returns:
            Dict with DNS configuration instructions
        """
        return {
            'domain': domain,
            'server_ip': server_ip,
            'records': [
                {
                    'type': 'A',
                    'name': '@',
                    'value': server_ip,
                    'ttl': 3600,
                    'description': 'Root domain A record'
                },
                {
                    'type': 'A',
                    'name': 'www',
                    'value': server_ip,
                    'ttl': 3600,
                    'description': 'WWW subdomain A record'
                },
                {
                    'type': 'CNAME',
                    'name': 'api',
                    'value': domain,
                    'ttl': 3600,
                    'description': 'API subdomain (optional)'
                }
            ],
            'instructions': [
                '1. Log in to your domain registrar or DNS provider',
                '2. Navigate to DNS management section',
                f'3. Add an A record pointing @ to {server_ip}',
                f'4. Add an A record pointing www to {server_ip}',
                '5. Wait 5-60 minutes for DNS propagation',
                '6. Return here to verify the configuration'
            ]
        }
    
    def bulk_verify_domains(self, domains: List[Dict[str, str]]) -> List[Dict]:
        """
        Verify multiple domains at once.
        
        Args:
            domains: List of dicts with 'domain' and 'expected_ip' keys
            
        Returns:
            List of verification results
        """
        results = []
        
        for domain_config in domains:
            domain = domain_config.get('domain')
            expected_ip = domain_config.get('expected_ip')
            
            if domain and expected_ip:
                result = self.verify_domain(domain, expected_ip)
                results.append(result)
        
        return results
    
    def check_ssl_certificate(self, domain: str, port: int = 443) -> Dict:
        """
        Check SSL certificate status for a domain.
        
        Args:
            domain: Domain name
            port: SSL port (default 443)
            
        Returns:
            Dict with SSL certificate information
        """
        import ssl
        import datetime
        
        result = {
            'domain': domain,
            'port': port,
            'has_ssl': False,
            'valid': False,
            'issuer': None,
            'expires': None,
            'message': ''
        }
        
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, port), timeout=5) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    result['has_ssl'] = True
                    result['issuer'] = dict(x[0] for x in cert['issuer'])
                    
                    # Parse expiration date
                    not_after = cert['notAfter']
                    expire_date = datetime.datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z')
                    result['expires'] = expire_date.isoformat()
                    
                    # Check if certificate is still valid
                    if expire_date > datetime.datetime.now():
                        result['valid'] = True
                        result['message'] = f"Valid SSL certificate (expires {expire_date.date()})"
                    else:
                        result['message'] = f"SSL certificate expired on {expire_date.date()}"
        
        except ssl.SSLError as e:
            result['message'] = f"SSL error: {str(e)}"
        
        except socket.timeout:
            result['message'] = f"Connection to {domain}:{port} timed out"
        
        except Exception as e:
            result['message'] = f"SSL check error: {str(e)}"
        
        return result
