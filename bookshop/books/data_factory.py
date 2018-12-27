import random

import factory
from faker import Faker

from books.models import Author, Publisher, Book, Store

fake = Faker()

class AuthorFactory(factory.Factory):
    class Meta:
        model = Author

    name = fake.name()
    age = random.choice(range(20, 80))

class PublisherFactory(factory.Factory):
    class Meta:
        model = Publisher

    name = fake.company()

class BookFactory(factory.Factory):
    class Meta:
        model = Book

    name = factory.Faker('sentence', nb_words=4)
    # authors = factory.Iterator(Author.objects.all())

    pages = random.choice(range(100, 800))
    price = random.choice(range(3, 35))
    rating = random.choice(range(5))
    publisher = factory.Iterator(Publisher.objects.all())
    pubdate = fake.date_this_century(before_today=True, after_today=False)
    
    # @factory.post_generation
    # def authors(self, create, extracted, **kwargs):
    #     if not create:
    #         return
    #     else:
    #         authors = Author.objects.all().order_by('?')[:3]
    #         # self.authors.add(authors)


                
class StoreFactory(factory.Factory):
    class Meta:
        model = Store

    name = fake.company()

    # @factory.post_generation
    # def books(self, create, extracted, **kwargs):
    #     if create:
    #         books = Book.objects.all().order_by('?')[:30]
    #         for book in books:
    #             self.books.add(book)

                
def build_data(book_count=None):

    authors = []
    publishers = []
    books = []
    
    if not book_count:
        book_count = 1000

    COUNT_PUBLISHERS = book_count * 0.1
    COUNT_STORES = book_count * 0.2
    COUNT_AUTHORS = book_count * 1.5

    while Author.objects.all().count() < COUNT_AUTHORS:
        author = AuthorFactory.create(name=fake.name(),
                                      age=random.choice(range(20, 80))).save()
        authors.append(author)
    else:
        authors = list(Author.objects.all())
        
    while Publisher.objects.all().count() < COUNT_PUBLISHERS:
        publishers.append(PublisherFactory.create(name=fake.company()).save())
    else:
        publishers = list(Publisher.objects.all())

    while Book.objects.all().count() < book_count:
        book = BookFactory.create(
            name = factory.Faker('sentence', nb_words=4),
            pages = random.choice(range(100, 800)),
            price = random.choice(range(3, 35)),
            rating = random.choice(range(5)),
            publisher = Publisher.objects.all().order_by('?')[0],
            pubdate = fake.date_this_century(before_today=True, after_today=False)
        )
        book.save()
        authors = Author.objects.all().order_by('?')[:3]
        for author in authors:
            book.authors.add(author)
    else:
        books = list(Book.objects.all())

    while Store.objects.all().count() < COUNT_STORES:
        store = StoreFactory.create(name=fake.company())
        store.save()
        books = Book.objects.all().order_by('?')[:150]
        for book in books:
            store.books.add(book)
            
            
    

        
