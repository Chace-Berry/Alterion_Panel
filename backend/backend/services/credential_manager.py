"""
Secure credential storage using Alterion Secret Manager
Stores SSH username and password as secrets in hidden SSH environment
"""
import logging
import secrets
import string
from .secret_manager_models import SecretProject, SecretEnvironment, Secret, SecretVersion
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
    Save SSH username and password to Secret Manager with random key names
    Returns tuple of (random_key_prefix, username_key_id, password_key_id)
    """
    import secrets
    import string
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    # Generate random 15-character key prefix
    random_prefix = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(15))
    username_key = f"{random_prefix}_usr"
    password_key = f"{random_prefix}_pwd"
    
    try:
        prod_env = _get_or_create_credentials_project()
        
        # Encrypt key, value, and description for username
        encrypted_username_key = encrypt_value(username_key)
        encrypted_username = encrypt_value(username)
        encrypted_username_desc = encrypt_value(f'SSH username for node {node_id}')
        
        username_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_username_key,
            defaults={
                'value': encrypted_username,
                'description': encrypted_username_desc,
                'created_by': user,
                'updated_by': user
            }
        )
        
        # Create version history for username
        SecretVersion.objects.create(
            secret=username_secret,
            value=encrypted_username,
            changed_by=user,
            change_type='created' if created else 'updated'
        )
        
        logger.info(f"Saved SSH username for node {node_id}")
        
        # Encrypt key, value, and description for password
        encrypted_password_key = encrypt_value(password_key)
        encrypted_password = encrypt_value(password)
        encrypted_password_desc = encrypt_value(f'SSH password for node {node_id}')
        
        password_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_password_key,
            defaults={
                'value': encrypted_password,
                'description': encrypted_password_desc,
                'created_by': user,
                'updated_by': user
            }
        )
        
        # Create version history for password
        SecretVersion.objects.create(
            secret=password_secret,
            value=encrypted_password,
            changed_by=user,
            change_type='created' if created else 'updated'
        )
        
        logger.info(f"Saved SSH password for node {node_id}")
        
        return random_prefix, username_key, password_key
        
    except Exception as e:
        logger.error(f"Failed to save credentials for node {node_id}: {e}")
        raise


def get_node_ssh_username(node_id):
    """Retrieve SSH username from Secret Manager by decrypting keys to find match"""
    from .node_models import Node
    
    try:
        # Get the node to retrieve the ssh_key_id (random prefix)
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        username_key = f"{node.ssh_key_id}_usr"
        ssh_env = _get_or_create_credentials_project()
        
        # Query all secrets in the SSH environment and decrypt keys to find match
        all_secrets = Secret.objects.filter(environment=ssh_env)
        for secret in all_secrets:
            try:
                decrypted_key = decrypt_value(secret.key)
                if decrypted_key == username_key:
                    username = decrypt_value(secret.value)
                    return username
            except Exception:
                # Skip secrets that can't be decrypted or don't match
                continue
        
        logger.warning(f"No username found for node {node_id}")
        return None
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
    except Exception as e:
        logger.error(f"Failed to retrieve username for node {node_id}: {e}")
        return None


def get_node_ssh_password(node_id):
    """Retrieve SSH password from Secret Manager by decrypting keys to find match"""
    from .node_models import Node
    
    try:
        # Get the node to retrieve the ssh_key_id (random prefix)
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        password_key = f"{node.ssh_key_id}_pwd"
        ssh_env = _get_or_create_credentials_project()
        
        # Query all secrets in the SSH environment and decrypt keys to find match
        all_secrets = Secret.objects.filter(environment=ssh_env)
        for secret in all_secrets:
            try:
                decrypted_key = decrypt_value(secret.key)
                if decrypted_key == password_key:
                    password = decrypt_value(secret.value)
                    return password
            except Exception:
                # Skip secrets that can't be decrypted or don't match
                continue
        
        logger.warning(f"No password found for node {node_id}")
        return None
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
    except Secret.DoesNotExist:
        logger.warning(f"No password found for node {node_id}")
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
    """Delete both SSH username and password from Secret Manager"""
    from .node_models import Node
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    errors = []
    
    try:
        # Get the node to retrieve the ssh_key_id (random prefix)
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return
        
        username_key = f"{node.ssh_key_id}_usr"
        password_key = f"{node.ssh_key_id}_pwd"
        encrypted_username_key = encrypt_value(username_key)
        encrypted_password_key = encrypt_value(password_key)
        
        prod_env = _get_or_create_credentials_project()
        
        # Delete username
        try:
            username_secret = Secret.objects.get(environment=prod_env, key=encrypted_username_key)
            
            # Create version history before deleting
            SecretVersion.objects.create(
                secret=username_secret,
                value=username_secret.value,
                changed_by=user,
                change_type='deleted'
            )
            
            username_secret.delete()
            logger.info(f"Deleted SSH username for node {node_id}")
        except Secret.DoesNotExist:
            logger.warning(f"Username secret not found for node {node_id}")
        except Exception as e:
            logger.warning(f"Failed to delete username for node {node_id}: {e}")
            errors.append(str(e))
        
        # Delete password
        try:
            password_secret = Secret.objects.get(environment=prod_env, key=encrypted_password_key)
            
            # Create version history before deleting
            SecretVersion.objects.create(
                secret=password_secret,
                value=password_secret.value,
                changed_by=user,
                change_type='deleted'
            )
            
            password_secret.delete()
            logger.info(f"Deleted SSH password for node {node_id}")
        except Secret.DoesNotExist:
            logger.warning(f"Password secret not found for node {node_id}")
        except Exception as e:
            logger.warning(f"Failed to delete password for node {node_id}: {e}")
            errors.append(str(e))
        
        if errors:
            logger.warning(f"Errors during credential deletion for node {node_id}: {'; '.join(errors)}")
    
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
    except Exception as e:
        logger.error(f"Failed to delete credentials for node {node_id}: {e}")
        errors.append(str(e))


def update_node_ssh_password(node_id, new_password, user=None):
    """Update only the SSH password for a node"""
    from .node_models import Node
    
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    try:
        # Get the node to retrieve the ssh_key_id (random prefix)
        node = Node.objects.get(id=node_id)
        if not node.ssh_key_id:
            logger.warning(f"No ssh_key_id found for node {node_id}")
            return None
        
        password_key = f"{node.ssh_key_id}_pwd"
        encrypted_password_key = encrypt_value(password_key)
        
        prod_env = _get_or_create_credentials_project()
        encrypted_password = encrypt_value(new_password)
        encrypted_password_desc = encrypt_value(f'SSH password for node {node_id}')
        
        password_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=encrypted_password_key,
            defaults={
                'value': encrypted_password,
                'description': encrypted_password_desc,
                'updated_by': user
            }
        )
        
        # Create version history
        SecretVersion.objects.create(
            secret=password_secret,
            value=encrypted_password,
            changed_by=user,
            change_type='updated'
        )
        
        logger.info(f"Updated SSH password for node {node_id}")
        return password_key
    
    except Node.DoesNotExist:
        logger.warning(f"Node {node_id} not found")
        return None
        
    except Exception as e:
        logger.error(f"Failed to update password for node {node_id}: {e}")
        raise


def update_node_ssh_username(node_id, new_username, user=None):
    """Update only the SSH username for a node"""
    if user is None:
        user = User.objects.filter(is_superuser=True).first()
    
    username_key = f"node_{node_id}_ssh_username"
    
    try:
        prod_env = _get_or_create_credentials_project()
        encrypted_username = encrypt_value(new_username)
        
        username_secret, created = Secret.objects.update_or_create(
            environment=prod_env,
            key=username_key,
            defaults={
                'value': encrypted_username,
                'description': f'SSH username for node {node_id}',
                'updated_by': user
            }
        )
        
        # Create version history
        SecretVersion.objects.create(
            secret=username_secret,
            value=encrypted_username,
            changed_by=user,
            change_type='updated'
        )
        
        logger.info(f"Updated SSH username for node {node_id}")
        return username_key
        
    except Exception as e:
        logger.error(f"Failed to update username for node {node_id}: {e}")
        raise
