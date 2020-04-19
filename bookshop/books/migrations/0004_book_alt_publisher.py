# Generated by Django 3.0.5 on 2020-04-19 08:22

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [("books", "0003_auto_20200418_1949")]

    operations = [
        migrations.AddField(
            model_name="book",
            name="alt_publisher",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="alt_publisher",
                to="books.Publisher",
            ),
        )
    ]
