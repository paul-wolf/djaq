from django.urls import path

from . import views

urlpatterns = [
    path("price_average/", views.books_average_price),
    path("books/", views.books),
    path("book_list/", views.book_list),
]
