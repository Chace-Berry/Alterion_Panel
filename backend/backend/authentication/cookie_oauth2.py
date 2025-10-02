from rest_framework.authentication import BaseAuthentication
from oauth2_provider.models import AccessToken
from django.contrib.auth import get_user_model
from django.utils import timezone
import pathlib

class CookieOAuth2Authentication(BaseAuthentication):
    def authenticate(self, request):

        server_id_path = (pathlib.Path(__file__).parent.parent / "dashboard" / "serverid.dat").resolve()
        try:
            server_id = server_id_path.read_text().strip()
        except Exception:
            server_id = "default"
        
        token = request.COOKIES.get(f'alt_acs-tkn_{server_id}')
        if not token:
            return None
        try:
            access_token = AccessToken.objects.get(token=token)
        except AccessToken.DoesNotExist:
            return None
        if access_token.expires < timezone.now():
            return None
        user = access_token.user
        return (user, None)
