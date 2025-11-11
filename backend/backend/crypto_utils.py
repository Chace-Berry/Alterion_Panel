import base64, zlib, json, os, stat
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.fernet import Fernet

# --- Backend Key Management Helpers ---


# Key paths (all in keys folder)
KEYS_DIR = os.path.join(os.path.dirname(__file__), "keys")
BACKEND_PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "backend_private.pem")
BACKEND_PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "backend_public.pem")

# Utility to get agent public key path by nodeid
def get_agent_public_key_path(nodeid):
    return os.path.join(KEYS_DIR, f"agent_{nodeid}_pub.pem")

# Load agent public key by nodeid
def load_agent_public_key(nodeid):
    path = get_agent_public_key_path(nodeid)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Agent public key not found for nodeid {nodeid} at {path}")
    with open(path, "rb") as f:
        return load_public_key(f.read())


def generate_rsa_keypair(bits=2048):
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
        backend=default_backend()
    )
    public_key = private_key.public_key()
    return private_key, public_key

def serialize_private_key(private_key):
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

def serialize_public_key(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

def load_private_key(pem_bytes):
    return serialization.load_pem_private_key(pem_bytes, password=None, backend=default_backend())

def load_public_key(pem_bytes):
    return serialization.load_pem_public_key(pem_bytes, backend=default_backend())


def ensure_keys_dir():
    if not os.path.exists(KEYS_DIR):
        os.makedirs(KEYS_DIR, exist_ok=True)

def backend_generate_and_store_keypair(private_path=BACKEND_PRIVATE_KEY_PATH, public_path=BACKEND_PUBLIC_KEY_PATH):
    ensure_keys_dir()
    if os.path.exists(private_path) and os.path.exists(public_path):
        return  # Already exists
    priv, pub = generate_rsa_keypair()
    with open(private_path, "wb") as f:
        f.write(serialize_private_key(priv))
    with open(public_path, "wb") as f:
        f.write(serialize_public_key(pub))
    try:
        os.chmod(private_path, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(public_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception:
        pass




def backend_load_private_key():
    return load_encrypted_private_key()

def backend_load_public_key(public_path=BACKEND_PUBLIC_KEY_PATH):
    with open(public_path, "rb") as f:
        return load_public_key(f.read())

# --- Hybrid Encryption/Decryption for backend (panel) ---

# Hybrid encrypt using a specified public key (backend or agent)
def hybrid_encrypt(plaintext: bytes, peer_public_key=None, agent_nodeid=None) -> dict:
    # If agent_nodeid is given, use that agent's public key
    if agent_nodeid is not None:
        peer_public_key = load_agent_public_key(agent_nodeid)
    elif peer_public_key is None:
        with open(BACKEND_PUBLIC_KEY_PATH, "rb") as f:
            peer_public_key = load_public_key(f.read())
    aes_key = AESGCM.generate_key(bit_length=256)
    iv = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    compressed = zlib.compress(plaintext)
    ciphertext = aesgcm.encrypt(iv, compressed, None)
    encrypted_key = peer_public_key.encrypt(
        aes_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    return {
        "cryptdata": base64.b64encode(encrypted_key).decode(),
        "data": base64.b64encode(iv + ciphertext).decode(),
    }

def hybrid_decrypt(cryptdata_b64: str, data_b64: str, private_key) -> bytes:
    encrypted_key = base64.b64decode(cryptdata_b64)
    data = base64.b64decode(data_b64)
    iv = data[:12]
    ciphertext = data[12:]
    aes_key = private_key.decrypt(
        encrypted_key,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )
    aesgcm = AESGCM(aes_key)
    decrypted = aesgcm.decrypt(iv, ciphertext, None)
    decompressed = zlib.decompress(decrypted)
    return decompressed

def encrypt_payload(payload: dict, peer_public_key) -> dict:
    return hybrid_encrypt(json.dumps(payload).encode(), peer_public_key)

def decrypt_payload(cryptdata_b64: str, data_b64: str, private_key) -> dict:
    decrypted = hybrid_decrypt(cryptdata_b64, data_b64, private_key)
    return json.loads(decrypted.decode('utf-8'))

# --- Auto-generate/load backend keys on import (for production/packaging) ---
_backend_private_key = None
_backend_public_key = None
try:
    backend_generate_and_store_keypair()
    _backend_private_key = backend_load_private_key()
    _backend_public_key = backend_load_public_key()
except Exception as e:
    # If encrypted keys fail, try loading unencrypted fallback keys
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to load encrypted keys: {e}. Trying unencrypted fallback...")
    try:
        with open(BACKEND_PRIVATE_KEY_PATH, "rb") as f:
            _backend_private_key = load_private_key(f.read())
        with open(BACKEND_PUBLIC_KEY_PATH, "rb") as f:
            _backend_public_key = load_public_key(f.read())
        logger.info("Successfully loaded unencrypted fallback keys")
    except Exception as fallback_error:
        logger.error(f"Failed to load fallback keys too: {fallback_error}")

def get_backend_private_key():
    return _backend_private_key

def get_backend_public_key():
    return _backend_public_key


# --- Simple encryption/decryption for secrets (using AES-GCM) ---
from cryptography.fernet import Fernet
from django.conf import settings

def get_secret_key():
    """Get or generate encryption key for secrets"""
    # Use Django's SECRET_KEY as the base for generating a Fernet key
    key = settings.SECRET_KEY.encode()
    # Hash it to get consistent 32 bytes
    from hashlib import sha256
    hashed = sha256(key).digest()
    # Fernet requires base64-encoded 32-byte key
    return base64.urlsafe_b64encode(hashed)

def encrypt_value(value: str) -> str:
    """Encrypt a string value for storage"""
    f = Fernet(get_secret_key())
    encrypted = f.encrypt(value.encode())
    return base64.b64encode(encrypted).decode()

def decrypt_value(encrypted_value: str) -> str:
    """Decrypt a stored encrypted value"""
    f = Fernet(get_secret_key())
    encrypted_bytes = base64.b64decode(encrypted_value.encode())
    decrypted = f.decrypt(encrypted_bytes)
    return decrypted.decode()

# --- Persistent Fernet Key (pk_key) for encrypting RSA private key ---
PK_KEY_ENV = "ALTERION_PK_KEY"
ENCRYPTED_PRIVKEY_PATH = os.path.join(KEYS_DIR, "backend_private.pem.enc")
PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "backend_public.pem")

# Helper to get pk_key from env, or generate and set if missing
def get_pk_key():
    pk_key = os.environ.get(PK_KEY_ENV)
    if pk_key:
        return pk_key.encode() if isinstance(pk_key, str) else pk_key
    # Generate new key and set in env
    new_key = Fernet.generate_key()
    os.environ[PK_KEY_ENV] = new_key.decode()
    return new_key

# Encrypt and store private key with Fernet
def encrypt_and_store_private_key(private_key):
    f = Fernet(get_pk_key())
    pem = serialize_private_key(private_key)
    encrypted = f.encrypt(pem)
    with open(ENCRYPTED_PRIVKEY_PATH, "wb") as fkey:
        fkey.write(encrypted)

# Load and decrypt private key from disk
def load_encrypted_private_key():
    f = Fernet(get_pk_key())
    with open(ENCRYPTED_PRIVKEY_PATH, "rb") as fkey:
        encrypted = fkey.read()
    pem = f.decrypt(encrypted)
    return load_private_key(pem)

# Generate and store new keypair (encrypt privkey with pk_key)
def generate_and_store_encrypted_keypair():
    ensure_keys_dir()
    if os.path.exists(ENCRYPTED_PRIVKEY_PATH) and os.path.exists(PUBLIC_KEY_PATH):
        return  # Already exists
    priv, pub = generate_rsa_keypair()
    encrypt_and_store_private_key(priv)
    with open(PUBLIC_KEY_PATH, "wb") as f:
        f.write(serialize_public_key(pub))
    try:
        os.chmod(ENCRYPTED_PRIVKEY_PATH, stat.S_IRUSR | stat.S_IWUSR)
        os.chmod(PUBLIC_KEY_PATH, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception:
        pass
