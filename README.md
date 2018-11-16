# dql
django query language

Django Query Language
=====================

https://tomassetti.me/ebnf/
https://tomassetti.me/parsing-in-python/
https://ipfs.io/ipfs/QmXoypizjW3WknFiJnKLwHCnL72vedxjQkDDP1mXWo6uco/wiki/Recursive_descent_parser.html
http://books.agiliq.com/projects/django-orm-cookbook/en/latest/or_query.html
https://stackoverflow.com/questions/34119721/simple-programming-language-in-ebnf-form
Get sql from queryset:

https://stackoverflow.com/questions/10168935/parsing-nested-function-calls-using-pyparsing

    sql, sql_params = queryset.query.get_compiler(using=queryset.db).as_sql()

User.username
User -> extendeduser.moc



##Aggregation

https://docs.djangoproject.com/en/2.1/topics/db/aggregation/

    pubs = Publisher.objects.annotate(num_books=Count('book'))
    pubs = q("""(p.name, avg(b.price)): Publisher p
       <- Book b 
    """)
    

    pubs = q("Book b -> Publisher p [p.name, count(b.id) as num_books]")


    above_5 = Count('book', filter=Q(book__rating__gt=5))

    above_5 = q("Book{rating > 5} [count(*)]")
    above_5 = q("(count(*)): Book{rating > 5}")


    Book.objects.aggregate(Avg('price'))
    {'price__avg': 34.35}

    XQuery("Book [avg(price)]").as_int()
    34.35
    
    qs = Book.objects.annotate(Count('authors'))
    
    qx = q("Book [count(authors)]")
    
    
    Store.objects.annotate(min_price=Min('books__price'), max_price=Max('books__price'))
    
    q("Store{condition} s -> Book b [s.name, min(b.price) as min_price, max(b.price as max_price]")
    
    
    Author.objects.values('name').annotate(average_rating=Avg('book__rating'))
    
    q("(avg(Book.rating) as average_rating): Author a")
    
[u.username, u.email, x.oc] User u {(username.startswith('paul') | username == 'chris') & email ~ '@bitposter.co'} -> extendeduser x

xq = XQuery("

(x.oc.lower() as org_code, upper(x.organisation.name), count(*)): 
	User {(username ~ 'paul' or username == $name) & email ~ i'@bitposter.co'} u
		-> Extendeduser x
		-> Organisation o
		<- some query /* right join */
        <-> some other query /* inner join */

")

xq['count']

	User u {(username ~ 'paul' | username == 'chris') & email ~ i'@bitposter.co' & id in somelist} 
		-> Extendeduser x
		-> Organisation o
		-> `SELECT * FROM someothertable WHERE blah = 'blah'`
		-> otherXQ q
		-> (SELECT * FROM someothertable WHERE id IN `[i for i in list_of_i]`)
		-> some_queryset
[x.oc as org_code, x.organisation.name, count(*), q.*]

group_by x.oc, x.organisation.name
order_by x.organisation.name

Integer representing staff count:

    staff_count = XQuery("User [count(is_staff)]").as_int()
    staff_count = q("(count(*)): User").as_int()
    staff_count = q("(count(*)): User")[0]['count']
    
All staff, all fields:

    staff = XQuery("User{is_staff == TRUE} [*]").as_list() # list of dicts
    XQuery("User{is_staff == TRUE} [*]").as_generator() # generator of dicts
    cursor = XQuery("User{is_staff == TRUE} [*]").as_cursor() 

```python
User.objects.filter(Q(username__icontains='paul') | Q(username='chris') & Q(email__icontains='@bitposter.co')) 
```

```sql
('SELECT "auth_user"."id", "auth_user"."password", "auth_user"."last_login", "auth_user"."is_superuser", "auth_user"."username", "auth_user"."first_name", "auth_user"."last_name", "auth_user"."email", "auth_user"."is_staff", "auth_user"."is_active", "auth_user"."date_joined" FROM "auth_user" WHERE (UPPER("auth_user"."username"::text) LIKE UPPER(%s) OR ("auth_user"."username" = %s AND UPPER("auth_user"."email"::text) LIKE UPPER(%s)))',
 ('%paul%', 'chris', '%@bitposter.co%'))
```

qs = User.objects.filter(Q(username__icontains='paul') | Q(username='chris') & Q(email__icontains='@bitposter.co')) 
qs.values("x__oc, x__organisation__name").annotate(cnt=Count())

(x.oc, x.organisation.name, count(*)): 
User{(username == '%paul%' or username == 'chris') and email == '%@bitposter'} u 
-> ExtendedUser x


http://www.try-alf.org/blog/2014-12-03-what-would-a-functional-sql-look-like

https://cse.buffalo.edu/~mpetropo/notes/O2/OQLTutorial

http://effbot.org/zone/simple-top-down-parsing.htm

https://tomassetti.me/parsing-in-python/

https://docs.python.org/3/library/tokenize.html

http://lucumr.pocoo.org/2015/11/18/pythons-hidden-re-gems/

https://gist.github.com/eliben/5797351
