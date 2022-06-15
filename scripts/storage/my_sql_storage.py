from scripts.storage.sql_storage import SqlStorageTemplate
import mysql.connector
from furl import furl


class MySqlStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = "as new_value ON DUPLICATE KEY UPDATE value=new_value.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM_HOUR = "SELECT namespace, date, hour(time), tag, SUM(value) from main_table " \
                   "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, time('00:00'), tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, hour(time), tag"

    def __init__(self, uri):
        self.url = furl(uri)
        self.db = self._init_connection()
        self._execute_query("CREATE DATABASE IF NOT EXISTS main_table")
        self.db = self._init_connection(database="main_table")
        self._execute_query(self.SQL_CREATE_TABLE)

    def _init_connection(self, database=None):
        user = self.url.username
        password = self.url.password
        host = self.url.host
        port = self.url.port or 3306
        if database:
            return mysql.connector.connect(host=host, user=user, password=password, port=port, database=database)
        else:
            return mysql.connector.connect(host=host, user=user, password=password, port=port)
