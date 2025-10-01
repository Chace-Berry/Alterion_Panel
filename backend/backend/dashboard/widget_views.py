from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from authentication.cookie_oauth2 import CookieOAuth2Authentication
from django.contrib.auth import get_user_model
from accounts.models import WidgetLayout

User = get_user_model()


class WidgetLayoutView(APIView):
    """API for managing user widget layouts"""
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get user's widget layout"""
        try:
            widget_layout = WidgetLayout.objects.get(user=request.user)
            return Response({
                'layout': widget_layout.layout,
                'available_widgets': widget_layout.available_widgets
            })
        except WidgetLayout.DoesNotExist:
            # Return default layout if none exists
            default_layout = [
                {'i': 'alerts', 'x': 0, 'y': 0, 'w': 4, 'h': 3, 'minW': 3, 'minH': 2},
                {'i': 'traffic', 'x': 4, 'y': 0, 'w': 4, 'h': 3, 'minW': 3, 'minH': 2},
                {'i': 'uptime', 'x': 8, 'y': 0, 'w': 4, 'h': 3, 'minW': 3, 'minH': 2},
                {'i': 'performance', 'x': 0, 'y': 3, 'w': 6, 'h': 4, 'minW': 4, 'minH': 3},
                {'i': 'quick-actions', 'x': 6, 'y': 3, 'w': 6, 'h': 4, 'minW': 4, 'minH': 3},
                {'i': 'activity', 'x': 0, 'y': 7, 'w': 6, 'h': 3, 'minW': 4, 'minH': 2},
                {'i': 'domains', 'x': 6, 'y': 7, 'w': 6, 'h': 3, 'minW': 4, 'minH': 2},
            ]
            return Response({
                'layout': default_layout,
                'available_widgets': []
            })

    def post(self, request):
        """Save user's widget layout"""
        layout = request.data.get('layout', [])
        available_widgets = request.data.get('available_widgets', [])

        # Debug: Check what we're getting
        print(f"DEBUG: request.user = {request.user}, type = {type(request.user)}")
        print(f"DEBUG: User model = {User}")
        
        # Get the user ID directly to avoid any model instance issues
        try:
            if isinstance(request.user, str):
                user_obj = User.objects.get(username=request.user)
                user_id = user_obj.id
            elif hasattr(request.user, 'pk'):
                user_id = request.user.pk
                print(f"DEBUG: Got user_id from pk: {user_id}")
                # Verify user exists and fetch fresh instance
                user_obj = User.objects.get(pk=user_id)
                print(f"DEBUG: Fetched user_obj type: {type(user_obj)}, isinstance check: {isinstance(user_obj, User)}")
            elif hasattr(request.user, 'id'):
                user_id = request.user.id
                print(f"DEBUG: Got user_id from id: {user_id}")
                # Verify user exists
                user_obj = User.objects.get(pk=user_id)
            else:
                user_obj = User.objects.get(username=str(request.user))
                user_id = user_obj.id
            
            print(f"DEBUG: Final user_id = {user_id}, user_obj = {user_obj}, type = {type(user_obj)}")
            
        except User.DoesNotExist:
            return Response({
                'error': 'User not found'
            }, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(f"DEBUG: Exception getting user: {e}")
            return Response({
                'error': f'Authentication error: {str(e)}'
            }, status=status.HTTP_401_UNAUTHORIZED)

        # Use user_id for queries to avoid the "Must be User instance" error
        try:
            widget_layout = WidgetLayout.objects.get(user_id=user_id)
            widget_layout.layout = layout
            widget_layout.available_widgets = available_widgets
            widget_layout.save()
        except WidgetLayout.DoesNotExist:
            print(f"DEBUG: Creating new WidgetLayout with user_id={user_id}")
            # For creation, use the user object instead of user_id
            widget_layout = WidgetLayout.objects.create(
                user=user_obj,
                layout=layout,
                available_widgets=available_widgets
            )

        return Response({
            'status': 'success',
            'message': 'Widget layout saved successfully'
        }, status=status.HTTP_200_OK)


class WidgetLibraryView(APIView):
    """API for managing widget library (available widgets)"""
    authentication_classes = [CookieOAuth2Authentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get all available widgets from library"""
        try:
            widget_layout = WidgetLayout.objects.get(user=request.user)
            return Response({
                'available_widgets': widget_layout.available_widgets
            })
        except WidgetLayout.DoesNotExist:
            return Response({
                'available_widgets': []
            })

    def post(self, request):
        """Add a widget to the library (remove from dashboard)"""
        widget_id = request.data.get('widget_id')
        widget_config = request.data.get('widget_config', {})

        if not widget_id:
            return Response({
                'error': 'widget_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        widget_layout, created = WidgetLayout.objects.get_or_create(
            user=request.user,
            defaults={
                'layout': [],
                'available_widgets': []
            }
        )

        # Add to available widgets if not already there
        available = widget_layout.available_widgets
        if not any(w.get('id') == widget_id for w in available):
            available.append({
                'id': widget_id,
                'config': widget_config
            })
            widget_layout.available_widgets = available
            widget_layout.save()

        return Response({
            'status': 'success',
            'message': 'Widget added to library'
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        """Remove a widget from library (add back to dashboard)"""
        widget_id = request.data.get('widget_id')

        if not widget_id:
            return Response({
                'error': 'widget_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            widget_layout = WidgetLayout.objects.get(user=request.user)
            # Remove from available widgets
            widget_layout.available_widgets = [
                w for w in widget_layout.available_widgets 
                if w.get('id') != widget_id
            ]
            widget_layout.save()

            return Response({
                'status': 'success',
                'message': 'Widget removed from library'
            }, status=status.HTTP_200_OK)
        except WidgetLayout.DoesNotExist:
            return Response({
                'error': 'Widget layout not found'
            }, status=status.HTTP_404_NOT_FOUND)
