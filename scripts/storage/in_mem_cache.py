from scripts.storage.storage_top import Storage, fix_date, unfix_date, dict_key_value
import threading


class InMemCache(Storage):
    def __init__(self):
        self._lock = threading.RLock()
        self.clear()

    def clear(self):
        with self._lock:
            self._in_mem_cache = {}

    def _insert(self, val):
        self.insert(val[0], val[1], val[2], val[3], val[4])

    def insert(self, namespace, date, time, tag, value):
        with self._lock:
            per_namespace = dict_key_value(self._in_mem_cache, namespace)
            per_date = dict_key_value(per_namespace, fix_date(date))
            per_time = dict_key_value(per_date, time)
            per_time[tag] = value

    def bulk_insert(self, values):
        with self._lock:
            for value in values:
                self.insert(value[0], value[1], value[2], value[3], value[4])

    def retrieve(self, namespace, date, time="all", tag=None):
        with self._lock:
            if time not in ["all", "day", "hour"] and tag:  # single value
                value = self.retrieve_value(namespace, fix_date(date), time, tag)
                return {namespace: {date: {time: {tag: value}}}}
            values = self._in_mem_cache.get(namespace, {}).get(fix_date(date), {})
            if time not in ["all", "day", "hour"]:
                values = {time: values.get(time)}
            day_result = {}
            for time_key in values:
                the_time_key = time_key if time == "all" \
                    else (time_key[0:3] + "00" if time == "hour"
                          else "00:00" if time == "day" else time)
                values_by_tag = values.get(time_key)
                tag_keys = values_by_tag.keys() if not tag else [tag]
                if not day_result.get(the_time_key):
                    day_result[the_time_key] = {}
                hour_result = day_result.get(the_time_key)
                for tag_key in tag_keys:
                    if tag_key not in values_by_tag:
                        continue
                    if time == "all":  # get all values
                        day_result[the_time_key][tag_key] = values_by_tag.get(tag_key)
                    else:
                        if not hour_result.get(tag_key):
                            hour_result[tag_key] = 0
                        hour_result[tag_key] = hour_result[tag_key] + values_by_tag.get(tag_key, 0.0)
            for time_key in list(day_result.keys()):
                if not day_result.get(time_key):
                    del day_result[time_key]
            return {namespace: {date: day_result}}

    def retrieve_value(self, namespace, date, time, tag):
        with self._lock:
            return self._in_mem_cache \
                .get(namespace, {}) \
                .get(fix_date(date), {}) \
                .get(time, {}) \
                .get(tag, None)

    def retrieve_range(self, namespace, from_date, to_date, tag=None, time="day"):
        with self._lock:
            values = self._in_mem_cache.get(namespace, {})
            proper_date_from = fix_date(from_date)
            proper_date_to = fix_date(to_date)
            dates = [date for date in values.keys() if proper_date_from <= fix_date(date) <= proper_date_to]
            if time == "month":
                per_month = {}
                for date in dates:
                    date_prefix = date[0:7]
                    date_key = unfix_date(date_prefix + "-01")
                    per_month[date_key] = per_month.get(date_key, {"00:00": {}})
                    per_tag = self.retrieve(namespace, date, "day", tag).get(namespace).get(date).get("00:00")
                    for t in per_tag:
                        per_month[date_key]["00:00"][t] = per_month[date_key]["00:00"].get(t, 0) + per_tag[t]
                return {namespace: per_month}
            else:
                return_values = {unfix_date(date): self.retrieve(namespace, date, time, tag).get(namespace).get(date)
                                 for date in dates}
                return {namespace: return_values}

    def as_dictionary(self):
        with self._lock:
            return dict(self._in_mem_cache)

    def latest_date(self, namespace):
        with self._lock:
            per_namespace = self._in_mem_cache.get(namespace)
            return unfix_date(max(per_namespace)) if per_namespace else None

    def size(self):
        with self._lock:
            return _count(self._in_mem_cache)

    def __str__(self):
        with self._lock:
            return str(self._in_mem_cache)


def _count(d):
    return sum([_count(v) if isinstance(v, dict) else 1 for v in d.values()])
