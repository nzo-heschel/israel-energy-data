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
    return "<p>Use /smp to get last 3 months data" \
           "<br>Use /smp/&lt;from date&gt;/&lt;to date&gt; for date range where date format is DD-MM-YYYY" \
           "</p>"
    # return "Use /smp to get last 3 months data\n" \
    #        "Use /smp/<from>/<to> for date range where date format is DD-MM-YYYY"


@route('/smp')
def smp_default():
    today = datetime.date.today()
    start_time = today + relativedelta(months=-1)
    end = today.strftime(SMP_DATE_FORMAT)
    start = start_time.strftime(SMP_DATE_FORMAT)
    return smp(start, end)


@route('/smp/<date1>/<date2>')
def smp(date1, date2):
    date1 = date1.replace("-", "/")
    date2 = date2.replace("-", "/")
    smp_data = noga.smp(date1, date2)
    return smp_data


if __name__ == "__main__":
    FORMAT = '%(asctime)s  %(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logging.info("Starting")
    run(host='0.0.0.0', port=PORT, debug=True, reloader=True)
