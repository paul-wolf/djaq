import sys
import json
import traceback

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from djaq import DjaqQuery as DQ
from djaq.app_utils import make_dataclass


class Command(BaseCommand):
    help = "Interpret string"

    def add_arguments(self, parser):
        parser.add_argument("model", type=str, help="The model name; can be fully qualified")
        parser.add_argument("--output", type=str, help="Comma-separated list of field expressions")
        parser.add_argument("--where", type=str, help="A boolean expression that narrows results")
        parser.add_argument("--order_by", type=str, help="Comma-separated list of field expression for ordering the results")
        parser.add_argument(
            "--format",
            default="dicts",  # dicts, tuples, json, csv
            action="store",
            dest="format",
            type=str,
            help="one of: dicts, tuples, json, csv" 
        )
        parser.add_argument("--schema",
                            action="store_true",
                            default=False,
                            )
        parser.add_argument("--dataclass",
                            action="store_true",
                            default=False,
                            )

        parser.add_argument(
            "--limit", default=10, action="store", dest="limit", type=int
        )

        parser.add_argument(
            "--offset", default=0, action="store", dest="offset", type=int
        )

        parser.add_argument("--distinct",
                            action="store_true",
                            default=False,
                            )
        
        parser.add_argument("--sql",
                            action="store_true",
                            default=False,
                            )
        parser.add_argument("--count",
                            action="store_true",
                            default=False,
                            )
        # parser.add_argument(
        #     "--verbosity", default=0, action="store", dest="verbosity", type=int
        # )

    def handle(self, *args, **options):
        if options.get("schema"):
            if options.get("model"):
                print(json.dumps(DQ(options.get("model")).schema, cls=DjangoJSONEncoder, indent=4))
                return
            print(json.dumps(DQ.schema_all(), cls=DjangoJSONEncoder, indent=4))
            return 
        
        if options.get("dataclass"):
            if options.get("model"):
                make_dataclass(options.get("model"))
            return 
            
        q = DQ(
            options.get("model"),
            options.get("output"),
        )
        if options.get("where"):
            q = q.where(options.get("where"))

        if options.get("order_by"):
            q = q.order_by(options.get("order_by"))

        q = q.limit(options.get("limit"))

        q = q.offset(options.get("offset"))
        if options.get("distinct"):
            q = q.distinct()

        if options.get("sql"):
            print(q.sql())
            return
        if options.get("count"):
            print(q.count())
            return

        if options.get("format") == "dicts":
            print(json.dumps(list(q.dicts()), cls=DjangoJSONEncoder, indent=4))
        else:
            for rec in getattr(q, options.get("format"))():
                print(rec)
