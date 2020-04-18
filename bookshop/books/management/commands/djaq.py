import sys
import traceback

from django.core.management.base import BaseCommand, CommandError

from djaq.query import DjangoQuery as DQ


class Command(BaseCommand):
    help = "Interpret string"

    def add_arguments(self, parser):
        parser.add_argument("src", type=str)
        parser.add_argument(
            "--format",
            default="dicts",  # dicts, tuples, json, csv
            action="store",
            dest="format",
            type=str,
        )

        parser.add_argument(
            "--limit", default=10, action="store", dest="limit", type=int
        )

        parser.add_argument(
            "--offset", default=0, action="store", dest="offset", type=int
        )

    def handle(self, *args, **options):
        q = DQ(
            options.get("src"),
            limit=options.get("limit"),
            offset=options.get("offset"),
            verbosity=3,
        )
        for rec in getattr(q, options.get("format"))():
            print(rec)
