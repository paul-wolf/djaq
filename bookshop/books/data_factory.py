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
    # authors =
    publisher = factory.Iterator(Publisher.objects.all())
    pubdate = fake.date_this_century(before_today=True, after_today=False)
    
    @factory.post_generation
    def authors(self, create, extracted, **kwargs):
        if not create:
            return
        else:
            for i in range(3):
                self.authors.add(factory.Iterator(Author.objects.all()))


                
class StoreFactory(factory.Factory):
    class Meta:
        model = Store

    name = fake.company()

    @factory.post_generation
    def books(self, create, extracted, **kwargs):
        if not create:
            return
        else:
            for i in range(30):
                self.books.add(factory.Iterator(Books.objects.all()))

                
def build_data():

    authors = []
    publishers = []
    books = []
    
    if Author.objects.all().count() < 100:
        authors = AuthorFactory.build_batch(100)
        for a in author:
            a.save()
    else:
        authors = list(Author.objects.all())
        
    if Publisher.objects.all().count() < 10:
        publishers = PublisherFactory.build_batch(10)
        for p in publishers:
            p.save()
    else:
        publishers = list(Publisher.objects.all())

    if Book.objects.all().count() < 500:
        books = BookFactory.build_batch(500)
        for b in books:
            b.save()
    else:
        books = list(Book.objects.all())

    if Store.objects.all().count() < 20:
        stores = StoreFactory.build_batch(10)
        for s in stores:
            s.save()
            
    

        
