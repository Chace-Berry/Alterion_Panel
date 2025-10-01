from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from oauth2_provider.models import AccessToken, RefreshToken, Application
from django.utils import timezone
from django.contrib.auth import get_user_model
import re
import requests
from django.conf import settings


import logging
logger = logging.getLogger('django')
User = get_user_model()

@csrf_exempt
def check_session(request):
    # Use the server ID to find the correct cookie names
    from dashboard.views import get_stable_server_id
    server_id = get_stable_server_id()
    access_cookie_name = f"alt_acs-tkn_{server_id}"
    refresh_cookie_name = f"alt_rfr-tkn_{server_id}"
    access_token = request.COOKIES.get(access_cookie_name)
    refresh_token = request.COOKIES.get(refresh_cookie_name)
    logger.info(f"CHECK_SESSION: Using cookies {access_cookie_name}, {refresh_cookie_name}")
    logger.info(f"CHECK_SESSION: Found access_token={access_token}, refresh_token={refresh_token}")
    if not access_token:
        logger.info("CHECK_SESSION: No access token found in cookies.")
        return JsonResponse({'authenticated': False, 'error': 'No access token'}, status=401)
    
    # Validate access token
    try:
        token_obj = AccessToken.objects.get(token=access_token)
        logger.info(f"CHECK_SESSION: AccessToken object found: {token_obj}")
        if token_obj.expires > timezone.now():
            # Token is valid
            user = token_obj.user
            payload = {
                'authenticated': True,
                'username': user.username,
            }
            logger.info(f"CHECK_SESSION: Returning payload: {payload}")
            return JsonResponse(payload)
        else:
            logger.info("CHECK_SESSION: Access token expired.")
            # Access token expired, try to refresh if refresh token available
            if refresh_token:
                new_tokens = refresh_access_token(refresh_token, request)
                logger.info(f"CHECK_SESSION: refresh_access_token result: {new_tokens}")
                if new_tokens:
                    payload = {
                        'authenticated': True,
                        'user_id': new_tokens['user'].id,
                        'username': new_tokens['user'].username,
                        'accountNumber': new_tokens['user'].account_number,
                        'role': getattr(new_tokens['user'], 'role', None),
                        'email_verified': getattr(new_tokens['user'],'is_verified', False),
                        'token_refreshed': True,
                        'new_access_token': new_tokens['access_token'],
                        'new_refresh_token': new_tokens.get('refresh_token')
                    }
                    logger.info(f"CHECK_SESSION: Returning refreshed payload: {payload}")
                    return JsonResponse(payload)
            return JsonResponse({'authenticated': False, 'error': 'Token expired'}, status=401)
    except AccessToken.DoesNotExist:
        logger.info("CHECK_SESSION: AccessToken does not exist for provided token.")
        return JsonResponse({'authenticated': False, 'error': 'Invalid token'}, status=401)

def refresh_access_token(refresh_token, request):
    """
    Use refresh token to get a new access token
    Returns dict with new tokens and user, or None if failed
    """
    try:
        logger.info(f"REFRESH_ACCESS_TOKEN: Attempting refresh with token: {refresh_token}")
        # Validate refresh token exists and is not expired
        refresh_obj = RefreshToken.objects.get(token=refresh_token)
        logger.info(f"REFRESH_ACCESS_TOKEN: RefreshToken object: {refresh_obj}")
        # Check if refresh token is expired (if expiration is set)
        if hasattr(refresh_obj, 'expires') and refresh_obj.expires and refresh_obj.expires < timezone.now():
            logger.info("REFRESH_ACCESS_TOKEN: Refresh token expired.")
            return None
        # Get the default OAuth2 application
        try:
            application = Application.objects.get(name='MyApp')  # Adjust name as needed
        except Application.DoesNotExist:
            application = Application.objects.first()  # Fallback to first available
        logger.info(f"REFRESH_ACCESS_TOKEN: Using application: {application}")
        if not application:
            logger.info("REFRESH_ACCESS_TOKEN: No OAuth2 application found.")
            return None
        # Make internal request to token endpoint
        token_url = f"{request.scheme}://{request.get_host()}/o/token/"
        logger.info(f"REFRESH_ACCESS_TOKEN: Token URL: {token_url}")
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': application.client_id,
            'client_secret': application.client_secret,
        }
        logger.info(f"REFRESH_ACCESS_TOKEN: POST data: {data}")
        response = requests.post(token_url, data=data)
        logger.info(f"REFRESH_ACCESS_TOKEN: Response status: {response.status_code}, content: {response.content}")
        if response.status_code == 200:
            token_data = response.json()
            logger.info(f"REFRESH_ACCESS_TOKEN: Token data: {token_data}")
            # Get the new access token object and user
            new_access_token = AccessToken.objects.get(token=token_data['access_token'])
            logger.info(f"REFRESH_ACCESS_TOKEN: New AccessToken object: {new_access_token}")
            return {
                'access_token': token_data['access_token'],
                'refresh_token': token_data.get('refresh_token'),
                'user': new_access_token.user
            }
    except (RefreshToken.DoesNotExist, Exception) as e:
        logger.error(f"REFRESH_ACCESS_TOKEN: Exception occurred: {e}", exc_info=True)
    return None
