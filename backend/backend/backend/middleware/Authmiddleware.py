from django.http import HttpResponse
from django.template.loader import render_to_string
from oauth2_provider.models import AccessToken
from django.utils import timezone
from dashboard.views import get_stable_server_id

class AuthMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip auth check for API, static, assets, admin, and root
        if (request.path.startswith('/api/') or 
            request.path.startswith('/static/') or 
            request.path.startswith('/assets/') or 
            request.path.startswith('/admin/') or 
            request.path.startswith('/alterion/panel/api/') or
            request.path == '/'):
            return self.get_response(request)
        
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