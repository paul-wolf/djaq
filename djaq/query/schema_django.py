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


# Process-wide cache of extracted entities, keyed by canonical model label.
# An Entity is derived purely from model._meta (table/columns/relations/join
# keys), which is static for the process, so it is safe to share across queries
# and providers. This is what amortises the per-query schema extraction.
_ENTITY_CACHE: dict = {}


def clear_schema_cache():
    """Forget all cached entities (e.g. for tests or after a schema change)."""
    _ENTITY_CACHE.clear()


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
        if label in self._cache:
            return self._cache[label]
        # resolve + enforce the whitelist on every call (auth is never cached)
        model = find_model_class(label, whitelist=self.whitelist)
        key = model._meta.label
        entity = _ENTITY_CACHE.get(key)
        if entity is None:  # extraction is the expensive part -- cache it process-wide
            entity = self.entity(model)
            _ENTITY_CACHE[key] = entity
        self._cache[label] = entity
        return entity

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


def check_drift(s: schema.Schema, connection) -> list:
    """Compare a Schema against a live database via introspection.

    Returns a list of human-readable drift messages (empty == no drift). This is
    what makes a hand-written, cached or AI-generated schema trustworthy: before
    Djaq generates SQL from it, you can confirm every table, column and join key
    actually exists in the target database.
    """
    cursor = connection.cursor()
    tables = set(connection.introspection.table_names(cursor))
    _cols: dict = {}

    def cols(table):
        if table not in _cols:
            if table in tables:
                desc = connection.introspection.get_table_description(cursor, table)
                _cols[table] = {c.name for c in desc}
            else:
                _cols[table] = set()
        return _cols[table]

    problems = []
    for e in s.entities.values():
        if e.table not in tables:
            problems.append(f"missing table {e.table!r} for entity {e.key!r}")
            continue
        ecols = cols(e.table)
        for f in e.fields.values():
            if f.column not in ecols:
                problems.append(
                    f"missing column {e.table}.{f.column} for field {e.key}.{f.name}"
                )
        for r in e.relations.values():
            if r.link_table and r.link_table not in tables:
                problems.append(
                    f"missing link table {r.link_table!r} for relation {e.key}.{r.name}"
                )
            for jk in tuple(r.keys) + tuple(r.link_keys):
                for table, column in (
                    (jk.left_table, jk.left_column),
                    (jk.right_table, jk.right_column),
                ):
                    if table not in tables:
                        problems.append(
                            f"missing join table {table!r} for relation {e.key}.{r.name}"
                        )
                    elif column not in cols(table):
                        problems.append(
                            f"missing join column {table}.{column} for relation {e.key}.{r.name}"
                        )

    return list(dict.fromkeys(problems))  # dedupe, preserve order
