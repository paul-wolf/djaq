import timeit
import time
import importlib

from django.db.models import Q, Avg, Count, Min, Max, Sum, FloatField

from xquery.exp import XQuery as XQ

from books.models import Author, Publisher, Book, Store

def timeit(method):
    """Decorator to print timing of function call."""

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if 'log_time' in kw:
            name = kw.get('log_name', method.__name__.upper())
            kw['log_time'][name] = int((te - ts) * 1000)
        else:
            print('%r  %2.2f ms' % \
                  (method.__name__, (te - ts) * 1000))
        return result
    return timed

def sql(queryset):
    """Get sql source for a queryset."""
    sql, sql_params = queryset.query.get_compiler(using=queryset.db).as_sql()
    return sql

@timeit
def q_avg_price(**kwargs):
    xq = XQ("(avg(b.price)) Book b")
    l = []
    for rec in xq.tuples():
        l.append(rec)

@timeit
def q_avg_price_queryset(**kwargs):
    
    l = []
    qs = Book.objects.all().aggregate(Avg('price'))

    for rec in qs:
        l.append(rec)

@timeit
def q_all_books(**kwargs):
    xq = XQ("(b.id, b.name) Book b")
    l = []
    for rec in xq.tuples():
        l.append(rec)

@timeit
def q_all_books_queryset(**kwargs):

    l = []
    qs = Book.objects.all()
    print(sql(qs))
    for rec in qs:
        l.append(rec)

@timeit
def q_diff_avg_price(**kwargs):
    l = []
    xq = XQ("(Publisher.name, max(Book.price) - avg(Book.price) as price_diff) Book b")
    for rec in xq.tuples():
        l.append(rec)


@timeit
def q_diff_avg_price_queryset(**kwargs):

    l = []
    qs = Book.objects.aggregate(price_diff=Max('price', output_field=FloatField()) - Avg('price'))
    for rec in qs:
        l.append(rec)


@timeit
def q_books_per_publisher():

    l = []
    xq = XQ("(Publisher.name, count(Book.id) as num_books) Book b")
    for rec in xq.tuples():
        l.append(rec)

@timeit
def q_books_per_publisher_queryset():

    l = []
    qs = Publisher.objects.annotate(num_books=Count('book'))
    for rec in qs:
        l.append(rec)

@timeit
def q_books_avg_min_max():

    l = []
    xq = XQ("(avg(b.price), max(b.price), min(b.price)) Book b")
    for rec in xq.tuples():
        l.append(rec)
    

@timeit
def q_books_avg_min_max_queryset():

    l = []
    qs = Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))
    for rec in qs:
        l.append(rec)

def run():
    """Run all functions in this module starting with 'q_'. """

    m = importlib.import_module(__name__)
    funcs = [f for f in dir(m) if f.startswith('q_')]
    for funcname in funcs:
        func = getattr(m, funcname)
        func()

