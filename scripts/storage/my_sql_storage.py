from contextlib import contextmanager

from mysql.connector.pooling import MySQLConnectionPool

from scripts.storage.sql_storage import SqlStorageTemplate
from furl import furl

energy_db_name = "energy_data"


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
        self.pool = self._init_pool()
        self._execute_query("CREATE DATABASE IF NOT EXISTS energy_data")
        self.pool = self._init_pool(database=energy_db_name)
        self._execute_query(self.SQL_CREATE_TABLE)

    def _init_pool(self, database=None):
        user = self.url.username
        password = self.url.password
        host = self.url.host
        port = self.url.port or 3306
        db_config = {
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }
        if database:
            db_config["database"] = database
        return MySQLConnectionPool(pool_name="mysql_pool", pool_size=5, **db_config)

    @contextmanager
    def _managed_cursor(self, commit=False):
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()
            conn.close()
