import datetime
import unittest
from parameterized import parameterized_class
import scripts.storage.storage_util as storage

NAMESPACE = "a.b.c"
NAMESPACE_2 = "1.2.3"  # only one date
DATE_1_2_22 = "01-02-2022"
DATE_2_2_22 = "02-02-2022"
TAG_1 = "T-1"
TAG_2 = "T-2"
TAG_3 = "T-3"

PARAMS = [
    ("cache",),
    ("sqlite://",),
    ("mysql://root:mysql_root_123@localhost:3306",),
    ("postgres://postgres:postgrespw@localhost:32768",)
]


@parameterized_class("uri", PARAMS)
class TestStorage(unittest.TestCase):
    def populate(self):
        self.store.clear()
        self.store.insert(NAMESPACE, DATE_1_2_22, "10:00", TAG_1, 1.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "10:00", TAG_2, 2.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "10:30", TAG_1, 3.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "10:30", TAG_2, 4.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "11:00", TAG_1, 5.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "13:10", TAG_2, 6.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "13:25", TAG_2, 7.0)
        self.store.insert(NAMESPACE, DATE_2_2_22, "03:30", TAG_1, 8.0)
        self.store.insert(NAMESPACE, DATE_2_2_22, "03:40", TAG_2, 9.0)
        self.store.insert(NAMESPACE, DATE_2_2_22, "03:50", TAG_2, 10.0)
        self.store.insert(NAMESPACE, DATE_2_2_22, "06:40", TAG_2, 11.0)
        self.store.insert(NAMESPACE_2, DATE_2_2_22, "03:50", TAG_2, 10.0)
        self.store.insert(NAMESPACE_2, DATE_2_2_22, "06:40", TAG_2, 11.0)

    def setUp(self):
        self.store = storage.new_instance(self.uri)
        self.populate()

    def test_simple_retrieve(self):
        val = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_1, time="10:00")
        self.assertEqual(1.0, val[NAMESPACE][DATE_1_2_22]["10:00"][TAG_1])

    '''Verify that retrieve with time="all" returns all timestamps for given namespace/date/tag'''
    def test_retrieve_all(self):
        value_all = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_2, time="all")
        keys_all = value_all[NAMESPACE][DATE_1_2_22].keys()
        self.assertTrue(sorted(keys_all), sorted(('10:00', '10:30', '11:00', '13:10', '13:25')))

    '''Verify that time="hour" with a tag works properly'''
    def test_retrieve_hour_with_tag(self):
        value_hour_tag = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_2, time="hour")
        self.assertEqual(2, len(value_hour_tag[NAMESPACE][DATE_1_2_22]))
        unique_tags = set(flatten([d.keys() for d in value_hour_tag[NAMESPACE][DATE_1_2_22].values()]))
        self.assertEqual(1, len(unique_tags))
        self.assertTrue(TAG_2 in unique_tags)

    '''Verify that time="hour" without a tag works properly'''
    def test_retrieve_hour_without_tag(self):
        value_hour = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, time="hour")
        value_hour_entries = value_hour[NAMESPACE][DATE_1_2_22]
        self.assertEqual(2, len(value_hour_entries["10:00"]))
        value_hour_keys = value_hour_entries.keys()
        self.assertTrue(all(key.endswith(":00") for key in value_hour_keys))

    '''Verify that time="day" works properly'''
    def test_retrieve_day(self):
        value_day = self.store.retrieve(namespace=NAMESPACE, date=DATE_2_2_22, time="day")
        self.assertEqual(30.0, value_day[NAMESPACE][DATE_2_2_22]["00:00"][TAG_2])
        value_day_tag = self.store.retrieve(namespace=NAMESPACE, date=DATE_2_2_22, tag=TAG_2, time="day")
        self.assertEqual(1, len(value_day_tag[NAMESPACE][DATE_2_2_22]["00:00"]))

    def test_size(self):
        self.assertEqual(13, self.store.size())

    def test_latest_date(self):
        self.assertEqual(DATE_2_2_22, self.store.latest_date(NAMESPACE))
        self.assertEqual(DATE_2_2_22, self.store.latest_date(NAMESPACE_2))
        self.assertIsNone(self.store.latest_date("foo"))


@parameterized_class("uri", PARAMS)
class TestStorageNoPopulate(unittest.TestCase):
    def setUp(self):
        self.store = storage.new_instance(self.uri)

    def test_clear(self):
        self.store.insert(NAMESPACE, DATE_1_2_22, "10:00", TAG_1, 10)
        self.store.clear()
        self.assertEqual(0, self.store.size())

    '''Verify that when inserting twice with the same arguments, the last one wins'''
    def test_upsert(self):
        self.store.insert(NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 5.0)
        self.store.insert(NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 6.0)
        v = self.store.retrieve_value(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_1, time="11:11")
        self.assertEqual(6.0, v)

    def test_bulk_insert(self):
        values = [[NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 5.0], [NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 6.0]]
        self.store.bulk_insert(values)
        v = self.store.retrieve_value(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_1, time="11:11")
        self.assertEqual(6.0, v)


@parameterized_class("uri", PARAMS)
class TestStorageMonthly(unittest.TestCase):
    def setUp(self):
        self.store = storage.new_instance(self.uri)
        for day in range(1, 21):  # total 20 days
            date1 = datetime.date(2011, 1, day).strftime("%d-%m-%Y")
            date2 = datetime.date(2011, 2, day).strftime("%d-%m-%Y")
            self.store.insert(NAMESPACE, date1, "10:00", TAG_1, 1.0)
            self.store.insert(NAMESPACE, date1, "10:30", TAG_1, 2.0)
            self.store.insert(NAMESPACE, date1, "10:30", TAG_2, 2.0)
            self.store.insert(NAMESPACE, date2, "10:00", TAG_1, 5.0)
            self.store.insert(NAMESPACE, date2, "10:00", TAG_2, 2.0)

    def test_by_month(self):
        v1 = self.store.retrieve_range(NAMESPACE, "08-01-2011", "05-02-2011", time="month")
        # 13 days in January (8 to 20)
        self.assertEqual(39, v1[NAMESPACE]["01-01-2011"]["00:00"][TAG_1])
        self.assertEqual(26, v1[NAMESPACE]["01-01-2011"]["00:00"][TAG_2])
        # 5 days in February (1 to 5)
        self.assertEqual(25, v1[NAMESPACE]["01-02-2011"]["00:00"][TAG_1])
        self.assertEqual(10, v1[NAMESPACE]["01-02-2011"]["00:00"][TAG_2])

        v2 = self.store.retrieve_range(NAMESPACE, "08-01-2011", "12-01-2011", time="month", tag=TAG_1)
        self.assertEqual(1, len(v2[NAMESPACE]["01-01-2011"]["00:00"]))
        self.assertEqual(15, v2[NAMESPACE]["01-01-2011"]["00:00"][TAG_1])


class TestStorageNonParametrized(unittest.TestCase):
    def test_bad_uri(self):
        self.assertRaises(ValueError, storage.new_instance, "unrecognized uri")


def flatten(lists):
    return [item for sublist in lists for item in sublist]


if __name__ == '__main__':
    unittest.main()
