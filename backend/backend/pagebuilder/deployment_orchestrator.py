"""
Deployment Orchestration System
Coordinates the full deployment workflow: validation, NGINX config, backend startup, frontend deploy.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime
import hashlib

from .backend_detector import BackendDetector
from .dns_verifier import DNSVerifier
from .nginx_generator import NginxConfigGenerator
from .process_manager import ProcessManager


class DeploymentOrchestrator:
    """
    Orchestrates the complete deployment process for full-stack applications.
    """
    
    def __init__(self, 
                 deployment_root: str = "/var/www",
                 nginx_sites_available: str = "/etc/nginx/sites-available",
                 nginx_sites_enabled: str = "/etc/nginx/sites-enabled"):
        """
        Initialize deployment orchestrator.
        
        Args:
            deployment_root: Root directory for deployed applications
            nginx_sites_available: NGINX sites-available directory
            nginx_sites_enabled: NGINX sites-enabled directory
        """
        self.deployment_root = Path(deployment_root)
        self.dns_verifier = DNSVerifier()
        self.nginx_generator = NginxConfigGenerator(nginx_sites_available, nginx_sites_enabled)
        self.process_manager = ProcessManager()
    
    def deploy_project(self,
                      project_id: str,
                      project_name: str,
                      frontend_dist_path: str,
                      backend_path: Optional[str] = None,
                      domain: Optional[str] = None,
                      expected_ip: Optional[str] = None,
                      ssl_enabled: bool = False,
                      ssl_cert_path: str = "",
                      ssl_key_path: str = "",
                      verify_dns: bool = True,
                      restart_backend: bool = True) -> Dict:
        """
        Execute complete deployment workflow.
        
        Args:
            project_id: Unique project identifier
            project_name: Project name
            frontend_dist_path: Path to frontend dist folder
            backend_path: Path to backend folder (optional)
            domain: Domain name (optional)
            expected_ip: Expected server IP (optional)
            ssl_enabled: Enable SSL
            ssl_cert_path: Path to SSL certificate
            ssl_key_path: Path to SSL private key
            verify_dns: Whether to verify DNS before deploying
            restart_backend: Whether to restart backend if already running
            
        Returns:
            Dict with deployment results
        """
        deployment_log = []
        result = {
            'success': False,
            'logs': [],
            'deployment_path': None,
            'nginx_config': None,
            'backend_pid': None,
            'errors': []
        }
        
        def log(message: str, level: str = "info"):
            """Helper to add log entries"""
            entry = f"[{datetime.now().strftime('%H:%M:%S')}] [{level.upper()}] {message}"
            deployment_log.append(entry)
            result['logs'].append(entry)
        
        try:
            # Step 1: Validate frontend path
            log("Validating frontend files...", "info")
            if not Path(frontend_dist_path).exists():
                log(f"Frontend dist path does not exist: {frontend_dist_path}", "error")
                result['errors'].append("Frontend dist path not found")
                return result
            
            # Check for index.html
            index_html = Path(frontend_dist_path) / "index.html"
            if not index_html.exists():
                log("Warning: index.html not found in dist folder", "warning")
            
            log("Frontend validation successful", "success")
            
            # Step 2: DNS Verification (if domain provided)
            dns_verified = False
            if domain and verify_dns:
                log(f"Verifying DNS for domain {domain}...", "info")
                
                # Get server IP if not provided
                if not expected_ip:
                    expected_ip = self.dns_verifier.get_server_public_ip()
                    if expected_ip:
                        log(f"Detected server IP: {expected_ip}", "info")
                    else:
                        log("Warning: Could not detect server IP", "warning")
                
                if expected_ip:
                    dns_result = self.dns_verifier.verify_domain(domain, expected_ip)
                    if dns_result['verified']:
                        log(f"DNS verified: {domain} -> {expected_ip}", "success")
                        dns_verified = True
                    else:
                        log(f"DNS verification failed: {dns_result['message']}", "error")
                        result['errors'].append(f"DNS verification failed: {dns_result['message']}")
                        # Don't return here - allow deployment to continue without DNS
            
            # Step 3: Backend Detection and Configuration (if backend provided)
            backend_config = None
            if backend_path and Path(backend_path).exists():
                log("Detecting backend framework...", "info")
                
                try:
                    detector = BackendDetector(backend_path)
                    backend_config = detector.detect_framework()
                    
                    log(f"Detected framework: {backend_config['framework']} "
                        f"(confidence: {backend_config['confidence']:.2%})", "success")
                    log(f"Found {len(backend_config['detected_apis'])} APIs", "info")
                    log(f"Found {len(backend_config['detected_models'])} models", "info")
                except Exception as e:
                    log(f"Backend detection error: {str(e)}", "error")
                    result['errors'].append(f"Backend detection failed: {str(e)}")
            
            # Step 4: Deploy Frontend
            log("Deploying frontend files...", "info")
            
            # Create project deployment directory
            project_deploy_path = self.deployment_root / project_name
            frontend_deploy_path = project_deploy_path / "dist"
            
            try:
                # Remove existing deployment if present
                if frontend_deploy_path.exists():
                    log("Removing existing frontend deployment...", "info")
                    shutil.rmtree(frontend_deploy_path)
                
                # Create directory structure
                frontend_deploy_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy frontend files
                shutil.copytree(frontend_dist_path, frontend_deploy_path)
                log(f"Frontend deployed to {frontend_deploy_path}", "success")
                result['deployment_path'] = str(frontend_deploy_path)
            
            except Exception as e:
                log(f"Frontend deployment error: {str(e)}", "error")
                result['errors'].append(f"Frontend deployment failed: {str(e)}")
                return result
            
            # Step 5: Start/Restart Backend (if configured)
            backend_pid = None
            backend_port = None
            
            if backend_config and backend_config['framework'] != 'other':
                log(f"Starting {backend_config['framework']} backend...", "info")
                
                backend_port = backend_config.get('port', 8000)
                
                # Check if backend is already running
                if restart_backend:
                    existing_status = self.process_manager.get_process_status(project_id)
                    if existing_status.get('running'):
                        log(f"Restarting existing backend (PID {existing_status['pid']})...", "info")
                        restart_result = self.process_manager.restart_backend(project_id)
                        if restart_result['success']:
                            backend_pid = restart_result['pid']
                            log(f"Backend restarted successfully (PID {backend_pid})", "success")
                        else:
                            log(f"Backend restart failed: {restart_result['message']}", "error")
                else:
                    # Start new backend process
                    start_result = self.process_manager.start_backend(
                        project_id=project_id,
                        framework=backend_config['framework'],
                        backend_path=backend_path,
                        start_command=backend_config['suggested_start_command'],
                        port=backend_port
                    )
                    
                    if start_result['success']:
                        backend_pid = start_result['pid']
                        log(f"Backend started on port {backend_port} (PID {backend_pid})", "success")
                        result['backend_pid'] = backend_pid
                        
                        # Health check
                        import time
                        time.sleep(3)  # Wait for backend to start
                        health = self.process_manager.health_check(backend_port)
                        if health['healthy']:
                            log(f"Backend health check passed ({health['response_time']}ms)", "success")
                        else:
                            log(f"Backend health check warning: {health['message']}", "warning")
                    else:
                        log(f"Backend start failed: {start_result['message']}", "error")
                        result['errors'].append(f"Backend failed to start: {start_result['message']}")
            
            # Step 6: Generate and Apply NGINX Configuration (if domain provided)
            if domain:
                log("Generating NGINX configuration...", "info")
                
                try:
                    nginx_config = self.nginx_generator.generate_config(
                        project_name=project_name,
                        domain=domain,
                        frontend_path=str(frontend_deploy_path),
                        backend_port=backend_port or 8000,
                        ssl_enabled=ssl_enabled,
                        ssl_cert_path=ssl_cert_path,
                        ssl_key_path=ssl_key_path,
                        enable_websocket=True,  # Enable by default
                        enable_cors=True  # Enable by default
                    )
                    
                    # Write NGINX config
                    config_path = self.nginx_generator.write_config(domain, nginx_config)
                    log(f"NGINX config written to {config_path}", "success")
                    result['nginx_config'] = config_path
                    
                    # Enable site
                    self.nginx_generator.enable_site(domain)
                    log(f"NGINX site enabled for {domain}", "success")
                    
                    # Test NGINX configuration
                    test_result = self.nginx_generator.test_config()
                    if test_result['success']:
                        log("NGINX configuration test passed", "success")
                        
                        # Reload NGINX
                        reload_result = self.nginx_generator.reload_nginx()
                        if reload_result['success']:
                            log("NGINX reloaded successfully", "success")
                        else:
                            log(f"NGINX reload warning: {reload_result['error']}", "warning")
                    else:
                        log(f"NGINX configuration test failed: {test_result['error']}", "error")
                        result['errors'].append(f"NGINX config invalid: {test_result['error']}")
                
                except Exception as e:
                    log(f"NGINX configuration error: {str(e)}", "error")
                    result['errors'].append(f"NGINX configuration failed: {str(e)}")
            
            # Step 7: Final Status
            if len(result['errors']) == 0:
                log("Deployment completed successfully!", "success")
                result['success'] = True
            else:
                log(f"Deployment completed with {len(result['errors'])} errors", "warning")
        
        except Exception as e:
            log(f"Deployment error: {str(e)}", "error")
            result['errors'].append(str(e))
        
        return result
    
    def rollback_deployment(self, project_id: str, project_name: str, domain: Optional[str] = None) -> Dict:
        """
        Rollback a deployment.
        
        Args:
            project_id: Project identifier
            project_name: Project name
            domain: Domain name (optional)
            
        Returns:
            Dict with rollback results
        """
        result = {
            'success': False,
            'message': '',
            'stopped_backend': False,
            'removed_nginx': False,
            'removed_files': False
        }
        
        try:
            # Stop backend
            stop_result = self.process_manager.stop_backend(project_id, force=True)
            result['stopped_backend'] = stop_result['success']
            
            # Remove NGINX configuration
            if domain:
                self.nginx_generator.remove_config(domain)
                self.nginx_generator.reload_nginx()
                result['removed_nginx'] = True
            
            # Remove deployed files
            project_deploy_path = self.deployment_root / project_name
            if project_deploy_path.exists():
                shutil.rmtree(project_deploy_path)
                result['removed_files'] = True
            
            result['success'] = True
            result['message'] = "Rollback completed successfully"
        
        except Exception as e:
            result['message'] = f"Rollback error: {str(e)}"
        
        return result
    
    def get_deployment_status(self, project_id: str) -> Dict:
        """Get current deployment status"""
        return self.process_manager.get_process_status(project_id)
    
    @staticmethod
    def calculate_file_hash(file_path: str) -> str:
        """Calculate SHA256 hash of a file"""
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    @staticmethod
    def calculate_directory_hash(directory_path: str) -> str:
        """Calculate hash of entire directory"""
        sha256_hash = hashlib.sha256()
        
        for root, dirs, files in os.walk(directory_path):
            # Sort for consistency
            for filename in sorted(files):
                file_path = os.path.join(root, filename)
                try:
                    with open(file_path, 'rb') as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(byte_block)
                except Exception:
                    pass
        
        return sha256_hash.hexdigest()
