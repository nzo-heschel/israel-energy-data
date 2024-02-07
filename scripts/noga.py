import logging
import tempfile
import urllib.request
import pandas as pd
import re
import urllib.request
import os
import datetime
from dateutil.relativedelta import relativedelta

noga_file_url = 'https://www.noga-iso.co.il/Umbraco/Surface/Export/ExportCost/?startDateString={}&endDateString={}&culture=en-US&dataType={}'
SMP_CONST = "ConstrainedSmp"
SMP_UNCONST = "UnconstrainedSmp"

COST_AVERAGE = "AverageCost"
COST_COST = "Cost"
COST_REN = "RenewableGen"
COST_CONV = "ConventionalGen"
COST_DEMAND = "SystemDemand"

FORECAST_REN = "Renewable"
FORECAST_DEMAND = "SystemDemand"

FIRST_DATE = "01-01-2010"

proxies = {
    'https': os.environ.get('PROXY_SERVER'),
}


def update(store, noga_type, start_date, end_date):
    noga_types = NOGA_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA_TYPE_MAPPING
    # TODO: error handling wrong noga_type
    result = {}
    for a_type in noga_types:
        namespace = "noga." + a_type
        ns_start_date = start_date or store.latest_date(namespace) or "01-01-2000"
        json_list = request_file(a_type, ns_start_date, end_date)
        result[namespace] = json_list
    values = []
    count = 0
    total_count = 0
    for namespace in result:
        for entry in result.get(namespace):
            date0 = entry.get("Date")
            date = date0.replace("/", "-")
            time = entry.get("Time")
            for tag in [key for key in entry.keys() if key not in ["Date", "Time", "FileDate", "IsOnBlobList"]]:
                val = re.sub(r'[^0-9.]', '', str(entry.get(tag)).strip())
                values.append((namespace, date, time[0:5], tag, val))
                count = count + 1
                total_count = total_count + 1
                if count > 100:
                    store.bulk_insert(values)
                    values = []
                    count = 0
    if values:
        store.bulk_insert(values)
    logging.info("Inserted %s values into storage", total_count)
    return "Inserted {} values into storage".format(total_count)


def get(store, noga_type, start_date, end_date, tag, time="hour"):
    noga_types = NOGA_TYPE_MAPPING if noga_type == "all" else [noga_type] if noga_type else NOGA_TYPE_MAPPING
    start_date = start_date or one_month_ago()
    logging.info("Retrieving noga data with type(s) %s from %s until %s with \"%s\" interval and tag \"%s\"",
                 ", ".join(noga_types), start_date, end_date, time, tag)
    result = {}
    for a_type in noga_types:
        data = store.retrieve_range("noga." + a_type, start_date, end_date, time=time, tag=tag)
        result.update(data)
    for key in result:
        logging.info("Retrieved {} items of type {}".format(sum(len(v) for v in result[key].values()), key))
    return result


def one_month_ago():
    date = datetime.date.today() + relativedelta(months=-1)
    return date.strftime("%d-%m-%Y")


NOGA_TYPE_MAPPING = {
    'smp': 'SMP',
    'cost': 'Cost',
    'forecast1': 'DemandForecast&forecastType=1',
    'forecast2': 'DemandForecast&forecastType=2'
}


def request_file(noga_type, start_date, end_date):
    logging.info("Request noga/%s data from %s to %s", noga_type, start_date, end_date)
    data_type = NOGA_TYPE_MAPPING.get(noga_type)
    if data_type is None:
        return {"error": "Unrecognized Noga type"}
    start_date = start_date.replace("-", "/")
    end_date = end_date.replace("-", "/")
    url = noga_file_url.format(start_date, end_date, data_type)
    logging.info(url)
    json_list = get_data_from_file(url)
    logging.info("Received %s values for noga.%s", len(json_list), noga_type)
    return json_list



def get_data_from_file(url):
    xl_file = tempfile.NamedTemporaryFile()

    try:
        urllib.request.urlretrieve(url, xl_file.name)
        df = pd.read_excel(xl_file.name, header=1)
    except Exception as ex:
        raise ex
    finally:
        xl_file.close()

    labels = df.columns.values.tolist()
    logging.info("Labels: %s", labels)
    df.drop(columns=[label for label in labels if label[:7] == "Unnamed"], inplace=True)
    labels = df.columns.values.tolist()
    new_labels = [camel_no_unit(label) for label in labels]
    logging.info("New labels: %s", new_labels)
    df.columns = new_labels  # rename columns
    json_list = []
    for row in df.itertuples():
        json_row = {"Date": row.Date, "Time": row.Time}
        for i in range(2, len(labels)):
            json_row[new_labels[i]] = str(row[i+1])
        json_list.append(json_row)
    return json_list

pattern_units = re.compile(r" [\[(].*[\])]")


def camel_no_unit(s):
    s = pattern_units.sub("", s)
    s = s.title().replace(" ", "")
    s = s.replace("Hour", "Time")
    return s
