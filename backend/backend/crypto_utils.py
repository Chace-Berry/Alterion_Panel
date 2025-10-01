
import base64, zlib, json, logging
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import keyring

logger = logging.getLogger(__name__)
SERVICE_NAME = 'panel_crypto'
KEY_ID = 'panel_private_key'

# --- Key Storage ---
def get_private_key():
    key_pem = keyring.get_password(SERVICE_NAME, KEY_ID)
    if not key_pem:
        raise RuntimeError('No private key found in credential manager.')
    return serialization.load_pem_private_key(key_pem.encode(), password=None, backend=default_backend())

# --- Decryption ---
def decrypt_with_private_key(data_base64: str) -> bytes:
    private_key = get_private_key()
    encrypted = base64.b64decode(data_base64)
    return private_key.decrypt(
        encrypted,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_aes_gcm(ciphertext: bytes, key: bytes, iv: bytes) -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(iv, ciphertext, None)

def web_decrypt(cryptdata_base64: str, data_base64: str) -> dict:
    aes_key = decrypt_with_private_key(cryptdata_base64)
    data = base64.b64decode(data_base64)
    iv = data[:12]
    ciphertext = data[12:]
    decrypted_payload = decrypt_aes_gcm(ciphertext, aes_key, iv)
    decompressed = zlib.decompress(decrypted_payload)
    return json.loads(decompressed.decode('utf-8'))

# --- Intercept and decrypt all incoming payloads ---
def intercept_and_decrypt(request):
    cryptdata = request.data.get('cryptdata')
    data = request.data.get('data')
    if cryptdata and data:
        payload = web_decrypt(cryptdata, data)
        request.decrypted_payload = payload
        return payload
    return None
