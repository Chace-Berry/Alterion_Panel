from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Page
from .serializers import PageSerializer


class PageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for CRUD operations on Page model.
    Users can only access their own pages.
    """
    serializer_class = PageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Filter pages by current user"""
        return Page.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """Set user to current user on page creation"""
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Toggle published status of a page"""
        page = self.get_object()
        page.published = not page.published
        page.save()
        return Response({
            'published': page.published,
            'message': f"Page {'published' if page.published else 'unpublished'} successfully"
        })

    @action(detail=True, methods=['get'])
    def export_jsx(self, request, pk=None):
        """Export page as JSX component code"""
        page = self.get_object()
        jsx_code = self.generate_jsx(page)
        return Response({
            'jsx': jsx_code,
            'filename': f"{page.slug}.jsx"
        })

    def generate_jsx(self, page):
        """Generate React JSX code from blocks_json"""
        blocks = page.blocks_json
        components_code = []
        
        for block in blocks:
            block_type = block.get('type')
            props = block.get('props', {})
            
            if block_type == 'heading':
                level = props.get('level', 'h1')
                text = props.get('text', '')
                color = props.get('color', '#ffffff')
                components_code.append(f"  <{level} style={{ color: '{color}' }}>{text}</{level}>")
            
            elif block_type == 'text':
                text = props.get('text', '')
                fontSize = props.get('fontSize', '16px')
                color = props.get('color', '#ffffff')
                components_code.append(f"  <p style={{ fontSize: '{fontSize}', color: '{color}' }}>{text}</p>")
            
            elif block_type == 'image':
                src = props.get('src', '')
                alt = props.get('alt', 'Image')
                width = props.get('width', '100%')
                components_code.append(f"  <img src=\"{src}\" alt=\"{alt}\" style={{ width: '{width}' }} />")
            
            elif block_type == 'button':
                text = props.get('text', 'Button')
                href = props.get('href', '#')
                color = props.get('color', '#3b82f6')
                components_code.append(
                    f"  <a href=\"{href}\" style={{ background: '{color}', padding: '10px 20px', "
                    f"borderRadius: '6px', textDecoration: 'none', color: 'white' }}>{text}</a>"
                )
            
            elif block_type == 'container':
                padding = props.get('padding', '20px')
                background = props.get('background', 'rgba(255,255,255,0.05)')
                components_code.append(f"  <div style={{ padding: '{padding}', background: '{background}' }}>")
                components_code.append("    {/* Add nested content here */}")
                components_code.append("  </div>")
        
        components_str = '\n'.join(components_code)
        
        jsx = f"""import React from 'react';

const {page.slug.replace('-', '_').title()} = () => {{
  return (
    <div className="page-container">
{components_str}
    </div>
  );
}};

export default {page.slug.replace('-', '_').title()};
"""
        return jsx
