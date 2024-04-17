from scripts.storage.storage_top import Storage, fix_date, unfix_date, unfix_time, dict_key_value


class SqlStorageTemplate(Storage):

    SQL_CREATE_TABLE = "CREATE TABLE IF NOT EXISTS main_table " \
                       "(namespace VARCHAR(80), date DATE, time TIME, tag VARCHAR(50), value REAL, " \
                       "CONSTRAINT main_table_pk PRIMARY KEY (namespace, date, time, tag))"

    SQL_INSERT = "INSERT INTO main_table VALUES "
    SQL_ON_CONFLICT = None

    SQL_RETRIEVE = "SELECT * FROM main_table " \
                   "WHERE namespace = '{namespace}'"

    SQL_LATEST_DATE = "SELECT max(date) from main_table WHERE namespace = '{namespace}'"

    SQL_AND_DATE = None
    SQL_AND_DATE_RANGE = None
    SQL_AND_TIME = None
    SQL_AND_TAG = " AND tag = '{tag}'"

    SQL_SUM_HOUR = None
    SQL_SUM_DAY = None
    SQL_SUM_MONTH = None
    SQL_GROUP_BY_DATE = None
    SQL_GROUP_BY_HOUR = None
    SQL_GROUP_BY_MONTH = None

    SQL_SIZE = "SELECT count(*) from main_table"

    def clear(self):
        self._execute_query("DROP TABLE main_table",
                            self.SQL_CREATE_TABLE)

    def _get_db_cursor(self):
        return self.db.cursor()

    def _get_records(self, query):
        curr = self._get_db_cursor()
        curr.execute(query)
        records = curr.fetchall()
        return records

    def _execute_query(self, *queries):
        curr = self._get_db_cursor()
        for query in queries:
            curr.execute(query)
        self.db.commit()

    def retrieve_value(self, namespace, date, time, tag):
        records = self._get_records((self.SQL_RETRIEVE+self.SQL_AND_DATE+self.SQL_AND_TAG+self.SQL_AND_TIME)
                                    .format(namespace=namespace, date=fix_date(date), time=time, tag=tag))
        return records[0][-1] if records else None

    def insert(self, namespace, date, time, tag, value):
        self.bulk_insert([(namespace, fix_date(date), time, tag, value)])

    def bulk_insert(self, values):
        self._execute_query(self.SQL_INSERT + (",".join([self._fix(v) for v in values])) + self.SQL_ON_CONFLICT)

    def retrieve(self, namespace, date, tag=None, time="all"):
        return self._retrieve(namespace=namespace, date=fix_date(date), tag=tag, time=time)

    def retrieve_range(self, namespace, from_date, to_date, tag=None, time="day"):
        return self._retrieve(namespace, date_from=fix_date(from_date), date_to=fix_date(to_date), tag=tag, time=time)

    def latest_date(self, namespace):
        records = self._get_records(self.SQL_LATEST_DATE.format(namespace=namespace))
        return unfix_date(records[0][0])

    def size(self):
        records = self._get_records(self.SQL_SIZE)
        return records[0][0]

    def _retrieve(self, namespace, date=None, date_from=None, date_to=None, tag=None, time="all"):
        if date and tag and time not in ["all", "day", "hour"]:
            date = fix_date(date)
            value = self.retrieve_value(namespace, date, time, tag)
            return {namespace: {unfix_date(date): {time: {tag: value}}}}
        if date:
            sql_and_date = self.SQL_AND_DATE.format(date=date)
        else:
            sql_and_date = self.SQL_AND_DATE_RANGE.format(from_date=date_from, to_date=date_to)
        sql_and_tag = self.SQL_AND_TAG if tag else ""
        if time == "month":
            query = (self.SQL_SUM_MONTH + sql_and_date + sql_and_tag + self.SQL_GROUP_BY_MONTH) \
                .format(namespace=namespace, tag=tag)
        elif time == "day":
            query = (self.SQL_SUM_DAY + sql_and_date + sql_and_tag + self.SQL_GROUP_BY_DATE) \
                .format(namespace=namespace, tag=tag)
        elif time == "hour":
            query = (self.SQL_SUM_HOUR + sql_and_date + sql_and_tag + self.SQL_GROUP_BY_HOUR) \
                .format(namespace=namespace, tag=tag)
        else:
            query = (self.SQL_RETRIEVE + sql_and_date +
                     (self.SQL_AND_TIME if time != "all" else "") +
                     (self.SQL_AND_TAG if tag else "")) \
                .format(namespace=namespace, time=time, tag=tag)
        records = self._get_records(query)
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
        return "('{}', date('{}'), time('{}'), '{}', {})"\
            .format(value[0], fix_date(value[1]), value[2], value[3], value[4])
