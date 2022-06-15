import scripts.storage.my_sql_storage as mysql
import scripts.storage.postgres_storage as postgres
import scripts.storage.in_mem_cache as cache
import scripts.storage.in_mem_sql_storage as sqlite


def new_instance(uri):
    if uri.startswith("mysql"):
        return mysql.MySqlStorage(uri)
    elif uri.startswith("postgres"):
        return postgres.PostgresStorage(uri)
    elif uri.startswith("cache"):
        return cache.InMemCache()
    elif uri.startswith("sqlite"):
        return sqlite.InMemSqlStorage(uri)
    raise ValueError("Wrong type of storage")
