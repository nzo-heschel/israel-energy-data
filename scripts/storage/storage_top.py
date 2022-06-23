class Storage:

    def clear(self):
        pass

    def insert(self, namespace, date, time, tag, value):
        """Insert single value with namespace, date, time and tag"""
        pass

    def bulk_insert(self, values):
        """Insert a sequence of values. Each value is a list with namespace, date, time, tag and value."""
        pass

    def retrieve(self, namespace, date, time=None, tag=None):
        """Retrieve values from storage. If date, time and tag are specified then return single value.\n
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

    def retrieve_range(self, namespace, from_date, to_date, tag=None, time="day"):
        """Retrieve values for the given range of dates."""
        pass

    def latest_date(self, namespace):
        pass

    def size(self):
        pass

    def print(self):
        pass


def dict_key_value(d, key):
    if not d.get(key):
        d[key] = {}
    return d.get(key)


def fix_date(date):
    return date[6:10] + "-" + date[3:5] + "-" + date[0:2] if date[2] == "-" else date


def unfix_date(date):
    if not date:
        return None
    str_date = str(date)
    return str_date[8:10] + "-" + str_date[5:7] + "-" + str_date[0:4] if str_date[4] == "-" else str_date


def unfix_time(time):
    str_time = str(time) + ":00"  # if time is just a number
    return "0" + str_time[0:4] if str_time[2] != ":" else str_time[0:5]
