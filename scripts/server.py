import datetime
import logging
import os
import bottle
from bottle import route
from dateutil.relativedelta import relativedelta
import http.client
import scripts.noga as noga
import scripts.storage.storage_util as storage

PORT = int(os.environ.get("PORT", 9999))
SMP_DATE_FORMAT = "%d-%m-%Y"
STORAGE_URI = os.environ.get('STORAGE_URI', "mysql://root:mysql_root_123@localhost:3306")
store = storage.new_instance(STORAGE_URI)


@route('/')
def hello():
    return bottle.static_file(filename="index.html", root=os.environ['PYTHONPATH'] + "/" + "resources")


@route('/update')
def update():
    try:
        source, data_type, start_date, end_date = query_variables(bottle.request.query)[0:4]
        if source == "noga" or source == "all":
            noga.update(store, noga_type=data_type, start_date=start_date, end_date=end_date)
    except Exception as ex:
        logging.exception("Error: %s", ex)
        return bottle.HTTPError(status=400, body=ex)
    return bottle.HTTPResponse(status=200, body="OK")


@route('/get')
def get():
    try:
        source, data_type, start_date, end_date, tag, result_format, time = query_variables(bottle.request.query)
        data = {}
        if source == "noga":
            data = noga.get(store, noga_type=data_type, start_date=start_date,
                            end_date=end_date, tag=tag, time=time)
        formatted_data = format_data(data, result_format)
        return bottle.HTTPResponse(status=200, body=formatted_data)
    except Exception as ex:
        logging.error(ex)
        return bottle.HTTPError(status=400, body=ex)


def format_data(data, result_format):
    if result_format == "json":
        return data


def default_dates():
    today = datetime.date.today()
    start_time = today + relativedelta(months=-1)
    end = today.strftime(SMP_DATE_FORMAT)
    start = start_time.strftime(SMP_DATE_FORMAT)
    return start, end


def query_variables(query):
    source = query.source or "all"
    data_type = query.type or "all"
    start_date = query.start_date
    end_date = query.end_date or default_dates()[1]  # today
    result_format = query.format or "json"
    time = query.time or "hour"
    tag = query.tag or None
    return source, data_type, start_date, end_date, tag, result_format, time


def http_debug_level(level):
    http.client.HTTPConnection.debuglevel = level
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


if __name__ == "__main__":
    FORMAT = '%(asctime)s : %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    http_debug_level(1)
    logging.info("Starting")
    bottle.run(host='0.0.0.0', port=PORT, debug=True, reloader=True)
