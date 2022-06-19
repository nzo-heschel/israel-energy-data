from scripts.storage.sql_storage import SqlStorageTemplate
from scripts.storage.storage_top import fix_date
import psycopg2
from furl import furl


class PostgresStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = "ON CONFLICT ON CONSTRAINT main_table_pk DO UPDATE SET value = EXCLUDED.value"
    SQL_AND_DATE = " AND date = '{date}'"
    SQL_AND_DATE_RANGE = " AND date BETWEEN '{from_date}' AND '{to_date}'"
    SQL_AND_TIME = " AND time = '{time}'"
    SQL_SUM_HOUR = "SELECT namespace, date, to_char(time, 'HH24') as hour, tag, SUM(value) from main_table " \
                   "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, '00:00', tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY namespace, date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY namespace, date, hour, tag"

    def __init__(self, uri):
        self.url = furl(uri)
        self.db = self._init_connection()
        self._execute_query(self.SQL_CREATE_TABLE)

    def _init_connection(self):
        user = self.url.username
        password = self.url.password
        host = self.url.host
        port = self.url.port
        return psycopg2.connect(user=user, password=password, host=host, port=port)

    def bulk_insert(self, values):
        # in postgres we can't have duplicates in the same command.
        if len(values) > 1:
            values_dict = {}
            for value in values:
                values_dict[str(value[:-1])] = value
            values = values_dict.values()
        self._execute_query(self.SQL_INSERT + (",".join([self._fix(v) for v in values])) + self.SQL_ON_CONFLICT)

    def _fix(self, value):
        return "('{}', '{}', '{}', '{}', {})".format(value[0], fix_date(value[1]), value[2], value[3], value[4])
