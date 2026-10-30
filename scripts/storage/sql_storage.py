from contextlib import contextmanager
from datetime import datetime, time as dt_time, timedelta
import logging
import time as time_module
import numpy as np
import pandas as pd

from scripts.storage.storage_top import Storage, fix_date, unfix_date, unfix_time, dict_key_value


class SqlStorageTemplate(Storage):
    SQL_CREATE_TABLE = "CREATE TABLE IF NOT EXISTS main_table " \
                       "(namespace VARCHAR(80), date DATE, time TIME, tag VARCHAR(50), value REAL, " \
                       "CONSTRAINT main_table_pk PRIMARY KEY (namespace, date, time, tag))"

    SQL_INSERT = "INSERT INTO main_table VALUES "
    SQL_ON_CONFLICT = None

    SQL_RETRIEVE = "SELECT * FROM main_table " \
                   "WHERE namespace = '{namespace}'"
    SQL_RETRIEVE_COLUMNS = "SELECT date, time, tag, value FROM main_table " \
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

    @contextmanager
    def _managed_cursor(self, commit=False):
        raise NotImplementedError

    def _get_records(self, query):
        with self._managed_cursor() as curr:
            curr.execute(query)
            records = curr.fetchall()
            return records

    def _execute_query(self, *queries):
        with self._managed_cursor(commit=True) as curr:
            for query in queries:
                curr.execute(query)

    def retrieve_value(self, namespace, date, time, tag):
        records = self._get_records((self.SQL_RETRIEVE + self.SQL_AND_DATE + self.SQL_AND_TAG + self.SQL_AND_TIME)
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

    def retrieve_tag_dataframes(self, namespace, from_date, to_date):
        fixed_from = fix_date(from_date)
        fixed_to = fix_date(to_date)
        start_dt = datetime.strptime(fixed_from, "%Y-%m-%d")
        end_dt = datetime.strptime(fixed_to, "%Y-%m-%d")
        max_days = (end_dt - start_dt).days + 1
        if max_days <= 0:
            return {}, None, 0

        all_dates = [start_dt + timedelta(days=i) for i in range(max_days)]
        date_to_col = {}
        for i, dt in enumerate(all_dates):
            date_to_col[dt.strftime("%Y-%m-%d")] = i
            date_to_col[dt.date()] = i

        times_str = [f"{h:02d}:{m:02d}" for h in range(24) for m in range(0, 60, 5)]
        time_to_row = {}
        for idx, t in enumerate(times_str):
            h, m = int(t[:2]), int(t[3:5])
            time_to_row[t] = idx
            time_to_row[f"{t}:00"] = idx
            time_to_row[f"{h}:{m:02d}:00"] = idx
            time_to_row[dt_time(h, m)] = idx
        # Noga has spurious data on 28-05-2024,12:18 (no data for 12:15 so map 12:18 -> 12:15)
        # and 03-07-2025,14:36 (omitted from time_to_row so it maps to None and is skipped)
        r_1215 = time_to_row["12:15"]
        time_to_row["12:18"] = r_1215
        time_to_row["12:18:00"] = r_1215
        time_to_row[dt_time(12, 18)] = r_1215

        sql_and_date = self.SQL_AND_DATE_RANGE.format(from_date=fixed_from, to_date=fixed_to)
        query = (self.SQL_RETRIEVE_COLUMNS + sql_and_date).format(namespace=namespace)

        t0 = time_module.perf_counter()
        seen_cols = [False] * max_days
        arrays = {}
        mvs = {}
        row_count = 0
        item_count = 0
        last_dt = None
        last_tm = None
        r = None
        c = -1
        flat_idx = None

        with self._managed_cursor() as curr:
            curr.execute(query)
            while True:
                batch = curr.fetchmany(50000)
                if not batch:
                    break
                row_count += len(batch)
                for dt_val, tm_val, tag_val, val in batch:
                    if tm_val != last_tm:
                        last_tm = tm_val
                        r = time_to_row.get(tm_val)
                        if dt_val != last_dt:
                            last_dt = dt_val
                            c = date_to_col.get(dt_val, -1)
                            if c >= 0:
                                seen_cols[c] = True
                        if r is not None and c >= 0:
                            flat_idx = r * max_days + c
                            item_count += 1
                        else:
                            flat_idx = None
                    elif dt_val != last_dt:
                        last_dt = dt_val
                        c = date_to_col.get(dt_val, -1)
                        if c >= 0:
                            seen_cols[c] = True
                        if r is not None and c >= 0:
                            flat_idx = r * max_days + c
                            item_count += 1
                        else:
                            flat_idx = None
                    try:
                        mvs[tag_val][flat_idx] = val
                    except KeyError:
                        s = "Diesel" if tag_val == "Solar" else tag_val
                        arr = arrays.get(s)
                        if arr is None:
                            arr = np.zeros((288, max_days), dtype=np.float32)
                            arrays[s] = arr
                            mvs[s] = memoryview(arr.ravel())
                        mv = mvs[s]
                        mvs[tag_val] = mv
                        if flat_idx is not None and val is not None:
                            mv[flat_idx] = val
                    except TypeError:
                        pass
                del batch

        valid_indices = [i for i, seen in enumerate(seen_cols) if seen]
        if not valid_indices:
            return {}, None, 0

        valid_dates = [all_dates[i] for i in valid_indices]
        col_index = pd.Index(valid_dates, name="Date")
        row_index = pd.Index(times_str, name="Time")

        dfs_out = {}
        for tag_val, arr in list(arrays.items()):
            sliced = arr[:, valid_indices] if len(valid_indices) != max_days else arr
            dfs_out[tag_val] = pd.DataFrame(sliced, index=row_index, columns=col_index, copy=False)

        t1 = time_module.perf_counter()
        logging.info(
            "SQL retrieve_tag_dataframes(%s, %s..%s): %d rows -> %d DataFrames (%d days) in %.2fs",
            namespace, fixed_from, fixed_to, row_count, len(dfs_out), len(valid_dates), t1 - t0
        )
        return dfs_out, valid_dates[-1], item_count

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
        t0 = time_module.perf_counter()
        d = {}
        date_cache = {}
        time_cache = {}
        row_count = 0
        with self._managed_cursor() as curr:
            curr.execute(query)
            while True:
                batch = curr.fetchmany(50000)
                if not batch:
                    break
                row_count += len(batch)
                for ns_val, dt_val, tm_val, tag_val, value in batch:
                    try:
                        date_str = date_cache[dt_val]
                    except KeyError:
                        date_str = date_cache[dt_val] = unfix_date(dt_val)
                    try:
                        time_str = time_cache[tm_val]
                    except KeyError:
                        time_str = time_cache[tm_val] = unfix_time(tm_val)
                    try:
                        d[ns_val][date_str][time_str][tag_val] = value
                    except KeyError:
                        d.setdefault(ns_val, {}).setdefault(date_str, {}).setdefault(time_str, {})[tag_val] = value
                del batch
        t1 = time_module.perf_counter()
        logging.info(
            "SQL _retrieve(%s, %s..%s): %d rows in %.2fs",
            namespace, date or date_from, date or date_to, row_count, t1 - t0
        )
        return d

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
        return "('{}', date('{}'), time('{}'), '{}', {})" \
            .format(value[0], fix_date(value[1]), value[2], value[3], value[4])
