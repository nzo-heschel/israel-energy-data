from storage import Storage, fix_date, unfix_date, unfix_time, dict_key_value
import sqlite3

SQL_CREATE_TABLE = "CREATE TABLE IF NOT EXISTS main_table " \
                   "(namespace VARCHAR(80), date DATE, time TIME, tag VARCHAR(20), value REAL, " \
                   "CONSTRAINT main_table_pk PRIMARY KEY (namespace, date, time, tag))"

SQL_INSERT = "INSERT INTO main_table VALUES "
SQL_ON_CONFLICT = " ON CONFLICT(namespace, date, time, tag) DO UPDATE SET value=excluded.value"

SQL_RETRIEVE = "SELECT * FROM main_table " \
               "WHERE namespace IS '{namespace}'"

SQL_AND_DATE = " AND date IS date('{date}')"
SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
SQL_AND_TIME = " AND time is time('{time}')"
SQL_AND_TAG = " AND tag is '{tag}'"

SQL_SUM = "SELECT namespace, date, time, tag, SUM(value) from main_table " \
          "WHERE namespace IS '{namespace}' "
SQL_GROUP_BY_DATE = " GROUP BY date, tag"
SQL_GROUP_BY_HOUR = " GROUP BY date, strftime('%H', time), tag"


class InMemSqlStorage(Storage):
    def __init__(self, name="energy-data"):
        self.db = sqlite3.connect(name)
        curr = self.db.cursor()
        curr.execute(SQL_CREATE_TABLE)
        curr.close()

    def clear(self):
        curr = self.db.cursor()
        curr.execute("DROP TABLE main_table")
        curr.execute(SQL_CREATE_TABLE)
        curr.close()

    def retrieve_value(self, namespace, date, time, tag):
        c = self.db.execute((SQL_RETRIEVE+SQL_AND_DATE+SQL_AND_TAG+SQL_AND_TIME)
                            .format(namespace=namespace, date=fix_date(date), time=time, tag=tag))
        records = c.fetchall()
        return records[0][-1] if records else None

    def insert(self, namespace, date, time, tag, value):
        self.bulk_insert([(namespace, fix_date(date), time, tag, value)])

    def bulk_insert(self, values):
        # TODO: fix date if reached here directly
        query = SQL_INSERT + (",".join([self._fix(v) for v in values])) + SQL_ON_CONFLICT
        curr = self.db.cursor()
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
            query = (SQL_SUM + sql_and_date + (SQL_AND_TAG if tag else "") + SQL_GROUP_BY_DATE) \
                .format(namespace=namespace, tag=tag)
        elif time == "hour":
            query = (SQL_SUM + sql_and_date + (SQL_AND_TAG if tag else "") + SQL_GROUP_BY_HOUR) \
                .format(namespace=namespace, tag=tag)
        else:
            query = (SQL_RETRIEVE + sql_and_date +
                     (SQL_AND_TIME if time != "all" else "") +
                     (SQL_AND_TAG if tag else "")) \
                .format(namespace=namespace, time=time, tag=tag)
        c = self.db.execute(query)
        records = c.fetchall()
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
        return "('{}', date('{}'), time('{}'), '{}', {})".format(*value)
