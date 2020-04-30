from django.urls import path
from django.contrib.auth.views import LoginView

from .views import djaq_request_view, djaq_schema_view


urlpatterns = (
    path("api/request/", djaq_request_view),
    path("api/schema/", djaq_schema_view),
)
