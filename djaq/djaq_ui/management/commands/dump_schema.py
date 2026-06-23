"""Dump the Djaq schema (declarative facts) for apps as JSON.

    ./manage.py dump_schema                  # every installed app
    ./manage.py dump_schema books            # one app
    ./manage.py dump_schema books auth       # several apps
    ./manage.py dump_schema books -o schema.json

The JSON is the portable schema artefact: it can be cached, diffed across
migrations, hand-edited, fed to an AI, or loaded back with ``Schema.from_json``
to drive Djaq with no Django.
"""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError

from djaq.query.schema_django import DjangoSchemaProvider


class Command(BaseCommand):
    help = "Dump the Djaq schema for one or more apps (or all) as JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "apps", nargs="*", help="App labels to dump; omit for all installed apps."
        )
        parser.add_argument(
            "-o", "--output", help="Write to this file instead of stdout."
        )
        parser.add_argument("--indent", type=int, default=2)

    def handle(self, *args, **options):
        labels = options["apps"]
        if labels:
            models = []
            for label in labels:
                try:
                    models.extend(apps.get_app_config(label).get_models())
                except LookupError as exc:
                    raise CommandError(str(exc))
        else:
            models = list(apps.get_models())

        schema = DjangoSchemaProvider().schema_from(models)
        text = schema.to_json(indent=options["indent"])

        if options["output"]:
            with open(options["output"], "w") as fh:
                fh.write(text + "\n")
            self.stderr.write(
                f"wrote {len(schema.entities)} entities to {options['output']}"
            )
        else:
            self.stdout.write(text)
