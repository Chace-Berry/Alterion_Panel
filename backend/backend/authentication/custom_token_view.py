from oauth2_provider.views import TokenView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest
from django.utils import timezone


import logging
import json
# Import the server ID generator
from dashboard.views import get_stable_server_id

class CustomTokenView(TokenView):
    @method_decorator(csrf_exempt)
    def dispatch(self, request: HttpRequest, *args, **kwargs):
        if request.method == 'POST':
            if hasattr(request, 'POST') and 'identifier' in request.POST:
                if hasattr(request.POST, '_mutable'):
                    mutable = request.POST._mutable
                    request.POST._mutable = True
                    request.POST['username'] = request.POST['identifier']
                    request.POST._mutable = mutable
                # Set extra_credentials so OAuth2 validator can access identifier
                request.extra_credentials = dict(request.POST)
        return super().dispatch(request, *args, **kwargs)



    def post(self, request, *args, **kwargs):
        logger = logging.getLogger('oauth2_provider')
        logger.info("CustomTokenView: post method called")

        # Log raw request body and POST data
        try:
            logger.info(f"CustomTokenView: request.body length: {len(request.body)} bytes")
            logger.info(f"CustomTokenView: request.body (first 500 chars): {request.body[:500]}")
            if hasattr(request, 'POST'):
                logger.info(f"CustomTokenView: request.POST={dict(request.POST)}")
        except Exception as e:
            logger.error(f"CustomTokenView: Error logging request body/POST: {e}")

        # Try to log cryptdata and data if present


        # Use decrypted data from CryptoMiddleware if present
        decrypted_data = getattr(request, 'decrypted_data', None)
        if decrypted_data and isinstance(decrypted_data, dict):
            from django.http import QueryDict
            qd = QueryDict('', mutable=True)
            for k, v in decrypted_data.items():
                if isinstance(v, list):
                    qd.setlist(k, v)
                else:
                    qd.setlist(k, [str(v)])
            # Remap identifier to username if present
            if 'identifier' in qd:
                qd.setlist('username', qd.getlist('identifier'))
            request.POST = qd
            logger.info(f"CustomTokenView: Injected decrypted_data into request.POST: {dict(request.POST)}")

        # Continue with normal token processing
        response = super().post(request, *args, **kwargs)
        logger.info(f"CustomTokenView: response.status_code={response.status_code}")

        # After successful authentication, update user organization/role if org_invite_code is present
        # OrgInviteLink/invite logic removed: not defined

        try:
            response_content = response.content.decode() if response.content else ""
            logger.info(f"CustomTokenView: response.content={response_content}")
        except Exception as e:
            logger.info(f"CustomTokenView: Could not decode response content: {e}")

        try:
            data = json.loads(response.content)
            access_token = data.get('access_token')
            refresh_token = data.get('refresh_token')
            logger.info(f"CustomTokenView: access_token present: {bool(access_token)}")
            logger.info(f"CustomTokenView: refresh_token present: {bool(refresh_token)}")
            if access_token:
                logger.info(f"CustomTokenView: access_token (FULL): {access_token}")
            if refresh_token:
                logger.info(f"CustomTokenView: refresh_token (FULL): {refresh_token}")

            # Handle remember_me
            remember_me = False
            if hasattr(request, 'POST') and 'remember_me' in request.POST:
                remember_me = request.POST.get('remember_me') in ['true', 'True', '1', True]
            else:
                try:
                    body_data = json.loads(request.body.decode())
                    remember_me = body_data.get('remember_me') in ['true', 'True', '1', True]
                except Exception:
                    pass

            cookie_max_age = 30 * 24 * 3600 if remember_me else None  # 30 days or session cookie
            logger.info(f"CustomTokenView: remember_me={remember_me}, cookie_max_age={cookie_max_age}")


            # Get stable server id
            server_id = get_stable_server_id()
            access_cookie_name = f"alt_acs-tkn_{server_id}"
            refresh_cookie_name = f"alt_rfr-tkn_{server_id}"

            if access_token:
                response.set_cookie(
                    access_cookie_name,
                    access_token,
                    httponly=True,
                    secure=True,
                    samesite='None',
                    max_age=cookie_max_age,
                    path='/',
                )
                logger.info(f"CustomTokenView: Set {access_cookie_name} cookie")

            if refresh_token:
                response.set_cookie(
                    refresh_cookie_name,
                    refresh_token,
                    httponly=True,
                    secure=True,
                    samesite='None',
                    max_age=cookie_max_age,
                    path='/',
                )
                logger.info(f"CustomTokenView: Set {refresh_cookie_name} cookie")

        except Exception as e:
            logger.error(f"CustomTokenView: Exception in response processing: {e}")
            # Removed traceback logging (traceback not imported)

        return response