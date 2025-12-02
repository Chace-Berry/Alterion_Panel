from oauth2_provider.views import TokenView
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpRequest
from django.utils import timezone


import logging
import json

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

                request.extra_credentials = dict(request.POST)
        return super().dispatch(request, *args, **kwargs)



    def post(self, request, *args, **kwargs):
        logger = logging.getLogger('oauth2_provider')
        logger.info("CustomTokenView: post method called")

        try:
            logger.info(f"CustomTokenView: request.body length: {len(request.body)} bytes")
            logger.info(f"CustomTokenView: request.body (first 500 chars): {request.body[:500]}")
            if hasattr(request, 'POST'):
                logger.info(f"CustomTokenView: request.POST={dict(request.POST)}")
        except Exception as e:
            logger.error(f"CustomTokenView: Error logging request body/POST: {e}")


        decrypted_data = getattr(request, 'decrypted_data', None)
        if decrypted_data and isinstance(decrypted_data, dict):
            from django.http import QueryDict
            qd = QueryDict('', mutable=True)
            for k, v in decrypted_data.items():
                if isinstance(v, list):
                    qd.setlist(k, v)
                else:
                    qd.setlist(k, [str(v)])

            if 'identifier' in qd:
                qd.setlist('username', qd.getlist('identifier'))
            request.POST = qd
            logger.info(f"CustomTokenView: Injected decrypted_data into request.POST: {dict(request.POST)}")

        response = super().post(request, *args, **kwargs)
        logger.info(f"CustomTokenView: response.status_code={response.status_code}")



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

            if response.status_code == 200 and access_token:
                try:
                    from dashboard.logging_utils import log_login
                    from oauth2_provider.models import AccessToken
                    from authentication.user_list_views import get_device_fingerprint, get_device_name, get_client_ip
                    from accounts.models import DeviceLogin
                    
                    token_obj = AccessToken.objects.get(token=access_token)
                    if token_obj.user:
                        log_login(token_obj.user, request)
                        
                        # Record device login
                        device_id = get_device_fingerprint(request)
                        ip_address = get_client_ip(request)
                        user_agent = request.META.get('HTTP_USER_AGENT', '')
                        device_name = get_device_name(request)
                        
                        device_login, created = DeviceLogin.objects.get_or_create(
                            user=token_obj.user,
                            device_id=device_id,
                            defaults={
                                'ip_address': ip_address,
                                'user_agent': user_agent,
                                'device_name': device_name,
                                'login_count': 1
                            }
                        )
                        
                        if not created:
                            device_login.ip_address = ip_address
                            device_login.user_agent = user_agent
                            device_login.device_name = device_name
                            device_login.login_count += 1
                            device_login.save()
                        
                        logger.info(f"CustomTokenView: Recorded device login for user {token_obj.user.username}")
                except Exception as e:
                    logger.error(f"CustomTokenView: Error logging login activity: {e}")

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

            server_id = get_stable_server_id()
            access_cookie_name = f"alt_acs-tkn_{server_id}"
            refresh_cookie_name = f"alt_rfr-tkn_{server_id}"

            if access_token:
                response.set_cookie(
                    access_cookie_name,
                    access_token,
                    httponly=True,
                    secure=True,
                    samesite='Lax',
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
                    samesite='Lax',
                    max_age=cookie_max_age,
                    path='/',
                )
                logger.info(f"CustomTokenView: Set {refresh_cookie_name} cookie")

        except Exception as e:
            logger.error(f"CustomTokenView: Exception in response processing: {e}")


        return response