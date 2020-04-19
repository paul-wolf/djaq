import time
import importlib
import traceback

from django.db.models import (
    Q,
    Avg,
    Count,
    Min,
    Max,
    Sum,
    FloatField,
    Subquery,
    OuterRef,
)
from djaq.query import DjangoQuery as DQ
from books.models import Author, Publisher, Book, Store


def timeit(method):
    """Decorator to print timing of function call."""

    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()
        if "log_time" in kw:
            name = kw.get("log_name", method.__name__.upper())
            kw["log_time"][name] = int((te - ts) * 1000)
        else:
            print("===========> %s  %2.2f ms" % (method.__name__, (te - ts) * 1000))
        return result

    return timed


def sql(queryset):
    """Get sql source for a queryset."""
    sql, sql_params = queryset.query.get_compiler(using=queryset.db).as_sql()
    return sql


@timeit
def q_avg_price(**kwargs):
    dq = DQ("(avg(b.price)) Book b")
    a = []
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_avg_price_queryset(**kwargs):

    a = []
    qs = Book.objects.all().aggregate(Avg("price"))

    for rec in qs:
        a.append(rec)


@timeit
def q_all_books(**kwargs):
    dq = DQ("(b.id, b.name) Book b")
    a = []
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_all_books_queryset(**kwargs):

    a = []
    qs = Book.objects.all()
    #  print(sql(qs))
    for rec in qs:
        a.append(rec)


@timeit
def q_diff_avg_price(**kwargs):
    a = []
    dq = DQ(
        """
    (Publisher.name, max(Book.price) -
    avg(Book.price) as price_diff) Book b
    """
    )
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_diff_avg_price_queryset(**kwargs):

    a = []
    qs = Book.objects.aggregate(
        price_diff=Max("price", output_field=FloatField())
        - Avg("price", output_field=FloatField())
    )
    for rec in qs:
        a.append(rec)


@timeit
def q_books_per_publisher(**kwargs):

    a = []
    dq = DQ("(Publisher.name, count(Book.id) as num_books) Book b")
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_books_per_publisher_queryset(**kwargs):

    a = []
    qs = Publisher.objects.annotate(num_books=Count("book"))
    for rec in qs:
        a.append(rec)


@timeit
def q_books_avg_min_max(**kwargs):

    a = []
    dq = DQ("(avg(b.price), max(b.price), min(b.price)) Book b")
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_books_avg_min_max_queryset(**kwargs):

    a = []
    qs = Book.objects.aggregate(Avg("price"), Max("price"), Min("price"))
    for rec in qs:
        a.append(rec)


@timeit
def q_sub_query(**kwargs):

    dq_sub = DQ("(b.id) Book{name == 'B*'} b", name="dq_sub")  # noqa: F841
    list(DQ("(b.name, b.price) Book{id in '@dq_sub'} b").tuples())


@timeit
def q_sub_queryset(**kwargs):

    qs = Book.objects.filter(name__startswith="B").only("id")
    dq = DQ("(b.name, b.price) Book{id in '@qs_sub'} b", names={"qs_sub": qs})
    a = []
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_sub_list(**kwargs):

    qs = Book.objects.filter(name__startswith="B").only("id")
    ids = [rec.id for rec in qs]
    dq = DQ(
        "(b.name, b.price) Book{id in '@qs_sub'} b",
        names={"qs_sub": ids},
        verbosity=kwargs.get("verbose"),
    )

    a = []
    for rec in dq.tuples():
        a.append(rec)


@timeit
def q_params(**kwargs):

    DQ(
        """(b.id, b.name) Book{b.id == 1 or
    regex(b.name, '$(mynamepattern)')} b """,
        verbosity=kwargs["verbose"],
    )
    # print(str(dq.context({'mynamepattern':'I.*'})))

    # dq = DQ("""(b.id, b.name) Book{b.id == '$(myid)' or
    # regex(b.name, '$(mynamepattern)')} b """,
    # verbosity=kwargs['verbose'])

    # a = []
    # for rec in dq.context({'myid': 1, 'mynamepattern':'I%'}).tuples():
    #     a.append(rec)


@timeit
def q_grouping(**kwargs):

    dq = DQ(
        "(b.id, b.name) Book{(b.id == 1 or b.id == 2) and b.id == 3} b ",
        verbosity=kwargs["verbose"],
    )

    qs = Book.objects.filter(name__startswith="B").only("id")
    [rec.id for rec in qs][:3]
    a = []
    for rec in dq.limit(10).tuples():
        a.append(rec)


@timeit
def q_implicit_model(**kwargs):
    list(DQ("(Book.name, Book.id)").tuples())


@timeit
def q_ilike(**kwargs):
    name_pattern = "C%"  # noqa: F841
    list(DQ("(b.name) Book{ilike(b.name, '$(name_pattern)')} b ").tuples())
    #  print(str(dq.context({"name_pattern": "C%"})))

    #
    #  print(str(dq.rewind().context(locals())))


@timeit
def q_rewind(**kwargs):
    dq = DQ("(b.name) Book b")
    a = []
    for rec in dq.tuples():
        a.append(rec)
    a = []
    for rec in dq.rewind().tuples():
        a.append(rec)


@timeit
def q_rewind_queryset(**kwargs):
    qs = Book.objects.all()
    a = []
    for rec in qs:
        a.append(rec)
    a = []
    for rec in qs:
        a.append(rec)


@timeit
def q_conditional_sum(**kwargs):
    list(
        DQ(
            """
    (sum(iif(b.rating >= 3, b.rating, 0)) as below_3, sum(iif(b.rating > 3, b.rating, 0)) as above_3) Book b
        """
        ).tuples()
    )


@timeit
def q_subquery(**kwargs):

    pubs = DQ("(p.id) Publisher p", name="pubs")  # noqa: F841
    books = DQ("(b.name) Book{publisher in '@pubs'} b")
    if kwargs.get("sql"):
        print(books.query())
    a = []
    for rec in books.tuples():
        a.append(rec)


@timeit
def q_subquery_outerref(**kwargs):
    qs = Book.objects.filter(
        publisher__in=Subquery(
            Publisher.objects.filter(pk=OuterRef("publisher")).only("pk")
        )
    )
    if kwargs.get("sql"):
        print(sql(qs))
    a = []
    for rec in qs:
        a.append(rec)


@timeit
def q_count(**kwargs):
    #  print(DQ("(Book.id)").count())
    DQ("(count(Book.id)) Book").value()


@timeit
def q_count_queryset(**kwargs):
    Book.objects.all().count()


@timeit
def q_conditional_sum_queryset(**kwargs):
    above_3 = Count("book", filter=Q(book__rating__gt=3))
    below_3 = Count("book", filter=Q(book__rating__lte=3))
    qs = Publisher.objects.annotate(below_3=below_3).annotate(above_3=above_3)
    a = []
    for rec in qs:
        a.append(rec)


def run(options):
    """Run all functions in this module starting with 'q_'. """

    m = importlib.import_module(__name__)

    pattern = options.get("funcname")

    for funcname in [f for f in dir(m) if f.startswith("q_")]:
        try:

            if pattern:
                if funcname.startswith(pattern):
                    #  print("----------------------- {}".format(funcname))
                    getattr(m, funcname)(**options)
            else:
                #  print("----------------------- {}".format(funcname))
                getattr(m, funcname)(**options)
        except Exception as e:
            print(e)
            traceback.print_exc()
