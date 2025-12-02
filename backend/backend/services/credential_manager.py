"""
Secure credential storage using Alterion Secret Manager
Stores SSH username and password as secrets in hidden SSH environment
"""
import logging
import secrets
import string
from secretmanager.models import SecretProject, SecretEnvironment, Secret, SecretVersion
from crypto_utils import encrypt_value, decrypt_value
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()

# Generate random 15-character project name to hide SSH credentials
def _generate_random_project_name():
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(15))

# Internal identifier for finding the project
NODE_CREDENTIALS_PROJECT_IDENTIFIER = "_ssh_node_creds_internal_"


def _get_or_create_credentials_project():
    """Get or create the SSH credentials project with random name and hidden SSH environment"""
    # Try to find existing project by description identifier
    project = SecretProject.objects.filter(description__contains=NODE_CREDENTIALS_PROJECT_IDENTIFIER).first()
    
    if not project:
        # Create new project with random name
        random_name = _generate_random_project_name()
        project = SecretProject.objects.create(
            name=random_name,
            description=f'{NODE_CREDENTIALS_PROJECT_IDENTIFIER} SSH credentials for node connections',
            created_by=User.objects.filter(is_superuser=True).first()
        )
        logger.info(f"Created credentials project with random name: {random_name}")
    
    # Get or create hidden SSH environment
    ssh_env, env_created = SecretEnvironment.objects.get_or_create(
        project=project,
        slug='ssh',
        defaults={
            'name': 'SSH',
            'position': 0,
            'is_hidden': True  # Hide from UI
        }
    )
    
    if env_created:
        logger.info("Created hidden SSH environment for node credentials")
    
    return ssh_env


def save_node_ssh_credentials(node_id, username, password, user=None):
    """
    Save SSH username and password to Secret Manager with node_id + random suffix
    Returns the ssh_key_id (node_id + random suffix)
    """
    import secrets
    import string
    
    print(f"[CRED_MGR] save_node_ssh_credentials called for node {node_id}")
    print(f"[CRED_MGR] Username: {username}")
    print(f"[CRED_MGR] Password present: {bool(password)}")
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
        print(f"[CRED_MGR] Using superuser: {user}")
    
    # Generate ssh_key_id as node_id + random 8-character suffix for unpredictability
    random_suffix = ''.join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))
    ssh_key_id = f"{node_id}_{random_suffix}"
    print(f"[CRED_MGR] Generated ssh_key_id: {ssh_key_id}")
    
    try:
        prod_env = _get_or_create_credentials_project()
        print(f"[CRED_MGR] Using environment: {prod_env.name if prod_env else 'None'}")
        
        # Store username and password as single combined value (username:password)
        combined_value = f"{username}:{password}"
        print(f"[CRED_MGR] Combined value length: {len(combined_value)}")
        
        # Encrypt key, value, and description
        encrypted_key = encrypt_value(ssh_key_id)
        encrypted_value = encrypt_value(combined_value)
        encrypted_desc = encrypt_value(f'SSH credentials for node {node_id}')
        print(f"[CRED_MGR] Encryption completed")
        
        credential_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_key,
            defaults={
                'value': encrypted_value,
                'description': encrypted_desc,
                'created_by': user,
                'updated_by': user
            }
        )
        print(f"[CRED_MGR] Secret {'created' if created else 'updated'} with ID: {credential_secret.id}")
        
        # Create version history
        version = SecretVersion.objects.create(
            secret=credential_secret,
            value=encrypted_value,
            changed_by=user,
            change_type='created' if created else 'updated'
        )
        print(f"[CRED_MGR] Version history created with ID: {version.id}")
        
        logger.info(f"Saved SSH credentials for node {node_id} with key {ssh_key_id}")
        print(f"[CRED_MGR] Successfully saved credentials!")
        
        return ssh_key_id
        
    except Exception as e:
        logger.error(f"Failed to save credentials for node {node_id}: {e}")
        print(f"[CRED_MGR] ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise


def get_node_ssh_username(node_id):
    """Retrieve SSH username from Secret Manager"""
    from .node_models import Node
    
    try:
        # Get the node to retrieve the ssh_key_id
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        ssh_env = _get_or_create_credentials_project()
        
        # Query all secrets and decrypt keys to find match
        all_secrets = Secret.objects.filter(environment=ssh_env)
        for secret in all_secrets:
            try:
                decrypted_key = decrypt_value(secret.key)
                if decrypted_key == node.ssh_key_id:
                    # Decrypt value and extract username (before colon)
                    combined_value = decrypt_value(secret.value)
                    username = combined_value.split(':', 1)[0]
                    return username
            except Exception:
                continue
        
        logger.warning(f"No credentials found for node {node_id}")
        return None
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve username for node {node_id}: {e}")
        return None


def get_node_ssh_password(node_id):
    """Retrieve SSH password from Secret Manager"""
    from .node_models import Node
    
    try:
        # Get the node to retrieve the ssh_key_id
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        ssh_env = _get_or_create_credentials_project()
        
        # Query all secrets and decrypt keys to find match
        all_secrets = Secret.objects.filter(environment=ssh_env)
        for secret in all_secrets:
            try:
                decrypted_key = decrypt_value(secret.key)
                if decrypted_key == node.ssh_key_id:
                    # Decrypt value and extract password (after colon)
                    combined_value = decrypt_value(secret.value)
                    password = combined_value.split(':', 1)[1] if ':' in combined_value else None
                    return password
            except Exception:
                continue
        
        logger.warning(f"No credentials found for node {node_id}")
        return None
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve password for node {node_id}: {e}")
        return None


def get_node_ssh_credentials(node_id):
    """
    Retrieve both SSH username and password from Secret Manager
    Returns tuple of (username, password) or (None, None) if not found
    """
    username = get_node_ssh_username(node_id)
    password = get_node_ssh_password(node_id)
    return username, password


def delete_node_ssh_credentials(node_id, user=None):
    """Delete SSH credentials from Secret Manager"""
    from .node_models import Node
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    try:
        # Get the node to retrieve the ssh_key_id
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return
        
        encrypted_key = encrypt_value(node.ssh_key_id)
        prod_env = _get_or_create_credentials_project()
        
        # Delete credentials
        try:
            credential_secret = Secret.objects.get(environment=prod_env, key=encrypted_key)
            
            # Create version history before deleting
            SecretVersion.objects.create(
                secret=credential_secret,
                value=credential_secret.value,
                changed_by=user,
                change_type='deleted'
            )
            
            credential_secret.delete()
            logger.info(f"Deleted SSH credentials for node {node_id}")
        except Secret.DoesNotExist:
            logger.warning(f"Credentials not found for node {node_id}")
        except Exception as e:
            logger.warning(f"Failed to delete credentials for node {node_id}: {e}")
    
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
    except Exception as e:
        logger.error(f"Failed to delete credentials for node {node_id}: {e}")


def update_node_ssh_password(node_id, new_password, user=None):
    """Update only the SSH password for a node (re-saves combined credentials)"""
    from .node_models import Node
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    try:
        # Get current username and update with new password
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        # Get current username
        current_username = get_node_ssh_username(node_id)
        if not current_username:
            logger.warning(f"No existing username found for node {node_id}")
            return None
        
        # Store updated credentials (username:new_password)
        combined_value = f"{current_username}:{new_password}"
        encrypted_key = encrypt_value(node.ssh_key_id)
        encrypted_value = encrypt_value(combined_value)
        encrypted_desc = encrypt_value(f'SSH credentials for node {node_id}')
        
        prod_env = _get_or_create_credentials_project()
        
        credential_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_key,
            defaults={
                'value': encrypted_value,
                'description': encrypted_desc,
                'updated_by': user
            }
        )
        
        # Create version history
        SecretVersion.objects.create(
            secret=credential_secret,
            value=encrypted_value,
            changed_by=user,
            change_type='updated'
        )
        
        logger.info(f"Updated SSH password for node {node_id}")
        return node.ssh_key_id
    
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
        
    except Exception as e:
        logger.error(f"Failed to update password for node {node_id}: {e}")
        raise


def update_node_ssh_username(node_id, new_username, user=None):
    """Update only the SSH username for a node (re-saves combined credentials)"""
    from .node_models import Node
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    try:
        # Get current password and update with new username
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        # Get current password
        current_password = get_node_ssh_password(node_id)
        if not current_password:
            logger.warning(f"No existing password found for node {node_id}")
            return None
        
        # Store updated credentials (new_username:password)
        combined_value = f"{new_username}:{current_password}"
        encrypted_key = encrypt_value(node.ssh_key_id)
        encrypted_value = encrypt_value(combined_value)
        encrypted_desc = encrypt_value(f'SSH credentials for node {node_id}')
        
        prod_env = _get_or_create_credentials_project()
        
        credential_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_key,
            defaults={
                'value': encrypted_value,
                'description': encrypted_desc,
                'updated_by': user
            }
        )
        
        # Create version history
        SecretVersion.objects.create(
            secret=credential_secret,
            value=encrypted_value,
            changed_by=user,
            change_type='updated'
        )
        
        logger.info(f"Updated SSH username for node {node_id}")
        return node.ssh_key_id
        
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
        
    except Exception as e:
        logger.error(f"Failed to update username for node {node_id}: {e}")
        raise
