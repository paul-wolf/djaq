from django.urls import path
from django.contrib.auth.views import LoginView

from .views import (
    query_view,
    schema_view,
    get_models,
    get_fields,
    sql_view,
    get_whitelist_view,
)


urlpatterns = (
    path("", query_view),
    path("schema/", schema_view),
    path("sql/", sql_view),
    path("models/<appname>/", get_models),
    path("fields/<modelname>/", get_fields),
    path("whitelist/", get_whitelist_view),
)
