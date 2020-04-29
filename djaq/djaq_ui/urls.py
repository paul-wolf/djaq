from django.urls import path
from django.contrib.auth.views import LoginView

from .views import query_view, schema_view


urlpatterns = (path("", query_view), path("schema/", schema_view))
