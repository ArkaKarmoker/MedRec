from django.urls import path
from . import views
from django.views.generic import RedirectView

urlpatterns = [
    path("app/", views.app, name="app"),
    path("", RedirectView.as_view(url="/app/", permanent=False), name="root_redirect"),
    path("api/chat/", views.gemini_chat, name="gemini_chat"),
]
