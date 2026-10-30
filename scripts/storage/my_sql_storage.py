from contextlib import contextmanager
import ssl
import struct

# Python 3.15 removed deprecated ssl.PROTOCOL_TLSv1* constants still referenced by mysql-connector-python
for _attr in ("PROTOCOL_TLSv1", "PROTOCOL_TLSv1_1", "PROTOCOL_TLSv1_2"):
    if not hasattr(ssl, _attr):
        setattr(ssl, _attr, ssl.PROTOCOL_TLS)

from mysql.connector.network import NetworkBrokerPlain, MySQLSocket
from mysql.connector.errors import InterfaceError, OperationalError, ReadTimeoutError
from mysql.connector.pooling import MySQLConnectionPool

from scripts.storage.sql_storage import SqlStorageTemplate
from furl import furl

# Buffer MySQL socket reads with a 64KB BufferedReader and avoid per-row settimeout syscalls
def _buffered_broker_recv(self, sock, address):
    try:
        rfile = getattr(sock, "_rfile", None)
        if rfile is None or rfile.closed:
            rfile = sock.makefile("rb", 65536)
            sock._rfile = rfile
        header = rfile.read(4)
        if len(header) < 4:
            raise InterfaceError(errno=2013)
        payload_len = header[0] | (header[1] << 8) | (header[2] << 16)
        self._pktnr = header[3]
        payload = rfile.read(payload_len)
        if len(payload) < payload_len:
            raise InterfaceError(errno=2013)
        return bytearray(header + payload)
    except (TimeoutError,) as err:
        raise ReadTimeoutError(errno=3024, msg=str(err)) from err
    except OSError as err:
        raise OperationalError(errno=2055, values=(address, str(err))) from err


def _fast_socket_recv(self, read_timeout=None):
    if read_timeout != getattr(self, "_last_read_timeout", object()):
        try:
            if not self._connection_timeout and self.sock is not None:
                self.sock.settimeout(float(read_timeout) if read_timeout else None)
                self._last_read_timeout = read_timeout
        except OSError:
            pass
    return self._netbroker.recv(self.sock, self.address)


NetworkBrokerPlain.recv = _buffered_broker_recv
MySQLSocket.recv = _fast_socket_recv

energy_db_name = "energy_data"


class MySqlStorage(SqlStorageTemplate):
    SQL_ON_CONFLICT = "as new_value ON DUPLICATE KEY UPDATE value=new_value.value"
    SQL_AND_DATE = " AND date = date('{date}')"
    SQL_AND_DATE_RANGE = " AND date BETWEEN date('{from_date}') AND date('{to_date}')"
    SQL_AND_TIME = " AND time = time('{time}')"
    SQL_SUM_HOUR = "SELECT namespace, date, hour(time), tag, SUM(value) from main_table " \
                   "WHERE namespace = '{namespace}' "
    SQL_SUM_DAY = "SELECT namespace, date, time('00:00'), tag, SUM(value) from main_table " \
                  "WHERE namespace = '{namespace}' "
    SQL_SUM_MONTH = "SELECT namespace, date(concat_ws('-', year(date), month(date), 1)), '00:00', tag, SUM(value) from main_table " \
                    "WHERE namespace = '{namespace}' "
    SQL_GROUP_BY_DATE = " GROUP BY date, tag"
    SQL_GROUP_BY_HOUR = " GROUP BY date, hour(time), tag"
    SQL_GROUP_BY_MONTH = "GROUP BY date(concat_ws('-', year(date), month(date), 1)), tag"

    def __init__(self, uri):
        self.url = furl(uri)
        self.pool = self._init_pool()
        self._execute_query("CREATE DATABASE IF NOT EXISTS energy_data")
        self.pool = self._init_pool(database=energy_db_name)
        self._execute_query(self.SQL_CREATE_TABLE)

    def _init_pool(self, database=None):
        user = self.url.username
        password = self.url.password
        host = self.url.host
        port = self.url.port or 3306
        db_config = {
            "user": user,
            "password": password,
            "host": host,
            "port": port
        }
        if database:
            db_config["database"] = database
        return MySQLConnectionPool(pool_name="mysql_pool", pool_size=5, **db_config)

    @contextmanager
    def _managed_cursor(self, commit=False):
        conn = self.pool.get_connection()
        if not conn.is_connected():
            conn.reconnect(attempts=3, delay=1)
        cursor = conn.cursor()
        cursor.execute("SET SESSION net_write_timeout = 600, SESSION net_read_timeout = 600")
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            try:
                cursor.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass
