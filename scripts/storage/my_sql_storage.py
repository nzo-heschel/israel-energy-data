from scripts.storage.sql_storage import SqlStorageTemplate
import mysql.connector
from furl import furl
import logging


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
        self.db = self._init_connection()
        self._execute_query("CREATE DATABASE IF NOT EXISTS energy_data")
        self.db = self._init_connection(database=energy_db_name)
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

    def _get_db_cursor(self):
        try:
            return self.db.cursor()
        except mysql.connector.errors.OperationalError:
            logging.info("Renew database connection")
            self.db = self._init_connection(energy_db_name)
            return self.db.cursor()
