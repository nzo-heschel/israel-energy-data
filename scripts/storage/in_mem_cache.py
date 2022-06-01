from storage import Storage, fix_date


class InMemCache(Storage):
    def __init__(self):
        self.clear()

    def clear(self):
        self._in_mem_cache = {}

    def _insert(self, val):
        self.insert(val[0], val[1], val[2], val[3], val[4])

    def insert(self, namespace, date, time, tag, value):
        if namespace not in self._in_mem_cache:
            self._in_mem_cache[namespace] = {}
        per_namespace = self._in_mem_cache.get(namespace)
        if date not in per_namespace:
            per_namespace[date] = {}
        per_date = per_namespace.get(date)
        if time not in per_date:
            per_date[time] = {}
        per_time = per_date.get(time)
        per_time[tag] = value

    def bulk_insert(self, values):
        for value in values:
            self.insert(value[0], value[1], value[2], value[3], value[4])

    def retrieve(self, namespace, date, time="all", tag=None):
        if time not in ["all", "day", "hour"] and tag:  # single value
            value = self.retrieve_value(namespace, date, time, tag)
            return {namespace: {date: {time: {tag: value}}}}
        values = self._in_mem_cache.get(namespace, {}).get(date, {})
        if time not in ["all", "day", "hour"]:
            values = {time: values.get(time)}
        day_result = {}
        for time_key in values:
            the_time_key = time_key if time == "all" \
                else (time_key[0:3] + "00" if time == "hour"
                      else "00:00" if time == "day" else time)
            if not day_result.get(the_time_key):
                day_result[the_time_key] = {}
            hour_result = day_result.get(the_time_key)
            values_by_tag = values.get(time_key)
            tag_keys = values_by_tag.keys() if not tag else [tag]
            for tag_key in tag_keys:
                if time == "all":  # get all values
                    day_result[the_time_key][tag_key] = values_by_tag.get(tag_key)
                else:
                    if not hour_result.get(tag_key):
                        hour_result[tag_key] = 0
                    hour_result[tag_key] = hour_result[tag_key] + values_by_tag.get(tag_key, 0.0)
        return {namespace: {date: day_result}}

    def retrieve_value(self, namespace, date, time, tag):
        return self._in_mem_cache \
            .get(namespace, {}) \
            .get(date, {}) \
            .get(time, {}) \
            .get(tag, None)

    def retrieve_range(self, namespace, from_date, to_date, tag=None, time="day"):
        values = self._in_mem_cache.get(namespace, {})
        proper_date_from = fix_date(from_date)
        proper_date_to = fix_date(to_date)
        dates = [date for date in values.keys() if proper_date_from <= fix_date(date) <= proper_date_to]
        return_values = {date: self.retrieve(namespace, date, time, tag).get(namespace).get(date) for date in dates}
        return {namespace: return_values}

    def as_dictionary(self):
        return dict(self._in_mem_cache)

    def __str__(self):
        return str(self._in_mem_cache)
