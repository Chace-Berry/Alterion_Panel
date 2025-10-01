import os
import base64
import json
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

def get_device_id():
	# Example: use hostname as device id, or customize as needed
	import socket
	return socket.gethostname()

def get_private_key_path():
	device_id = get_device_id()
	return os.path.join(settings.BASE_DIR, 'panel', device_id, 'encryption', 'keys', 'keystore', 'private-key.pem')

def load_private_key():
	key_path = get_private_key_path()
	with open(key_path, 'rb') as key_file:
		return serialization.load_pem_private_key(
			key_file.read(),
			password=None,
			backend=default_backend()
		)

class CryptoMiddleware(MiddlewareMixin):
	"""
	Middleware to decrypt incoming encrypted credentials using the device private key.
	Expects encrypted fields in request.POST or request.body as base64.
	Attaches decrypted data to request.decrypted_data.
	"""
	def process_request(self, request):
		# Only decrypt for POST requests with encrypted data
		if request.method != 'POST':
			return None
		try:
			# Try to get encrypted data from POST or body
			enc_data = request.POST.get('cryptdata')
			if not enc_data and request.body:
				try:
					body_json = json.loads(request.body.decode())
					enc_data = body_json.get('cryptdata')
				except Exception:
					pass
			if not enc_data:
				return None
			private_key = load_private_key()
			decrypted = private_key.decrypt(
				base64.b64decode(enc_data),
				padding.OAEP(
					mgf=padding.MGF1(algorithm=hashes.SHA256()),
					algorithm=hashes.SHA256(),
					label=None
				)
			)
			# Assume decrypted is utf-8 JSON
			try:
				decrypted_data = json.loads(decrypted.decode())
			except Exception:
				decrypted_data = {'decrypted': decrypted.decode(errors='ignore')}
			request.decrypted_data = decrypted_data
		except Exception as e:
			# Optionally log error
			request.decrypted_data = None
		return None
