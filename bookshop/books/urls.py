from django.contrib import admin
from django.urls import path, re_path, include

from . import views

urlpatterns = [
    path("price_average/", views.books_average_price),
    path("books/", views.books),
    path("book_list/", views.book_list),
]
