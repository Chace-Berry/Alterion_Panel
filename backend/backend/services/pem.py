"""
PEM Key Generation Script for Alterion Panel
This script should be run during installation to:
1. Create RSA public/private key pair for encrypting locally stored account data
2. Set strict file permissions (read/write only by application)

Note: Server ID is managed separately in dashboard/views.py
"""

import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import stat


def generate_rsa_keypair():
    """Generate RSA public/private key pair"""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )
    
    public_key = private_key.public_key()
    
    return private_key, public_key


def save_private_key(private_key, filepath):
    """Save private key to PEM file"""
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    with open(filepath, 'wb') as f:
        f.write(pem)
    
    print(f"✓ Private key saved to: {filepath}")


def save_public_key(public_key, filepath):
    """Save public key to PEM file"""
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    with open(filepath, 'wb') as f:
        f.write(pem)
    
    print(f"✓ Public key saved to: {filepath}")


def set_file_permissions_windows(filepath):
    """Set strict file permissions on Windows - only application can read/write"""
    try:
        # On Windows, we'll use os.chmod with the most restrictive permissions
        # Read and write for owner only
        os.chmod(filepath, stat.S_IRUSR | stat.S_IWUSR)
        print(f"✓ Set permissions for: {filepath}")
    except Exception as e:
        print(f"⚠ Warning: Could not set permissions for {filepath}: {e}")


def set_file_permissions_unix(filepath):
    """Set strict file permissions on Unix/Linux - 600 (rw-------)"""
    try:
        # Only owner can read and write, no permissions for group or others
        os.chmod(filepath, 0o600)
        print(f"✓ Set permissions (600) for: {filepath}")
    except Exception as e:
        print(f"⚠ Warning: Could not set permissions for {filepath}: {e}")


def set_strict_permissions(filepath):
    """Set strict file permissions based on OS"""
    if sys.platform == 'win32':
        set_file_permissions_windows(filepath)
    else:
        set_file_permissions_unix(filepath)


def setup_encryption_keys(base_dir=None):
    """
    Main setup function to generate encryption keys for local account storage
    """
    if base_dir is None:
        # Default to the services directory
        base_dir = Path(__file__).resolve().parent
    else:
        base_dir = Path(base_dir)
    
    base_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Alterion Panel - Encryption Keys Setup")
    print("=" * 60)
    
    # File paths
    private_key_file = base_dir / 'private-key.pem'
    public_key_file = base_dir / 'public-key.pem'
    
    # Check if keys already exist
    if private_key_file.exists() or public_key_file.exists():
        response = input("\n⚠ Encryption keys already exist. Regenerate? (yes/no): ").lower()
        if response not in ['yes', 'y']:
            print("Setup cancelled. Existing keys preserved.")
            return False
        print("\n⚠ WARNING: Regenerating keys will make existing encrypted data unreadable!")
        confirm = input("Are you sure you want to continue? (yes/no): ").lower()
        if confirm not in ['yes', 'y']:
            print("Setup cancelled.")
            return False
    
    print("\n1. Generating RSA Key Pair (4096-bit)...")
    private_key, public_key = generate_rsa_keypair()
    
    print("\n2. Saving Private Key...")
    save_private_key(private_key, private_key_file)
    set_strict_permissions(private_key_file)
    
    print("\n3. Saving Public Key...")
    save_public_key(public_key, public_key_file)
    set_strict_permissions(public_key_file)
    
    print("\n" + "=" * 60)
    print("✓ Encryption keys setup completed successfully!")
    print("=" * 60)
    print(f"\nGenerated files:")
    print(f"  - Private Key: {private_key_file}")
    print(f"  - Public Key:  {public_key_file}")
    print("\n⚠ IMPORTANT: Keep these files secure and backed up!")
    print("⚠ Never share the private key or commit it to version control!")
    print("⚠ These keys are used to encrypt saved login accounts in browser")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate encryption keys for Alterion Panel account storage'
    )
    parser.add_argument(
        '--dir',
        type=str,
        help='Directory to store keys (default: services/)',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force regeneration without confirmation'
    )
    
    args = parser.parse_args()
    
    if args.force:
        # Skip confirmation if --force flag is used
        import builtins
        original_input = builtins.input
        builtins.input = lambda _: 'yes'
    
    try:
        setup_encryption_keys(args.dir)
    except KeyboardInterrupt:
        print("\n\nSetup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error during setup: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if args.force:
            builtins.input = original_input
