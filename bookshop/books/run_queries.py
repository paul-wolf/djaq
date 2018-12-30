import timeit
import time
import importlib
import traceback

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
    xq = XQ("""
    (Publisher.name, max(Book.price) - 
    avg(Book.price) as price_diff) Book b
    """)
    for rec in xq.tuples():
        l.append(rec)


@timeit
def q_diff_avg_price_queryset(**kwargs):

    l = []
    qs = Book.objects.aggregate(price_diff=Max('price', output_field=FloatField()) - Avg('price'))
    for rec in qs:
        l.append(rec)


@timeit
def q_books_per_publisher(**kwargs):

    l = []
    xq = XQ("(Publisher.name, count(Book.id) as num_books) Book b")
    for rec in xq.tuples():
        l.append(rec)


@timeit
def q_books_per_publisher_queryset(**kwargs):

    l = []
    qs = Publisher.objects.annotate(num_books=Count('book'))
    for rec in qs:
        l.append(rec)


@timeit
def q_books_avg_min_max(**kwargs):

    l = []
    xq = XQ("(avg(b.price), max(b.price), min(b.price)) Book b")
    for rec in xq.tuples():
        l.append(rec)
    

@timeit
def q_books_avg_min_max_queryset(**kwargs):

    l = []
    qs = Book.objects.aggregate(Avg('price'), Max('price'), Min('price'))
    for rec in qs:
        l.append(rec)

@timeit
def q_sub_query(**kwargs):

    xq_sub = XQ("(b.id) Book{name == 'B*'} b", name='xq_sub')
    xq = XQ("(b.name, b.price) Book{id in '@xq_sub'} b")
    l = []
    for rec in xq.tuples():
        l.append(l)

@timeit
def q_sub_queryset(**kwargs):

    qs = Book.objects.filter(name__startswith="B").only('id')
    xq = XQ("(b.name, b.price) Book{id in '@qs_sub'} b", data={"qs_sub": qs})
    l = []
    for rec in xq.tuples():
        l.append(l)

@timeit
def q_sub_list(**kwargs):

    qs = Book.objects.filter(name__startswith="B").only('id')
    ids = [rec.id for rec in qs]
    xq = XQ("(b.name, b.price) Book{id in '@qs_sub'} b", data={"qs_sub": ids}, verbosity=0)

    l = []
    for rec in xq.tuples():
        l.append(l)

@timeit
def q_params(**kwargs):

    # xq = XQ("(b.id, b.name) Book{b.id == 108955 or regex(b.name, 'I .*') and b.name == 'Personal occur admit play.'} b ", verbosity=kwargs['verbosity'])
            
    xq = XQ("(b.id, b.name) Book{b.id == '%s' and regex(b.name, '%s')} b ", verbosity=kwargs['verbosity'])
            

    qs = Book.objects.filter(name__startswith="B").only('id')
    ids = [rec.id for rec in qs][:3]
    # xq = XQ("(b.name, b.price) Book{id in '@qs_sub'} b", data={"qs_sub": ids}, verbosity=3)

    l = []
    for rec in xq.tuples(parameters=[135794, 'I.*']):
        print(rec)
        

@timeit
def q_grouping(**kwargs):
            
    xq = XQ("(b.id, b.name) Book{(b.id == 1 or b.id == 2) and b.id == 3} b ",            
            verbosity=kwargs['verbosity'])
            

    qs = Book.objects.filter(name__startswith="B").only('id')
    ids = [rec.id for rec in qs][:3]
    l = []
    for rec in xq.limit(10).tuples(parameters=[135794, 'I.*']):
        print(rec)
        
@timeit
def q_implicit_model(**kwargs):
    str(XQ("(Book.name, Book.id)"))
    
@timeit
def q_rewind(**kwargs):
    xq = XQ("(b.name) Book b")
    l = []
    for rec in xq.tuples():
        l.append(rec)
    l = []
    for rec in xq.rewind().tuples():
        l.append(rec)
    
@timeit
def q_rewind_queryset(**kwargs):
    qs = Book.objects.all()
    l = []
    for rec in qs:
        l.append(rec)
    l = []
    for rec in qs:
        l.append(rec)
    

@timeit
def q_conditional_sum(**kwargs):
    xq = XQ("""
    (sum(iif(b.rating >= 3, b.rating, 0)) as below_3, sum(iif(b.rating > 3, b.rating, 0)) as above_3) Book b
        """)
    for rec in xq.tuples():
        print(rec)

@timeit
def q_conditional_sum_queryset(**kwargs):
    above_3 = Count('book', filter=Q(book__rating__gt=3))
    below_3 = Count('book', filter=Q(book__rating__lte=3))
    qs = Publisher.objects.annotate(below_3=below_3).annotate(above_3=above_3)
    l = []
    for rec in qs:
        l.append(rec)

def run(options):
    """Run all functions in this module starting with 'q_'. """

    m = importlib.import_module(__name__)

    funcname = options.get('funcname')
    if funcname:
        getattr(m, funcname)(**options)
        return

    for funcname in [f for f in dir(m) if f.startswith('q_')]:
        try:
            print("----------------------- {}".format(funcname))
            getattr(m, funcname)(**options)
        except Exception as e:
            traceback.print_exc()
