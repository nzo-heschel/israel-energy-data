import psycopg2
import urllib.parse as urlparse

from storage import Storage, fix_date, unfix_date, unfix_time, dict_key_value

POSTGRES_CREATE_TABLE = "CREATE TABLE IF NOT EXISTS main_table " \
                        "(namespace VARCHAR(80), date DATE, time TIME, tag VARCHAR(20), value REAL, " \
                        "CONSTRAINT main_table_pk PRIMARY KEY (namespace, date, time, tag))"

POSTGRES_INSERT = "INSERT INTO main_table VALUES "

POSTGRES_CONFLICT = "ON CONFLICT ON CONSTRAINT main_table_pk DO UPDATE SET value = EXCLUDED.value"

SQL_RETRIEVE = "SELECT * FROM main_table " \
               "WHERE namespace = '{namespace}'"

SQL_AND_DATE = " AND date = '{date}'"
SQL_AND_DATE_RANGE = " AND date BETWEEN '{from_date}' AND '{to_date}'"
SQL_AND_TIME = " AND time = '{time}'"
SQL_AND_TAG = " AND tag = '{tag}'"

SQL_SUM = "SELECT namespace, date, to_char(time, 'HH24') as hour, tag, SUM(value) from main_table " \
          "WHERE namespace = '{namespace}' "
SQL_SUM_DAY = "SELECT namespace, date, '00:00', tag, SUM(value) from main_table " \
              "WHERE namespace = '{namespace}' "
SQL_GROUP_BY_DATE = " GROUP BY namespace, date, tag"
SQL_GROUP_BY_HOUR = " GROUP BY namespace, date, hour, tag"


class PostgresStorage(Storage):
    def __init__(self):
        self.conn = self._init_connection()
        curr = self.conn.cursor()
        curr.execute(POSTGRES_CREATE_TABLE)
        self.conn.commit()
        curr.close()

    def _init_connection(self):
        url = urlparse.urlparse("postgres://postgres:postgrespw@localhost:55000")
        dbname = url.path[1:]
        user = url.username
        password = url.password
        host = url.hostname
        port = url.port
        return psycopg2.connect(dbname=dbname, user=user, password=password, host=host, port=port)

    def clear(self):
        curr = self.conn.cursor()
        curr.execute("DROP TABLE main_table")
        curr.execute(POSTGRES_CREATE_TABLE)
        curr.close()

    def retrieve_value(self, namespace, date, time, tag):
        curr = self.conn.cursor()
        query = (SQL_RETRIEVE+SQL_AND_DATE+SQL_AND_TIME+SQL_AND_TAG) \
            .format(namespace=namespace, date=fix_date(date), time=time, tag=tag)
        curr.execute(query)
        records = curr.fetchall()
        curr.close()
        return records[0][-1] if records else None

    def insert(self, namespace, date, time, tag, value):
        self.bulk_insert([(namespace, fix_date(date), time, tag, value)])

    def bulk_insert(self, values):
        # TODO: fix date if reached here directly
        query = POSTGRES_INSERT + (",".join([self._fix(v) for v in values])) + POSTGRES_CONFLICT
        curr = self.conn.cursor()
        curr.execute(query)
        curr.close()

    def retrieve(self, namespace, date, tag=None, time="all"):
        return self._retrieve(namespace=namespace, date=fix_date(date), tag=tag, time=time)

    def retrieve_range(self, namespace, from_date, to_date, tag=None, time="day"):
        return self._retrieve(namespace, date_from=fix_date(from_date), date_to=fix_date(to_date), tag=tag, time=time)

    def _retrieve(self, namespace, date=None, date_from=None, date_to=None, tag=None, time="all"):
        if date and tag and time not in ["all", "day", "hour"]:
            date = fix_date(date)
            value = self.retrieve_value(namespace, date, time, tag)
            return {namespace: {unfix_date(date): {time: {tag: value}}}}
        if date:
            sql_and_date = SQL_AND_DATE.format(date=date)
        else:
            sql_and_date = SQL_AND_DATE_RANGE.format(from_date=date_from, to_date=date_to)
        if time == "day":
            query = (SQL_SUM_DAY + sql_and_date + (SQL_AND_TAG if tag else "") + SQL_GROUP_BY_DATE) \
                .format(namespace=namespace, tag=tag)
        elif time == "hour":
            query = (SQL_SUM + sql_and_date + (SQL_AND_TAG if tag else "") + SQL_GROUP_BY_HOUR) \
                .format(namespace=namespace, tag=tag)
        else:
            query = (SQL_RETRIEVE + sql_and_date +
                     (SQL_AND_TIME if time != "all" else "") +
                     (SQL_AND_TAG if tag else "")) \
                .format(namespace=namespace, time=time, tag=tag)
        curr = self.conn.cursor()
        curr.execute(query)
        records = curr.fetchall()
        curr.close()
        return self._records_to_dict(records)

    def _records_to_dict(self, records):
        d = {}
        for record in records:
            (namespace, date, time, tag, value) = record
            date = unfix_date(date)
            time = unfix_time(time)  # remove seconds
            ns = dict_key_value(d, namespace)
            dt = dict_key_value(ns, date)
            tm = dict_key_value(dt, time)
            tm[tag] = value
        return d

    def _fix(self, value):
        return "('{}', '{}', '{}', '{}', {})".format(value[0], fix_date(value[1]), value[2], value[3], value[4])
