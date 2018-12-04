import sys
import traceback

from django.core.management.base import BaseCommand, CommandError

from xquery.exp import XQuery as Q


class Command(BaseCommand):
    help = 'Interpret string'
    
    def add_arguments(self, parser):
        parser.add_argument('src', type=str)
        parser.add_argument('--format',
                            default='objs', # dicts, tuples, json
                            action='store',
                            dest='format',
                            type=str)

    def handle(self, *args, **options):
        xq = Q(options.get('src'), limit=10)
        try:
            for rec in getattr(xq, options.get('format'))():
                print(rec)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            print(e)
        
