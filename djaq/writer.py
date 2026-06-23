"""The write side of Djaq.

Command-query separation: ``DjaqQuery`` reads and never mutates; ``Writer``
mutates and never returns query results. A Writer performs create/update/delete
through the Django ORM, so model defaults, validation and signals fire exactly
as users expect -- unlike ``QuerySet.update()``/bulk operations, which silently
skip them. Updates are therefore per-instance (``obj.save()``).

Group writes atomically with :func:`transaction` (Shape A): it is a thin wrapper
over Django's connection-scoped ``transaction.atomic``, so any Writer call inside
the block participates::

    w = Writer()
    w.create("Author", {"name": "Sue", "age": 40})      # one-off, autocommit

    with transaction():                                  # all-or-nothing
        w.update("Book", pk, {"price": 5})
        w.delete("Book", other_pk)
"""

from django.db import transaction as _db_transaction

from .app_utils import find_model_class


def transaction(using="default"):
    """An atomic boundary for grouping writes (commit on exit, rollback on error)."""
    return _db_transaction.atomic(using=using)


class Writer:
    """ORM-honouring create/update/delete, scoped by an optional whitelist."""

    def __init__(self, whitelist=None, using="default"):
        self.whitelist = whitelist
        self.using = using

    def _model(self, entity):
        return find_model_class(entity, whitelist=self.whitelist)

    def get(self, entity, pk):
        """Return a model instance by pk (the write side owns instance retrieval)."""
        return self._model(entity).objects.using(self.using).get(pk=pk)

    def create(self, entity, fields):
        """Create a row, honouring defaults/validation/signals. Returns the new pk."""
        model = self._model(entity)
        obj = model.objects.using(self.using).create(**fields)
        return obj.pk

    def update(self, entity, pk, fields):
        """Update one row by pk via ``instance.save()`` (signals fire).

        Returns 1 if updated, 0 if no row matched.
        """
        model = self._model(entity)
        try:
            obj = model.objects.using(self.using).get(pk=pk)
        except model.DoesNotExist:
            return 0
        for name, value in fields.items():
            setattr(obj, name, value)
        obj.save(using=self.using)
        return 1

    def delete(self, entity, pk):
        """Delete one row by pk via ``instance.delete()`` (signals fire).

        Returns 1 if deleted, 0 if no row matched.
        """
        model = self._model(entity)
        try:
            obj = model.objects.using(self.using).get(pk=pk)
        except model.DoesNotExist:
            return 0
        obj.delete(using=self.using)
        return 1
