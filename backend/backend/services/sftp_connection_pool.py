"""
SFTP Connection Pool Manager
Maintains persistent SFTP connections to avoid reconnecting on every request
Includes automatic cleanup of idle connections
"""
import paramiko
import logging
import threading
import time
from datetime import datetime, timedelta
from .credential_manager import get_node_ssh_credentials
from .node_models import Node

logger = logging.getLogger(__name__)


class SFTPConnectionPool:
    """Manages a pool of persistent SFTP connections"""
    
    def __init__(self, max_idle_time=300):  # 5 minutes idle timeout
        self.connections = {}  # {node_id: {'ssh': ssh, 'sftp': sftp, 'last_used': datetime}}
        self.lock = threading.RLock()
        self.max_idle_time = max_idle_time
        self.cleanup_thread = None
        self.running = True
        self._start_cleanup_thread()
    
    def _start_cleanup_thread(self):
        """Start background thread to cleanup idle connections"""
        def cleanup_worker():
            while self.running:
                time.sleep(60)  # Check every minute
                self._cleanup_idle_connections()
        
        self.cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        self.cleanup_thread.start()
        logger.info("SFTP connection pool cleanup thread started")
    
    def _cleanup_idle_connections(self):
        """Close connections that have been idle too long"""
        with self.lock:
            now = datetime.now()
            to_remove = []
            
            for node_id, conn_info in self.connections.items():
                idle_seconds = (now - conn_info['last_used']).total_seconds()
                if idle_seconds > self.max_idle_time:
                    to_remove.append(node_id)
            
            for node_id in to_remove:
                logger.info(f"[SFTP_POOL] Closing idle connection to {node_id}")
                self._close_connection(node_id)
    
    def _close_connection(self, node_id):
        """Close and remove a connection from the pool (must be called with lock held)"""
        if node_id in self.connections:
            conn_info = self.connections[node_id]
            try:
                if conn_info.get('sftp'):
                    conn_info['sftp'].close()
            except Exception as e:
                logger.warning(f"Error closing SFTP for {node_id}: {e}")
            
            try:
                if conn_info.get('ssh'):
                    conn_info['ssh'].close()
            except Exception as e:
                logger.warning(f"Error closing SSH for {node_id}: {e}")
            
            del self.connections[node_id]
    
    def _test_connection(self, ssh, sftp):
        """Test if an existing connection is still alive"""
        try:
            # Try a simple operation to check if connection is alive
            sftp.listdir('.')
            return True
        except Exception:
            return False
    
    def get_connection(self, node_id):
        """
        Get or create an SFTP connection for a node
        Returns (ssh, sftp) tuple
        Raises exception on failure
        """
        with self.lock:
            # Check if we have an existing connection
            if node_id in self.connections:
                conn_info = self.connections[node_id]
                ssh = conn_info['ssh']
                sftp = conn_info['sftp']
                
                # Test if connection is still alive
                if self._test_connection(ssh, sftp):
                    # Update last used time
                    conn_info['last_used'] = datetime.now()
                    logger.debug(f"[SFTP_POOL] Reusing existing connection to {node_id}")
                    return ssh, sftp
                else:
                    # Connection is dead, remove it
                    logger.info(f"[SFTP_POOL] Existing connection to {node_id} is dead, reconnecting")
                    self._close_connection(node_id)
            
            # Create new connection
            logger.info(f"[SFTP_POOL] Creating new connection to {node_id}")
            ssh, sftp = self._create_new_connection(node_id)
            
            # Store in pool
            self.connections[node_id] = {
                'ssh': ssh,
                'sftp': sftp,
                'last_used': datetime.now()
            }
            
            return ssh, sftp
    
    def _create_new_connection(self, node_id):
        """Create a new SFTP connection to a node"""
        try:
            # Get node from database
            node = Node.objects.get(id=node_id)
            
            # Retrieve credentials from Secret Manager
            username, password = get_node_ssh_credentials(node_id)
            
            if not username or not password:
                raise ValueError(f"No SSH credentials found in Secret Manager for node {node_id}")
            
            logger.info(f"[SFTP_POOL] Connecting to {node_id} ({node.ip_address}:{node.ssh_port}) as {username}")
            
            # Create SSH connection
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect using stored credentials
            ssh.connect(
                hostname=node.ip_address,
                port=node.ssh_port,
                username=username,
                password=password,
                timeout=10,
                banner_timeout=10,
                auth_timeout=10
            )
            
            # Open SFTP session
            sftp = ssh.open_sftp()
            
            logger.info(f"[SFTP_POOL] SFTP connection established to {node_id}")
            return ssh, sftp
            
        except Node.DoesNotExist:
            logger.error(f"Node {node_id} not found in database")
            raise ValueError(f"Node {node_id} not found")
        except paramiko.AuthenticationException as e:
            logger.error(f"SSH authentication failed for node {node_id}: {e}")
            raise ValueError(f"SSH authentication failed for node {node_id}. Check credentials in Secret Manager.")
        except paramiko.SSHException as e:
            logger.error(f"SSH connection error for node {node_id}: {e}")
            raise ValueError(f"SSH connection error: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to connect to node {node_id}: {e}")
            raise
    
    def close_connection(self, node_id):
        """Manually close a specific connection"""
        with self.lock:
            if node_id in self.connections:
                logger.info(f"[SFTP_POOL] Manually closing connection to {node_id}")
                self._close_connection(node_id)
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            logger.info(f"[SFTP_POOL] Closing all {len(self.connections)} connections")
            for node_id in list(self.connections.keys()):
                self._close_connection(node_id)
        
        # Stop cleanup thread
        self.running = False
    
    def get_stats(self):
        """Get pool statistics"""
        with self.lock:
            return {
                'active_connections': len(self.connections),
                'connections': {
                    node_id: {
                        'last_used': conn_info['last_used'].isoformat(),
                        'idle_seconds': (datetime.now() - conn_info['last_used']).total_seconds()
                    }
                    for node_id, conn_info in self.connections.items()
                }
            }


# Global connection pool instance
_connection_pool = None
_pool_lock = threading.Lock()


def get_connection_pool():
    """Get the global SFTP connection pool instance"""
    global _connection_pool
    
    if _connection_pool is None:
        with _pool_lock:
            if _connection_pool is None:
                _connection_pool = SFTPConnectionPool()
    
    return _connection_pool


def get_pooled_sftp_connection(node_id):
    """
    Get a pooled SFTP connection for a node
    Returns (ssh, sftp) tuple - DO NOT close these connections manually!
    """
    pool = get_connection_pool()
    return pool.get_connection(node_id)


def close_pooled_connection(node_id):
    """Manually close a pooled connection (usually not needed)"""
    pool = get_connection_pool()
    pool.close_connection(node_id)
