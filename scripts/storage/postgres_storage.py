from sql_storage import SqlStorageTemplate
from storage import fix_date
import psycopg2
import urllib.parse as urlparse


class PostgresStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = "ON CONFLICT ON CONSTRAINT main_table_pk DO UPDATE SET value = EXCLUDED.value"
    SQL_AND_DATE = " AND date = '{date}'"
    SQL_AND_DATE_RANGE = " AND date BETWEEN '{from_date}' AND '{to_date}'"
    SQL_AND_TIME = " AND time = '{time}'"
    SQL_SUM = "SELECT namespace, date, to_char(time, 'HH24') as hour, tag, SUM(value) from main_table " \
              "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, '00:00', tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY namespace, date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY namespace, date, hour, tag"

    def __init__(self):
        self.db = self._init_connection()
        self._execute_query(self.SQL_CREATE_TABLE)

    def _init_connection(self):
        url = urlparse.urlparse("postgres://postgres:postgrespw@localhost:55000")
        dbname = url.path[1:]
        user = url.username
        password = url.password
        host = url.hostname
        port = url.port
        return psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)

    def _fix(self, value):
        return "('{}', '{}', '{}', '{}', {})".format(value[0], fix_date(value[1]), value[2], value[3], value[4])
