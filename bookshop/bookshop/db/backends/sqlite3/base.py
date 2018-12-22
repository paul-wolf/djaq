import time
import logging

from django.db.backends.utils import CursorWrapper
from django.db.backends.sqlite3.base import (
    DatabaseWrapper as DjangoDatabaseWrapper
)

from django.conf import settings

logger = logging.getLogger(__name__)


class CustomCursorWrapper(CursorWrapper):
    """Bitposter custom cursor wrapper."""

    def execute(self, sql, params=None):
        start = time.time()
        result = super()._execute_with_wrappers(sql, params, many=False, executor=self._execute)
        end = time.time()
        t = end - start
        return result

    def executemany(self, sql, param_list):
        start = time.time()
        result = super()._execute_with_wrappers(sql, param_list, many=True, executor=self._executemany)
        end = time.time()
        t = end - start
        return result


class DatabaseWrapper(DjangoDatabaseWrapper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def create_cursor(self, name=None):
        from django.db.backends.sqlite3 import base
        cursor = base.DatabaseWrapper.create_cursor(self, name=name)
        return CustomCursorWrapper(cursor, self)
