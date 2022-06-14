import my_sql_storage as mysql
import postgres_storage as postgres
import in_mem_cache as cache
import in_mem_sql_storage as sqlite


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

# c = new_instance("mysql://root:mysql_root_123@localhost:3306")
# c = new_instance("sqlite://my_file")
# c = new_instance("postgres://postgres:postgrespw@localhost:55000")
# c = new_instance("cache://")
