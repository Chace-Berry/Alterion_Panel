import requests

class SecretManagerClient:
    def __init__(self, api_url, client_id, client_secret, decrypt_func=None):
        self.api_url = api_url.rstrip('/')
        self.client_id = client_id
        self.client_secret = client_secret
        self.decrypt_func = decrypt_func
        self.access_token = None

    def authenticate(self, username, password):
        token_url = f"{self.api_url}/oauth/token"
        data = {
            "grant_type": "password",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "username": username,
            "password": password
        }
        resp = requests.post(token_url, data=data)
        resp.raise_for_status()
        token_data = resp.json()
        self.access_token = token_data.get("access_token")
        if not self.access_token:
            raise Exception("Failed to obtain access token")

    def get_secret(self, environment_id, secret_key):
        if not self.access_token:
            raise Exception("Authenticate first to obtain access token.")
        url = f"{self.api_url}/environments/{environment_id}/secrets/"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        secrets = resp.json()
        for secret in secrets:
            if secret['key'] == secret_key:
                value = secret['value']
                if self.decrypt_func:
                    try:
                        value = self.decrypt_func(value)
                    except Exception:
                        value = '[Decryption Failed]'
                return value
        raise KeyError(f"Secret '{secret_key}' not found in environment '{environment_id}'")

# Example usage:
# from crypto_utils import decrypt_value
# client = SecretManagerClient("https://your-api-url", "your-client-id", "your-client-secret", decrypt_func=decrypt_value)
# client.authenticate("username", "password")
# db_password = client.get_secret("prod-env-id", "DB_PASSWORD")
