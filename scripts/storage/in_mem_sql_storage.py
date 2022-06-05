from sql_storage import SqlStorageTemplate
import sqlite3


class InMemSqlStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = " ON CONFLICT(namespace, date, time, tag) DO UPDATE SET value=excluded.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM = "SELECT namespace, date, time, tag, SUM(value) from main_table " \
              "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = SQL_SUM
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, strftime('%H', time), tag"

    def __init__(self, name="energy-data"):
        self.db = sqlite3.connect(name)
        self._execute_query(self.SQL_CREATE_TABLE)
