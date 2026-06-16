from django.urls import path
from . import views
from django.views.generic import RedirectView

urlpatterns = [
    path("app/", views.app, name="app"),
    path("app/<uuid:chat_uuid>/", views.app, name="chat_session"),
    path("", RedirectView.as_view(url="/app/", permanent=False), name="root_redirect"),
    path("api/chat/", views.gemini_chat, name="gemini_chat"),
    # Chat history API
    path("api/sessions/", views.list_sessions, name="list_sessions"),
    path("api/sessions/create/", views.create_session, name="create_session"),
    path("api/sessions/<uuid:session_id>/", views.get_session, name="get_session"),
    path("api/sessions/<uuid:session_id>/rename/", views.rename_session, name="rename_session"),
    path("api/sessions/<uuid:session_id>/pin/", views.toggle_pin_session, name="toggle_pin_session"),
    path("api/sessions/<uuid:session_id>/share/", views.share_session, name="share_session"),
    path("api/sessions/shared-links/", views.list_shared_links, name="list_shared_links"),
    path("api/sessions/<uuid:session_id>/delete/", views.delete_session, name="delete_session"),
    path("api/sessions/delete-all/", views.delete_all_sessions, name="delete_all_sessions"),
    # Public shared chat view
    path("share/<str:share_id>/", views.view_shared_chat, name="view_shared_chat"),
]
