"""Produce a :class:`~djaq.query.schema.Schema` from Django models.

This is the only Django-coupled code in the query path. It reads model metadata
once and emits the declarative :mod:`~djaq.query.schema` contract; everything
downstream (resolver, generator) depends only on that contract. Other providers
(hand-written, AI-generated, loaded from JSON) produce the same artefact.
"""

from django.db.models.fields.related import (
    ForeignKey,
    ManyToManyField,
    ManyToManyRel,
    ManyToOneRel,
    OneToOneField,
)

from . import schema
from ..app_utils import find_model_class


#: Django internal field type -> Djaq's neutral type taxonomy.
_TYPE_MAP = {
    "AutoField": "int",
    "SmallAutoField": "int",
    "BigAutoField": "bigint",
    "IntegerField": "int",
    "SmallIntegerField": "int",
    "BigIntegerField": "bigint",
    "PositiveIntegerField": "int",
    "PositiveSmallIntegerField": "int",
    "PositiveBigIntegerField": "bigint",
    "FloatField": "float",
    "DecimalField": "decimal",
    "BooleanField": "bool",
    "CharField": "string",
    "SlugField": "string",
    "EmailField": "string",
    "URLField": "string",
    "GenericIPAddressField": "string",
    "FileField": "string",
    "ImageField": "string",
    "TextField": "text",
    "DateField": "date",
    "DateTimeField": "datetime",
    "TimeField": "time",
    "DurationField": "duration",
    "UUIDField": "uuid",
    "JSONField": "json",
    "BinaryField": "binary",
}


def neutral_type(internal: str) -> str:
    """Map a Django internal type name to Djaq's neutral taxonomy."""
    if internal in _TYPE_MAP:
        return _TYPE_MAP[internal]
    # best-effort fallback: "FooBarField" -> "foobar"
    return internal[:-5].lower() if internal.endswith("Field") else internal.lower()


def _choices(f) -> tuple:
    return tuple(tuple(c) for c in (f.choices or ()))


class DjangoSchemaProvider:
    def __init__(self, whitelist=None):
        self.whitelist = whitelist
        self._cache: dict = {}

    def get_entity(self, label) -> schema.Entity:
        """Return the Entity for a model label, extracting (and caching) on demand.

        ``find_model_class`` enforces the whitelist, so traversing to a model that
        the caller may not access raises ``ModelNotFoundException`` here -- this is
        where Djaq circumscribes the data a (possibly remote) query can reach.
        """
        if label not in self._cache:
            model = find_model_class(label, whitelist=self.whitelist)
            self._cache[label] = self.entity(model)
        return self._cache[label]

    def entity(self, model) -> schema.Entity:
        meta = model._meta
        fields: dict = {}
        relations: dict = {}

        for f in meta.get_fields():
            if isinstance(f, ManyToManyField):
                relations[f.name] = self._m2m(meta, f)
            elif isinstance(f, ForeignKey):  # includes OneToOneField
                kind = "o2o" if isinstance(f, OneToOneField) else "fk"
                fields[f.name] = schema.Field(
                    f.name,
                    f.column,
                    neutral_type(f.target_field.get_internal_type()),
                    _choices(f),
                )
                relations[f.name] = schema.Relation(
                    f.name,
                    kind,
                    f.related_model._meta.label,
                    keys=tuple(
                        schema.JoinKey(
                            fk.model._meta.db_table,
                            fk.column,
                            tgt.model._meta.db_table,
                            tgt.column,
                        )
                        for fk, tgt in f.related_fields
                    ),
                )
            elif isinstance(f, ManyToManyRel):
                continue  # reverse m2m: not yet supported
            elif isinstance(f, ManyToOneRel):  # includes OneToOneRel
                relations[f.name] = self._reverse(f)
            elif getattr(f, "concrete", False):
                fields[f.name] = schema.Field(
                    f.name, f.column, neutral_type(f.get_internal_type()), _choices(f)
                )

        return schema.Entity(
            key=meta.label,
            name=model.__name__,
            table=meta.db_table,
            pk=meta.pk.column,
            fields=fields,
            relations=relations,
        )

    def _reverse(self, f) -> schema.Relation:
        # f.model is the source (the entity being described); f.related_model the target.
        keys = tuple(
            schema.JoinKey(
                f.model._meta.db_table,
                f_from,
                f.related_model._meta.db_table,
                f_to,
            )
            for f_from, f_to in f.get_joining_columns()
        )
        return schema.Relation(f.name, "reverse", f.related_model._meta.label, keys=keys)

    def _m2m(self, source_meta, f) -> schema.Relation:
        link_table = f.m2m_db_table()
        target_meta = f.related_model._meta
        # source <-> link
        link_keys = (
            schema.JoinKey(
                link_table, f.m2m_column_name(), source_meta.db_table, source_meta.pk.column
            ),
        )
        # link <-> target
        keys = (
            schema.JoinKey(
                target_meta.db_table,
                target_meta.pk.column,
                link_table,
                f.m2m_reverse_name(),
            ),
        )
        return schema.Relation(
            f.name,
            "m2m",
            target_meta.label,
            keys=keys,
            link_table=link_table,
            link_keys=link_keys,
        )

    def schema_from(self, models) -> schema.Schema:
        s = schema.Schema()
        for model in models:
            s.add(self.entity(model))
        return s
