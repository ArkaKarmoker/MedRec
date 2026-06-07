from django.db import models
from django.contrib.auth.models import User


class ChatSession(models.Model):
    """Represents a single chat conversation for a user."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_sessions')
    title = models.CharField(max_length=255, default='New Chat')
    is_pinned = models.BooleanField(default=False)
    share_id = models.CharField(max_length=36, null=True, blank=True, unique=True, db_index=True)
    shared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-updated_at']

    def __str__(self):
        return f"{self.title} ({self.user.username})"


class ChatMessage(models.Model):
    """Represents a single message within a chat session."""
    ROLE_CHOICES = [
        ('user', 'User'),
        ('bot', 'Bot'),
    ]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    model_name = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
