from furl import furl
from scripts.storage.sql_storage import SqlStorageTemplate
import sqlite3
from contextlib import contextmanager


class InMemSqlStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = " ON CONFLICT(namespace, date, time, tag) DO UPDATE SET value=excluded.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM_HOUR = "SELECT namespace, date, strftime('%H', time), tag, SUM(value) from main_table " \
                   "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, '00:00', tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_SUM_MONTH = "SELECT namespace, strftime('%Y-%m-01', date), '00:00', tag, SUM(value) from main_table " \
                    "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, strftime('%H', time), tag"
    SQL_GROUP_BY_MONTH = " GROUP BY strftime('%Y-%m-01', date), tag"

    def __init__(self, uri="sqlite://energy-data"):
        self.url = furl(uri)
        file_name = str(self.url.host)
        self.db = sqlite3.connect(file_name, check_same_thread=False)
        self._execute_query(self.SQL_CREATE_TABLE)

    @contextmanager
    def _managed_cursor(self, commit=False):
        cursor = self.db.cursor()
        try:
            yield cursor
            if commit:
                self.db.commit()
        finally:
            cursor.close()
