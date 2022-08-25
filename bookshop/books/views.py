import logging

from django.http import JsonResponse
from django.http import HttpResponseServerError
from django.shortcuts import render
from django.conf import settings
from django.db.models import Avg

from djaq.query import DjaqQuery as DQ
from djaq.conditions import B

from .models import Book
from .forms import BookForm

logger = logging.getLogger(__name__)


class PriceEngine:
    def get_average_price(self):
        price_data = Book.objects.all().aggregate(Avg("price"))
        return float(price_data["price__avg"])


def books_average_price(request):
    price_data = Book.objects.all().aggregate(Avg("price"))
    return JsonResponse({"price": float(price_data["price__avg"])})


def books_average_price(request):
    price_engine = PriceEngine()
    price = price_engine.get_average_price()
    return JsonResponse({"price": price})


def books(request):
    """Present a search form for books."""

    section = {"title": "Show me books"}
    book_form = BookForm()
    data = {"section": section, "book_form": book_form, "settings": settings}
    return render(request, "books.html", data)


def book_list(request):
    """Get the list of books based on search form values.

    AJAX view

    We assume this will be a POST.

    """

    try:

        # define optional expressions for each search value
        c = (
            B("regex(b.name, '$(name)')")
            & B("b.pages > '$(pages)'")
            & B("b.rating > '$(rating)'")
            & B("b.price > '$(price)'")
        )

        # construct the query and get results as dicts, maximum of 20 records
        books = list(
            DQ(
                "(b.name as name, b.price as price, b.rating as rating, b.pages as pages, b.publisher.name as publisher) Book b"
            )
            .conditions(c)  # add our conditions here
            .context(request.POST)  # add our context data here
            .limit(20)
            .dicts()
        )

        # return the rendered html
        return render(request, "book_list.html", {"books": books})
    except Exception as e:
        print(e)
        logger.exception(e)
        return HttpResponseServerError(e)
