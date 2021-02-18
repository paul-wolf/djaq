from django.contrib import admin
from django.urls import path, re_path, include


urlpatterns = [
    path("admin/", admin.site.urls),
    path("dquery/", include("djaq.djaq_ui.urls")),
    path("djaq/", include("djaq.djaq_api.urls")),
    path("books/", include("books.urls")),
]
