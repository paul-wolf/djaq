from django.contrib import admin
from django.urls import path, re_path, include

from djaq.ui import urls as djaq_urls

urlpatterns = [path("admin/", admin.site.urls), path("query/", include("djaq.ui.urls"))]
