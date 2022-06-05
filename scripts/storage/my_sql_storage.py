from sql_storage import SqlStorageTemplate
import mysql.connector


class MySqlStorage(SqlStorageTemplate):

    SQL_ON_CONFLICT = "as new_value ON DUPLICATE KEY UPDATE value=new_value.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM = "SELECT namespace, date, hour(time), tag, SUM(value) from main_table " \
              "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, time('00:00'), tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, hour(time), tag"

    def __init__(self, name="energy_data"):
        self.db = mysql.connector.connect(host='localhost', user='root', password='mysql_root_123')
        self._execute_query("CREATE DATABASE IF NOT EXISTS " + name)
        self.db = mysql.connector.connect(host='localhost', database=name, user='root', password='mysql_root_123')
        self._execute_query(self.SQL_CREATE_TABLE)
