import sys
import json
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

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
        # parser.add_argument(
        #     "--verbosity", default=0, action="store", dest="verbosity", type=int
        # )

    def handle(self, *args, **options):
        q = DQ(
            options.get("src"),
            limit=options.get("limit"),
            offset=options.get("offset"),
            verbosity=options.get("verbosity"),
        )
        if options.get("format") == "dicts":
            print(json.dumps(list(q.dicts()), cls=DjangoJSONEncoder, indent=4))
        else:
            for rec in getattr(q, options.get("format"))():
                print(rec)
