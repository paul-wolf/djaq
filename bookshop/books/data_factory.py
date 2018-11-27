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

                
def build_data():

    authors = []
    publishers = []
    books = []
    
    if Author.objects.all().count() < 100:
        for i in range(100):
            author = AuthorFactory.create(name=fake.name(),
                                          age=random.choice(range(20, 80))).save()
            authors.append(author)
            
    else:
        authors = list(Author.objects.all())
        
    if Publisher.objects.all().count() < 10:
        for i in range(10):
            publishers.append(PublisherFactory.create(name=fake.company()).save())
    else:
        publishers = list(Publisher.objects.all())

    if Book.objects.all().count() < 500:
        for i in range(500):
            
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

    if Store.objects.all().count() < 20:
        for i in range(20):
            store = StoreFactory.create(name=fake.company())
            store.save()
            books = Book.objects.all().order_by('?')[:150]
            for book in books:
                store.books.add(book)
            
            
    

        
