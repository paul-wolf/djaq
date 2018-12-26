import sys
import traceback

from django.core.management.base import BaseCommand, CommandError

from books.run_queries import run


class Command(BaseCommand):
    help = 'run tests'
    
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        run()
