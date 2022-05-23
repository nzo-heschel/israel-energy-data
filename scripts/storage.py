class Storage:
    def insert(self, namespace, date, time, tag, value):
        """Insert single value with namespace, date, time and tag"""
        pass

    def bulk_insert(self, namespace, values):
        """Insert a sequence of values. Each value has a date, time, tag and value"""
        pass

    def retrieve(self, namespace, date, time=None, tag=None):
        """Retrieve values from storage. If date, time and tag are specified then return single value
        (interval is ignored).\n
        time is either HH:mm or hour/day/all.\n
        If HH:mm then return specific value. Otherwise:\n
        hour: return hourly data\n
        day: return (single) value\n
        all: return highest granularity\n
        If tag is set then return values for the specified tag, otherwise for all tags.\n
        Returns a dictionary by date/time/tag. If interval is daily then time is 00:00"""
        pass

    def retrieve_value(self, namespace, date, time, tag):
        """Returns a simple value of None"""
        pass

    def retrieve_range(self, namespace, from_date, to_date, tag, interval="day"):
        """Retrieve values for the given range of dates and according to the interval (hour/day/all)."""
        pass

    def print(self):
        pass


class InMemCache(Storage):
    def __init__(self):
        self._in_mem_cache = {}

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

    def bulk_insert(self, namespace, values):
        for value in values:
            self.insert(namespace, value[0], value[1], value[2], value[3])

    def retrieve(self, namespace, date, tag=None, time=None):
        if time not in ["all", "day", "hour"]:
            value = self.retrieve_value(namespace, date, time, tag)
            return {namespace: {date: {time or "00:00": {tag: value}}}}
        values = self._in_mem_cache.get(namespace, {}).get(date, {})
        day_result = {}
        for time_key in values:
            the_time_key = time_key if time == "all" else (time_key[0:3] + "00" if time == "hour" else "00:00")
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

    def as_dictionary(self):
        return dict(self._in_mem_cache)

    def __str__(self):
        return str(self._in_mem_cache)
