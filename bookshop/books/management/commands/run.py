import sys
import traceback

from django.core.management.base import BaseCommand, CommandError

from books.run_queries import run


class Command(BaseCommand):
    help = "run tests"

    def add_arguments(self, parser):

        parser.add_argument(
            "--funcname", default=None, action="store", dest="funcname", type=str
        )

        parser.add_argument("--v", action="store", dest="verbose", default=0, type=int)

        parser.add_argument("--sql", default=False, action="store_true", dest="sql")

    def handle(self, *args, **options):

        run(options)
