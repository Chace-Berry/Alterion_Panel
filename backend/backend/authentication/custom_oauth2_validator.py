from oauth2_provider.oauth2_validators import OAuth2Validator
from django.contrib.auth import get_user_model
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger('oauth2_provider')

class CustomOAuth2Validator(OAuth2Validator):
    logger.info("CustomOAuth2Validator loaded and ready for debug logging.")
    
    def validate_client(self, client_id, client_secret, client, request, *args, **kwargs):
        """
        Standard client validation (no provider logic).
        """
        return super().validate_client(client_id, client_secret, client, request, *args, **kwargs)
    
    def validate_user(self, username, password, client, request, *args, **kwargs):
        # Log extra_credentials instead of request.POST
        logger.info(f"OAuth2 extra_credentials: {getattr(request, 'extra_credentials', None)}")
        logger.info(f"OAuth2 POST data: {getattr(request, 'POST', None)}")
        logger.info(f"OAuth2 username parameter: {username}")

        # Accept 'identifier' and match against username, email, or phone_number (if present on user model)
        identifier = None
        if hasattr(request, 'extra_credentials') and request.extra_credentials:
            identifier = request.extra_credentials.get('identifier')
        if not identifier and hasattr(request, 'POST'):
            identifier = request.POST.get('identifier')
        if not identifier:
            identifier = username

        logger.info(f"OAuth2 login attempt: identifier={identifier}, client_id={getattr(client, 'client_id', None)}")
        User = get_user_model()
        user = None
        
        # Try username (exact match)
        try:
            user = User.objects.get(username=identifier)
            logger.info(f"User found by username: {identifier}")
        except User.DoesNotExist:
            pass
        
        # Try email (case-insensitive)
        if user is None and hasattr(User, 'email'):
            try:
                user = User.objects.get(email__iexact=identifier)
                logger.info(f"User found by email: {identifier}")
            except User.DoesNotExist:
                pass
        
        # Try phone_number if present on model
        if user is None and hasattr(User, 'phone_number'):
            try:
                user = User.objects.get(phone_number=identifier)
                logger.info(f"User found by phone_number: {identifier}")
            except User.DoesNotExist:
                pass
        
        if user is None:
            logger.info(f"User not found for identifier: {identifier}")
            return False
        
        if user.check_password(password):
            request.user = user
            logger.info(f"Password correct for identifier: {identifier}")
            return True
        
        logger.info(f"Password incorrect for identifier: {identifier}")
        return False

    def save_bearer_token(self, token, request, *args, **kwargs):
        """
        Override to set conditional refresh token expiration based on 'remember_me'
        """
        logger.info(f"OAUTH2_TOKEN: Token dict before saving: {token}")
        refresh_token_obj = super().save_bearer_token(token, request, *args, **kwargs)
        logger.info(f"OAUTH2_TOKEN: refresh_token_obj after saving: {refresh_token_obj}")

        # Check if 'remember_me' was provided in the request
        remember_me = False

        # Check in extra_credentials first
        if hasattr(request, 'extra_credentials') and request.extra_credentials:
            remember_me = request.extra_credentials.get('remember_me', False)

        # Check in direct request parameters (POST data)
        if not remember_me and hasattr(request, 'POST'):
            remember_me_value = request.POST.get('remember_me', 'false').lower()
            remember_me = remember_me_value in ['true', '1', 'yes', 'on']

        # Also check if it's in the raw request data
        if not remember_me and hasattr(request, '_post') and request._post:
            remember_me_value = request._post.get('remember_me', 'false').lower()
            remember_me = remember_me_value in ['true', '1', 'yes', 'on']

        logger.info(f"Remember me setting: {remember_me}")

        # Set conditional expiration for refresh token
        if refresh_token_obj and hasattr(refresh_token_obj, 'refresh_token') and refresh_token_obj.refresh_token:
            from oauth2_provider.models import RefreshToken
            try:
                refresh_obj = RefreshToken.objects.get(token=refresh_token_obj.refresh_token.token)
                logger.info(f"OAUTH2_TOKEN: RefreshToken object: {refresh_obj}")
                logger.info(f"OAUTH2_TOKEN: RefreshToken token value: {refresh_obj.token}")
                if remember_me:
                    refresh_obj.expires = timezone.now() + timedelta(days=300)
                    logger.info(f"Set refresh token to expire in 300 days (remember_me=True)")
                else:
                    refresh_obj.expires = timezone.now() + timedelta(hours=24)
                    logger.info(f"Set refresh token to expire in 24 hours (remember_me=False)")
                refresh_obj.save()
            except RefreshToken.DoesNotExist:
                logger.warning("Refresh token not found for conditional expiration setting")

        return refresh_token_obj

    def validate_authorization_request(self, request):
        """
        Standard authorization request validation (no provider logic).
        """
        return super().validate_authorization_request(request)
