"""Benchmark Djaq against the Django QuerySet API.

Separates two phases:

* BUILD  -- turning a query spec into SQL. Django QuerySets are lazy, so this is
            their compile step (``str(qs.query)``). For Djaq it is
            ``construct()`` (frontend -> resolver -> generator). Djaq is shown
            both "cold" (a fresh schema extraction per query, the naive default)
            and "warm" (a reused provider, so schema extraction is amortised).
* EXEC   -- the database round-trip plus materialising rows to dicts. Roughly
            equal work for both; dominated by the DB.

Data is created inside a rolled-back transaction, so the database is left
untouched. Run against any backend, e.g.::

    DJAQ_DB=postgres ./manage.py benchmark --rows 2000
"""

import datetime
import random
from time import perf_counter

from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.db.models import Avg, Count, Q

from djaq import DjaqQuery as DQ
from djaq.query.schema_django import DjangoSchemaProvider

from books.models import Book, Publisher, Author


def measure(fn, iterations, warmup=3):
    """Return (min, mean) wall time per call, in seconds."""
    for _ in range(warmup):
        fn()
    times = []
    for _ in range(iterations):
        t0 = perf_counter()
        fn()
        times.append(perf_counter() - t0)
    return min(times), sum(times) / len(times)


def fmt(seconds):
    us = seconds * 1e6
    return f"{us:8.1f}us" if us < 1000 else f"{us / 1000:8.2f}ms"


# Each case: a label, a Djaq factory (optional provider for warm builds), and an
# equivalent QuerySet factory.
CASES = [
    (
        "select id, name",
        lambda p=None: DQ("Book", "id, name", provider=p),
        lambda: Book.objects.values("id", "name"),
    ),
    (
        "fk join publisher.name",
        lambda p=None: DQ("Book", "name, publisher.name", provider=p),
        lambda: Book.objects.values("name", "publisher__name"),
    ),
    (
        "filter price > 15",
        lambda p=None: DQ("Book", "id, name", provider=p).where("price > 15"),
        lambda: Book.objects.filter(price__gt=15).values("id", "name"),
    ),
    (
        "group avg(price)",
        lambda p=None: DQ("Book", "publisher.name, avg(price)", provider=p),
        lambda: Book.objects.values("publisher__name").annotate(a=Avg("price")),
    ),
    (
        "sumif conditional agg",
        lambda p=None: DQ(
            "Book",
            "publisher.name, sumif(rating < 3, 1, 0) as below, "
            "sumif(rating >= 3, 1, 0) as above",
            provider=p,
        ),
        lambda: Publisher.objects.values("name").annotate(
            below=Count("book", filter=Q(book__rating__lt=3)),
            above=Count("book", filter=Q(book__rating__gte=3)),
        ),
    ),
]


class Command(BaseCommand):
    help = "Compare Djaq vs Django QuerySet build/exec timing."

    def add_arguments(self, parser):
        parser.add_argument("--rows", type=int, default=2000)
        parser.add_argument("--iterations", type=int, default=300)

    def handle(self, *args, **opts):
        with transaction.atomic():
            self._populate(opts["rows"])
            self._report(opts["iterations"])
            transaction.set_rollback(True)  # leave the database untouched

    def _populate(self, rows):
        random.seed(0)
        Publisher.objects.bulk_create([Publisher(name=f"Pub {i}") for i in range(10)])
        Author.objects.bulk_create([Author(name=f"Auth {i}", age=30) for i in range(10)])
        pubs = list(Publisher.objects.all())
        pubdate = datetime.date(2021, 1, 1)
        Book.objects.bulk_create(
            [
                Book(
                    name=f"Book {i}",
                    pages=random.randint(50, 900),
                    price=random.randint(3, 40),
                    rating=random.randint(0, 5),
                    publisher=random.choice(pubs),
                    pubdate=pubdate,
                )
                for i in range(rows)
            ]
        )

    def _report(self, iterations):
        self.stdout.write(
            f"\nbackend={connection.vendor}  rows={Book.objects.count()}  "
            f"iterations={iterations}\n"
        )

        warm_provider = DjangoSchemaProvider()  # shared -> schema extracted once

        header = f"{'case':<24} {'Djaq cold':>11} {'Djaq warm':>11} {'Django':>11}"
        self.stdout.write("\nBUILD (spec -> SQL)")
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for label, djaq, qs in CASES:
            cold, _ = measure(lambda: djaq().sql(), iterations)
            warm, _ = measure(lambda: djaq(warm_provider).sql(), iterations)
            django, _ = measure(lambda: str(qs().query), iterations)
            self.stdout.write(
                f"{label:<24} {fmt(cold):>11} {fmt(warm):>11} {fmt(django):>11}"
            )

        header2 = f"{'case':<24} {'Djaq':>11} {'Django':>11} {'rows':>8}"
        self.stdout.write("\nEXEC (round-trip + materialise dicts)")
        self.stdout.write(header2)
        self.stdout.write("-" * len(header2))
        for label, djaq, qs in CASES:
            # build once, then time execute + fetch only (no reconstruct)
            parser = djaq().parser
            parser.construct()

            def djaq_exec():
                parser.rewind()
                return list(parser.dicts())

            def qs_exec():
                return list(qs())

            n = len(djaq_exec())
            d_min, _ = measure(djaq_exec, iterations)
            q_min, _ = measure(qs_exec, iterations)
            self.stdout.write(
                f"{label:<24} {fmt(d_min):>11} {fmt(q_min):>11} {n:>8}"
            )
        self.stdout.write("")
