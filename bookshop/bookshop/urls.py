from django.contrib import admin
from django.urls import path, re_path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("query/", include("djaq.djaq_ui.urls")),
]
