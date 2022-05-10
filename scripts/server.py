import datetime
import logging
import os

from bottle import route, run
from dateutil.relativedelta import relativedelta

import noga

PORT = int(os.environ.get("PORT", 9999))
SMP_DATE_FORMAT = "%d-%m-%Y"


@route('/')
def hello():
    return '<p>Use <a href="/smp">/smp</a> to get last 3 months SMP data' \
           '<br>Use /smp/&lt;from date&gt;/&lt;to date&gt; for date range where date format is DD-MM-YYYY' \
           '<br>Use <a href="/cost">/cost</a> to get last 3 months Cost data' \
           '<br>Use /cost/&lt;from date&gt;/&lt;to date&gt; for date range where date format is DD-MM-YYYY' \
           '</p>'


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
def smp_default():
    start, end = default_dates()
    return cost(start, end)


@route('/cost/<date1>/<date2>')
def cost(date1, date2):
    return noga.cost(date1, date2)


if __name__ == "__main__":
    FORMAT = '%(asctime)s  %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logging.info("Starting")
    run(host='0.0.0.0', port=PORT, debug=True, reloader=True)
