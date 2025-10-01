from rest_framework.authentication import BaseAuthentication
from oauth2_provider.models import AccessToken
from django.contrib.auth import get_user_model
from django.utils import timezone

class CookieOAuth2Authentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get('msa_access')
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
