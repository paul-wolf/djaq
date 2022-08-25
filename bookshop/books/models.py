from django.db import models
from django.contrib.auth.models import User

from django.db.models.signals import post_save
from django.dispatch import receiver


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


CATEGORY_CHOICES = (
    ("F", "Fiction"),
    ("N", "Non-fiction"),
)

GENRE_CHOICES = (
    ("O", "Other"),
    ("F", "Fantasy"),
    ("A", "Adventure"),
    ("R", "Romance"),
    ("M", "Mystery"),
    ("H", "Horror"),
    ("T", "Thriller"),
    ("S", "Science fiction"),
)


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
    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES, default="N")
    genre = models.CharField(max_length=1, choices=GENRE_CHOICES, default="O")

    # def save(self, *args, **kwargs):
    #     try:
    #         ISBN.objects.get(book=self)
    #     except ISBN.DoesNotExist:
    #         ISBN.objects.create(book=self)
    #     super().save(*args, **kwargs)

    def __str__(self):
        return self.name


@receiver(post_save, sender=Book)
def create_ISBN(sender, instance, created, **kwargs):
    try:
        ISBN.objects.get(book=instance)
    except ISBN.DoesNotExist:
        ISBN.objects.create(book=instance)


class ISBN(models.Model):
    code = models.CharField(max_length=20)
    book = models.OneToOneField(Book, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.code:
            # not unique, we don't care
            self.code = "978-3-16-148410-0"
        super().save(*args, **kwargs)


class Store(models.Model):
    name = models.CharField(max_length=300)
    books = models.ManyToManyField(Book)

    def __str__(self):
        return self.name
