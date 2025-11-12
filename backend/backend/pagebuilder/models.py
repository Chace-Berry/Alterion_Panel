from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Page(models.Model):
    """
    Represents a user-created page in the page builder.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pages')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    blocks_json = models.JSONField(default=list, help_text="JSON array of page blocks")
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        unique_together = ['user', 'slug']

    def __str__(self):
        return f"{self.title} ({self.slug})"
