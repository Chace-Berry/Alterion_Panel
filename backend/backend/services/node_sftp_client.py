"""
SFTP client for node file operations
Uses credentials from Secret Manager to establish SSH/SFTP connections
"""
import paramiko
import logging
from .credential_manager import get_node_ssh_credentials
from .node_models import Node

logger = logging.getLogger(__name__)


def get_node_sftp_connection(node_id):
    """
    Establish SFTP connection to a node using credentials from Secret Manager
    Returns (ssh_client, sftp_client) tuple
    Raises exception on failure
    """
    try:
        # Get node from database
        node = Node.objects.get(id=node_id)
        
        # Retrieve credentials from Secret Manager
        username, password = get_node_ssh_credentials(node_id)
        
        if not username or not password:
            raise ValueError(f"No SSH credentials found in Secret Manager for node {node_id}")
        
        logger.info(f"Connecting to node {node_id} ({node.ip_address}:{node.ssh_port}) as {username}")
        
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
        
        logger.info(f"SFTP connection established to node {node_id}")
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


def close_sftp_connection(ssh, sftp):
    """Safely close SFTP and SSH connections"""
    try:
        if sftp:
            sftp.close()
            logger.debug("SFTP session closed")
    except Exception as e:
        logger.warning(f"Error closing SFTP session: {e}")
    
    try:
        if ssh:
            ssh.close()
            logger.debug("SSH connection closed")
    except Exception as e:
        logger.warning(f"Error closing SSH connection: {e}")


def test_node_connection(node_id):
    """
    Test SSH/SFTP connection to a node
    Returns dict with success status and message
    """
    try:
        ssh, sftp = get_node_sftp_connection(node_id)
        
        # Try to list home directory to verify connection works
        try:
            sftp.listdir('.')
            message = "Connection successful"
        except Exception as e:
            message = f"Connected but SFTP error: {str(e)}"
        
        close_sftp_connection(ssh, sftp)
        
        return {
            'success': True,
            'message': message
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }
