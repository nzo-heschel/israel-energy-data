import datetime
import logging
import os

from bottle import route, run, static_file
from dateutil.relativedelta import relativedelta

import noga

PORT = int(os.environ.get("PORT", 9999))
SMP_DATE_FORMAT = "%d-%m-%Y"

@route('/')
def hello():
    return static_file(filename="index.html", root=os.environ['PYTHONPATH'] + "/" + "resources")


def default_dates():
    today = datetime.date.today()
    start_time = today + relativedelta(months=-1)
    end = today.strftime(SMP_DATE_FORMAT)
    start = start_time.strftime(SMP_DATE_FORMAT)
    return start, end


@route('/smp')
def smp_default():
    start, end = default_dates()
    return smp(start, end)


@route('/smp/<date1>/<date2>')
def smp(date1, date2):
    return noga.smp(date1, date2)


@route('/cost')
def cost_default():
    start, end = default_dates()
    return cost(start, end)


@route('/cost/<date1>/<date2>')
def cost(date1, date2):
    return noga.cost(date1, date2)


@route('/forecast-1')
def forecast1_default():
    start, end = default_dates()
    return forecast1(start, end)


@route('/forecast-1/<date1>/<date2>')
def forecast1(date1, date2):
    return noga.forecast1(date1, date2)


@route('/forecast-2')
def forecast2_default():
    start, end = default_dates()
    return forecast2(start, end)


@route('/forecast-2/<date1>/<date2>')
def forecast2(date1, date2):
    return noga.forecast2(date1, date2)


if __name__ == "__main__":
    FORMAT = '%(asctime)s  %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logging.info("Starting")
    run(host='0.0.0.0', port=PORT, debug=True, reloader=True)
