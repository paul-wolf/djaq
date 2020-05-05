from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    company = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return "{self.user.username} ({self.company})"


class Author(models.Model):
    name = models.CharField(max_length=100)
    age = models.IntegerField()

    def __str__(self):
        return self.name


class Consortium(models.Model):
    name = models.CharField(max_length=30)
    marketcap = models.IntegerField(default=9999999)


class Publisher(models.Model):
    name = models.CharField(max_length=300)
    owner = models.ForeignKey(Consortium, on_delete=models.CASCADE, null=True)

    def __str__(self):
        return self.name


class Book(models.Model):

    name = models.CharField(max_length=300)
    pages = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    rating = models.FloatField()
    authors = models.ManyToManyField(Author)
    publisher = models.ForeignKey(Publisher, on_delete=models.CASCADE)
    alt_publisher = models.ForeignKey(
        Publisher, related_name="alt_publisher", on_delete=models.CASCADE, null=True
    )
    pubdate = models.DateField()
    in_print = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Store(models.Model):
    name = models.CharField(max_length=300)
    books = models.ManyToManyField(Book)

    def __str__(self):
        return self.name
