from django.http import HttpResponse
from django.template.loader import render_to_string
from oauth2_provider.models import AccessToken
from django.utils import timezone
from dashboard.views import get_stable_server_id

class AuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Exclude login and session check endpoints from auth
        excluded_paths = [
            '/api/alterion/panel/auth/login/',
            '/api/alterion/panel/auth/check_session/',
        ]
        if request.path in excluded_paths:
            return self.get_response(request)

        # Skip auth check for API, static, assets, admin, and root
        if (request.path.startswith('/api/') or request.path.startswith('/alterion/panel/api/')):
            # Enforce HTTPS for API endpoints
            if not request.is_secure():
                return HttpResponse('HTTPS required for API', status=403)
            # Check for Bearer token in Authorization header
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ', 1)[1]
                try:
                    token_obj = AccessToken.objects.get(token=token)
                    if token_obj.expires > timezone.now():
                        return self.get_response(request)
                except AccessToken.DoesNotExist:
                    pass
            # Optionally allow cookie-based access for API as fallback
            server_id = get_stable_server_id()
            access_cookie_name = f"alt_acs-tkn_{server_id}"
            access_token = request.COOKIES.get(access_cookie_name)
            if access_token:
                try:
                    token_obj = AccessToken.objects.get(token=access_token)
                    if token_obj.expires > timezone.now():
                        return self.get_response(request)
                except AccessToken.DoesNotExist:
                    pass
            # Check for api_key in query params
            api_key = request.GET.get('api_key')
            if api_key:
                try:
                    token_obj = AccessToken.objects.get(token=api_key)
                    if token_obj.expires > timezone.now():
                        return self.get_response(request)
                except AccessToken.DoesNotExist:
                    pass
            # Not authenticated for API, return 401
            return HttpResponse('Unauthorized', status=401)
        elif (request.path.startswith('/static/') or
              request.path.startswith('/assets/') or
              request.path.startswith('/admin/') or
              request.path == '/'):
            return self.get_response(request)
        else:
            # Debug logging for incoming requests
            import logging
            logger = logging.getLogger('authmiddleware')
            logger.info(f"Request path: {request.path}")
            logger.info(f"Request host: {request.get_host()}")
            logger.info(f"Request is_secure: {request.is_secure()}")
            logger.info(f"Authorization header: {request.META.get('HTTP_AUTHORIZATION', '')}")
            logger.info(f"API key param: {request.GET.get('api_key')}")
            logger.info(f"Cookies: {request.COOKIES}")
            # Get server ID for cookie names
            server_id = get_stable_server_id()
            access_cookie_name = f"alt_acs-tkn_{server_id}"
            access_token = request.COOKIES.get(access_cookie_name)

            if access_token:
                try:
                    token_obj = AccessToken.objects.get(token=access_token)
                    if token_obj.expires > timezone.now():
                        # Valid token, proceed
                        return self.get_response(request)
                except AccessToken.DoesNotExist:
                    pass

            # Not authenticated or invalid token, return 404
            html = render_to_string('404.html')
            return HttpResponse(html, status=404)