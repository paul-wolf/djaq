import sys
import traceback

from django.core.management.base import BaseCommand, CommandError

from books.data_factory import build_data


class Command(BaseCommand):
    help = "Build data"

    def add_arguments(self, parser):

        parser.add_argument(
            "--book-count", default=1000, action="store", dest="book_count", type=int
        )

    def handle(self, *args, **options):
        build_data(book_count=options.get("book_count"))
