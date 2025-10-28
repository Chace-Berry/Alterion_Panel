# Key paths (all in keys folder)
import os
from pathlib import Path
KEYS_DIR = os.path.join(os.path.dirname(__file__), "keys")
AGENT_PRIVATE_KEY_PATH = os.path.join(KEYS_DIR, "agent_private.pem")
AGENT_PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "agent_public.pem")
BACKEND_PUBLIC_KEY_PATH = os.path.join(KEYS_DIR, "backend_public.pem")

# Utility to get backend public key path (for agent)
def get_backend_public_key_path():
    return BACKEND_PUBLIC_KEY_PATH

# Utility to get agent private key path
def get_agent_private_key_path():
    return AGENT_PRIVATE_KEY_PATH
    path = get_backend_public_key_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Backend public key not found at {path}")
    with open(path, "rb") as f:
        return load_public_key(f.read())

# Load agent private key
def load_agent_private_key():
    path = get_agent_private_key_path()
    if not os.path.exists(path):
        raise FileNotFoundError(f"Agent private key not found at {path}")
    with open(path, "rb") as f:
        return load_private_key(f.read())
import base64, zlib, json, os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

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

def hybrid_encrypt(plaintext: bytes, peer_public_key) -> dict:
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

def save_private_key_to_file(private_key, path):
    with open(path, 'wb') as f:
        f.write(serialize_private_key(private_key))

def save_public_key_to_file(public_key, path):
    with open(path, 'wb') as f:
        f.write(serialize_public_key(public_key))

def load_private_key_from_file(path):
    with open(path, 'rb') as f:
        return load_private_key(f.read())

def load_public_key_from_file(path):
    with open(path, 'rb') as f:
        return load_public_key(f.read())
