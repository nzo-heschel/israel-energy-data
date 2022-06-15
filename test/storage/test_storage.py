import unittest
from scripts.storage import storage_util as storage

NAMESPACE = "a.b.c"
DATE_1_2_22 = "01-02-2022"
DATE_2_2_22 = "02-02-2022"
TAG_1 = "T-1"
TAG_2 = "T-2"


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

    def setUp(self):
        self.store = storage.new_instance("sqlite://test_file")
        # self.store = storage.new_instance("cache")
        # self.store = storage.new_instance("mysql://root:mysql_root_123@localhost:3306")
        # self.store = storage.new_instance("postgres://postgres:postgrespw@localhost:55000")
        self.populate()

    def test_clear(self):
        c = storage.new_instance("sqlite://my_file_clear")
        c.insert(NAMESPACE, DATE_1_2_22, TAG_1, "10:00", 10)
        c.clear()
        self.assertEqual(0, c.size())

    def test_simple_retrieve(self):
        val = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_1, time="10:00")
        self.assertEqual(1.0, val[NAMESPACE][DATE_1_2_22]["10:00"][TAG_1])

    '''Verify that retrieve with time="all" returns all timestamps for given namespace/date/tag'''
    def test_retrieve_all(self):
        value_all = self.store.retrieve(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_2, time="all")
        keys_all = value_all[NAMESPACE][DATE_1_2_22].keys()
        for key in keys_all:
            self.assertTrue(key in ('10:00', '10:30', '11:00', '13:10', '13:25'))

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

    '''Verify that when inserting twice with the same arguments, the last one wins'''
    def test_upsert(self):
        c = storage.new_instance("sqlite://test_upsert")
        c.insert(NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 5.0)
        c.insert(NAMESPACE, DATE_1_2_22, "11:11", TAG_1, 6.0)
        v = c.retrieve_value(namespace=NAMESPACE, date=DATE_1_2_22, tag=TAG_1, time="11:11")
        self.assertEqual(6.0, v)

    def test_size(self):
        self.assertEqual(11, self.store.size())


def flatten(lists):
    return [item for sublist in lists for item in sublist]


if __name__ == '__main__':
    unittest.main()
