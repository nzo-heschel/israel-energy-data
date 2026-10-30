from contextlib import contextmanager
import queue
import MySQLdb
import MySQLdb.cursors
from MySQLdb import constants, converters
from furl import furl

from scripts.storage.sql_storage import SqlStorageTemplate

energy_db_name = "energy_data"

# Return DATE and TIME columns as strings directly from C instead of allocating datetime.date/timedelta objects
_FAST_CONVERSIONS = converters.conversions.copy()
_FAST_CONVERSIONS[constants.FIELD_TYPE.DATE] = str
_FAST_CONVERSIONS[constants.FIELD_TYPE.TIME] = str


class MySqlStorage(SqlStorageTemplate):
    SQL_ON_CONFLICT = "as new_value ON DUPLICATE KEY UPDATE value=new_value.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM_HOUR = "SELECT namespace, date, hour(time), tag, SUM(value) from main_table " \
                   "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, time('00:00'), tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_SUM_MONTH = "SELECT namespace, date(concat_ws('-', year(date), month(date), 1)), '00:00', tag, SUM(value) from main_table " \
                    "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, hour(time), tag"
    SQL_GROUP_BY_MONTH = "GROUP BY date(concat_ws('-', year(date), month(date), 1)), tag"

    def __init__(self, uri):
        self.url = furl(uri)
        self._database = None
        self._pool = queue.LifoQueue(maxsize=5)
        self._execute_query("CREATE DATABASE IF NOT EXISTS energy_data")
        self._database = energy_db_name
        self._pool = queue.LifoQueue(maxsize=5)
        self._execute_query(self.SQL_CREATE_TABLE)

    def _create_conn(self):
        host = self.url.host or "127.0.0.1"
        if host == "localhost":
            host = "127.0.0.1"
        kwargs = {
            "user": self.url.username or "root",
            "passwd": self.url.password or "",
            "host": host,
            "port": self.url.port or 3306,
            "charset": "utf8mb4",
            "conv": _FAST_CONVERSIONS,
            "autocommit": False,
        }
        if self._database:
            kwargs["db"] = self._database
        return MySQLdb.connect(**kwargs)

    @contextmanager
    def _managed_cursor(self, commit=False):
        try:
            conn = self._pool.get_nowait()
            conn.ping(True)
        except queue.Empty:
            conn = self._create_conn()
        except Exception:
            conn = self._create_conn()

        cursor_cls = MySQLdb.cursors.Cursor if commit else MySQLdb.cursors.SSCursor
        cursor = conn.cursor(cursor_cls)
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                self._pool.put_nowait(conn)
            except queue.Full:
                conn.close()
