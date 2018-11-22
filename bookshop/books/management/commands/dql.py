import ast

from django.core.management.base import BaseCommand, CommandError

from xquery.exp import XQuery
from xquery.app_utils import *


class Command(BaseCommand):
    help = 'Interpret string'

    def add_arguments(self, parser):
        parser.add_argument('src', type=str)

    def handle(self, *args, **options):
        xq = XQuery(options.get('src'))
        sql = xq.parse()

        print(sql)

        try:
            for rec in xq.dicts():
                print(rec)
        except Exception as e:
            print(e)
        
